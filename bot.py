import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# -------------------- إعدادات البوت --------------------

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("DuaSpaceBot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@DuaSpace1").strip()

try:
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "0").strip())
except ValueError:
    ADMIN_ID = 0

CONTACT_USERNAME = (
    os.environ.get("CONTACT_USERNAME", "xdua1")
    .strip()
    .lstrip("@")
)

DB_PATH = os.environ.get("DATABASE_PATH", "duaspace.db")
CONTACT_URL = f"https://t.me/{CONTACT_USERNAME}"
CHANNEL_URL = "https://t.me/DuaSpace1"

DEFAULT_WELCOME = (
    "أهلًا بك في Dua Space! 🪐\n"
    "اختاري الخدمة المناسبة، وأرسلي طلبك من خلال الأزرار أدناه."
)

DEFAULT_FOOTER = "\n\n—\n🪐 قناة Dua Space"

DEFAULT_SERVICES = [
    (
        "🎨 التصميم الجرافيكي والهويات البصرية",
        "تصميمات وهوية بصرية تناسب مشروعك.",
        "حسب تفاصيل الطلب",
    ),
    (
        "🖼️ تصميم الشعارات والإعلانات",
        "تصميم شعار أو إعلان لصفحتك أو مشروعك.",
        "حسب تفاصيل الطلب",
    ),
    (
        "💌 تصميم الدعوات والبطاقات",
        "دعوات مناسبات وبطاقات بتصميم مميز.",
        "حسب تفاصيل الطلب",
    ),
    (
        "📦 خدمات أخرى",
        "أرسلي تفاصيل الخدمة المطلوبة وسنراجع إمكانية تنفيذها.",
        "يُحدد بعد مراجعة الطلب",
    ),
]


# -------------------- قاعدة البيانات --------------------

def db_connect():
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def db_execute(sql, params=()):
    connection = db_connect()
    try:
        cursor = connection.execute(sql, params)
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def db_one(sql, params=()):
    connection = db_connect()
    try:
        return connection.execute(sql, params).fetchone()
    finally:
        connection.close()


def db_all(sql, params=()):
    connection = db_connect()
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def get_setting(key, default=""):
    row = db_one(
        "SELECT value FROM settings WHERE key = ?",
        (key,),
    )
    return row["value"] if row else default


def set_setting(key, value):
    db_execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def init_db():
    connection = db_connect()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price TEXT NOT NULL DEFAULT 'حسب الطلب',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                service_id INTEGER,
                service_title TEXT NOT NULL,
                price TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'جديد',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    if db_one(
        "SELECT key FROM settings WHERE key = 'seeded_services'"
    ) is None:
        for title, description, price in DEFAULT_SERVICES:
            db_execute(
                """
                INSERT INTO services(title, description, price, active)
                VALUES(?, ?, ?, 1)
                """,
                (title, description, price),
            )

        set_setting("seeded_services", "1")

    if db_one(
        "SELECT key FROM settings WHERE key = 'welcome_msg'"
    ) is None:
        set_setting("welcome_msg", DEFAULT_WELCOME)

    if db_one(
        "SELECT key FROM settings WHERE key = 'footer'"
    ) is None:
        set_setting("footer", DEFAULT_FOOTER)


def save_user(user):
    if not user:
        return

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    db_execute(
        """
        INSERT INTO users(
            user_id, username, first_name, first_seen, last_seen
        )
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_seen = excluded.last_seen
        """,
        (
            user.id,
            user.username or "",
            user.first_name or "",
            now,
            now,
        ),
    )


def is_admin_user(user_id):
    return bool(ADMIN_ID and user_id == ADMIN_ID)


# -------------------- القوائم والأزرار --------------------

def main_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛍️ تصفح الخدمات",
                    callback_data="services",
                )
            ],
            [
                InlineKeyboardButton(
                    "💳 الدفع والاستفسار",
                    url=CONTACT_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    "📢 قناة Dua Space",
                    url=CHANNEL_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 التواصل معنا",
                    url=CONTACT_URL,
                )
            ],
        ]
    )


def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛍️ إدارة الخدمات",
                    callback_data="admin_services",
                )
            ],
            [
                InlineKeyboardButton(
                    "📥 طلبات العملاء",
                    callback_data="admin_orders",
                )
            ],
            [
                InlineKeyboardButton(
                    "📢 النشر في القناة",
                    callback_data="publish_help",
                ),
                InlineKeyboardButton(
                    "📊 الإحصائيات",
                    callback_data="admin_stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚙️ إعدادات النصوص",
                    callback_data="admin_settings",
                )
            ],
            [
                InlineKeyboardButton(
                    "👀 معاينة واجهة العميل",
                    callback_data="show_customer_menu",
                )
            ],
        ]
    )


def services_keyboard(active_only=True):
    query = "SELECT id, title FROM services"

    if active_only:
        query += " WHERE active = 1"

    query += " ORDER BY id DESC LIMIT 50"

    rows = db_all(query)

    buttons = [
        [
            InlineKeyboardButton(
                row["title"][:60],
                callback_data=f"service:{row['id']}",
            )
        ]
        for row in rows
    ]

    buttons.append(
        [
            InlineKeyboardButton(
                "⬅️ القائمة الرئيسية",
                callback_data="home",
            )
        ]
    )

    return InlineKeyboardMarkup(buttons), rows


def admin_services_keyboard():
    rows = db_all(
        "SELECT id, title, active FROM services ORDER BY id DESC LIMIT 50"
    )

    buttons = []

    for row in rows:
        status = "✅" if row["active"] else "⏸️"

        buttons.append(
            [
                InlineKeyboardButton(
                    f"{status} {row['title'][:48]}",
                    callback_data=f"svcadmin:{row['id']}",
                )
            ]
        )

    buttons.extend(
        [
            [
                InlineKeyboardButton(
                    "➕ إضافة خدمة",
                    callback_data="svc_add",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ لوحة الإدارة",
                    callback_data="admin_home",
                )
            ],
        ]
    )

    return InlineKeyboardMarkup(buttons)


# -------------------- البداية والمساعدة --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    context.user_data.pop("flow", None)

    if is_admin_user(user.id):
        await update.effective_message.reply_text(
            "🪐 أهلًا دعاء!\n"
            "دي لوحة إدارة Dua Space.\n\n"
            "اختاري العملية المطلوبة:",
            reply_markup=admin_keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            get_setting("welcome_msg", DEFAULT_WELCOME),
            reply_markup=main_menu_keyboard(),
        )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if is_admin_user(update.effective_user.id):
        text = (
            "🛠️ أوامر الإدارة:\n\n"
            "/admin — لوحة الإدارة\n"
            "/publish النص — نشر نص في القناة\n"
            "/pin النص — نشر النص وتثبيته\n"
            "/stats — الإحصائيات\n"
            "/set_welcome النص — تعديل الترحيب\n"
            "/set_footer النص — تعديل توقيع المنشورات\n"
            "/cancel — إلغاء العملية الحالية\n\n"
            "لنشر صورة أو ملف، أرسليه للبوت مباشرة "
            "خارج خطوات إدخال بيانات الخدمات والطلبات."
        )
    else:
        text = (
            "أهلًا بك في Dua Space 🪐\n"
            "استخدمي الأزرار لتصفح الخدمات أو التواصل معنا."
        )

    await update.effective_message.reply_text(text)


async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin_user(update.effective_user.id):
        await update.effective_message.reply_text(
            "هذا الأمر مخصص للإدارة فقط."
        )
        return

    context.user_data.pop("flow", None)

    await update.effective_message.reply_text(
        "🎛️ لوحة إدارة Dua Space:",
        reply_markup=admin_keyboard(),
    )


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.pop("flow", None)
    context.user_data.pop("pending_service", None)

    await update.effective_message.reply_text(
        "تم إلغاء الخطوة الحالية.\n"
        "أرسلي /start للعودة للقائمة."
    )


# -------------------- استقبال طلبات العملاء --------------------

async def start_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    service_id: int,
):
    service = db_one(
        "SELECT * FROM services WHERE id = ? AND active = 1",
        (service_id,),
    )

    if not service:
        await update.callback_query.message.reply_text(
            "عذرًا، الخدمة غير متاحة حاليًا."
        )
        return

    context.user_data["flow"] = {
        "kind": "order_details",
        "service_id": service_id,
    }

    await update.callback_query.message.reply_text(
        f"📝 اخترتِ خدمة: {service['title']}\n\n"
        "اكتبي تفاصيل طلبك في رسالة واحدة، مثل المطلوب "
        "والألوان والمقاس وموعد التسليم.\n\n"
        "لإلغاء العملية اكتبي /cancel."
    )


async def handle_order_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    flow,
):
    details = (update.effective_message.text or "").strip()

    if not details:
        await update.effective_message.reply_text(
            "أرسلي تفاصيل الطلب كنص، أو اكتبي /cancel للإلغاء."
        )
        return

    service = db_one(
        "SELECT * FROM services WHERE id = ? AND active = 1",
        (flow["service_id"],),
    )

    if not service:
        context.user_data.pop("flow", None)

        await update.effective_message.reply_text(
            "عذرًا، الخدمة لم تعد متاحة. "
            "افتحي /start واختاري خدمة أخرى."
        )
        return

    user = update.effective_user
    save_user(user)

    order_id = db_execute(
        """
        INSERT INTO orders(
            user_id, username, service_id, service_title,
            price, details, status
        )
        VALUES(?, ?, ?, ?, ?, ?, 'جديد')
        """,
        (
            user.id,
            user.username or "",
            service["id"],
            service["title"],
            service["price"],
            details,
        ),
    )

    context.user_data.pop("flow", None)

    await update.effective_message.reply_text(
        f"✅ استلمنا طلبك رقم #{order_id}.\n"
        "سنراجع التفاصيل ونتواصل معك بشأن التنفيذ والدفع.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "💳 التواصل بشأن الدفع والطلب",
                        url=CONTACT_URL,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🛍️ العودة للخدمات",
                        callback_data="services",
                    )
                ],
            ]
        ),
    )

    username_text = (
        f"@{user.username}"
        if user.username
        else "بدون اسم مستخدم"
    )

    admin_text = (
        f"📥 طلب جديد #{order_id}\n\n"
        f"الخدمة: {service['title']}\n"
        f"السعر: {service['price']}\n"
        f"العميل: {user.first_name or 'بدون اسم'} "
        f"({username_text})\n"
        f"معرّف العميل: {user.id}\n\n"
        f"التفاصيل:\n{details[:2500]}"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "فتح الطلب وإدارته",
                            callback_data=f"orderadmin:{order_id}",
                        )
                    ]
                ]
            ),
        )
    except Exception:
        logger.exception(
            "Unable to notify admin about order %s",
            order_id,
        )


# -------------------- إدارة الخدمات --------------------

async def ask_add_service(query, context):
    context.user_data["pending_service"] = {}
    context.user_data["flow"] = {"kind": "add_title"}

    await query.message.reply_text(
        "اكتبي اسم الخدمة الجديدة.\n"
        "اكتبي /cancel للإلغاء."
    )


async def show_admin_service(query, service_id):
    service = db_one(
        "SELECT * FROM services WHERE id = ?",
        (service_id,),
    )

    if not service:
        await query.message.reply_text(
            "الخدمة غير موجودة.",
            reply_markup=admin_services_keyboard(),
        )
        return

    status = "مفعّلة ✅" if service["active"] else "موقوفة ⏸️"

    text = (
        f"🛍️ الخدمة رقم #{service['id']}\n\n"
        f"الاسم: {service['title']}\n"
        f"الوصف: {service['description'] or 'لا يوجد وصف'}\n"
        f"السعر: {service['price']}\n"
        f"الحالة: {status}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ تعديل الاسم",
                    callback_data=f"svcedit_title:{service_id}",
                ),
                InlineKeyboardButton(
                    "✏️ تعديل الوصف",
                    callback_data=f"svcedit_desc:{service_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💰 تعديل السعر",
                    callback_data=f"svcedit_price:{service_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⏯️ تفعيل/إيقاف",
                    callback_data=f"svctoggle:{service_id}",
                ),
                InlineKeyboardButton(
                    "🗑️ حذف",
                    callback_data=f"svcdeleteask:{service_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ قائمة الخدمات",
                    callback_data="admin_services",
                )
            ],
        ]
    )

    await query.message.reply_text(
        text,
        reply_markup=keyboard,
    )


# -------------------- الإحصائيات والطلبات --------------------

async def send_stats(target, context):
    users_count = db_one(
        "SELECT COUNT(*) AS n FROM users"
    )["n"]

    total_orders = db_one(
        "SELECT COUNT(*) AS n FROM orders"
    )["n"]

    new_orders = db_one(
        "SELECT COUNT(*) AS n FROM orders WHERE status = 'جديد'"
    )["n"]

    active_services = db_one(
        "SELECT COUNT(*) AS n FROM services WHERE active = 1"
    )["n"]

    try:
        chat = await context.bot.get_chat(CHANNEL_ID)
        members = await context.bot.get_chat_member_count(CHANNEL_ID)

        channel_text = (
            f"اسم القناة: {chat.title}\n"
            f"عدد مشتركي القناة: {members}"
        )

    except Exception as exc:
        logger.warning(
            "Could not read channel stats: %s",
            exc,
        )
        channel_text = (
            "تعذر قراءة عدد مشتركي القناة. "
            "تحققي من CHANNEL_ID وصلاحيات البوت."
        )

    text = (
        "📊 إحصائيات Dua Space\n\n"
        f"مستخدمو البوت المسجلون: {users_count}\n"
        f"إجمالي الطلبات: {total_orders}\n"
        f"الطلبات الجديدة: {new_orders}\n"
        f"الخدمات المفعلة: {active_services}\n\n"
        f"{channel_text}"
    )

    await target.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅️ لوحة الإدارة",
                        callback_data="admin_home",
                    )
                ]
            ]
        ),
    )


async def show_orders(query):
    rows = db_all(
        """
        SELECT id, service_title, status, created_at
        FROM orders
        ORDER BY id DESC
        LIMIT 20
        """
    )

    if not rows:
        await query.message.reply_text(
            "ما في طلبات لحد الآن.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ لوحة الإدارة",
                            callback_data="admin_home",
                        )
                    ]
                ]
            ),
        )
        return

    buttons = []

    for row in rows:
        title = (
            f"#{row['id']} | {row['status']} | "
            f"{row['service_title']}"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    title[:60],
                    callback_data=f"orderadmin:{row['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "⬅️ لوحة الإدارة",
                callback_data="admin_home",
            )
        ]
    )

    await query.message.reply_text(
        "📥 آخر الطلبات:\n"
        "اضغطي على الطلب لعرض تفاصيله.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_admin_order(query, order_id):
    order = db_one(
        "SELECT * FROM orders WHERE id = ?",
        (order_id,),
    )

    if not order:
        await query.message.reply_text("الطلب غير موجود.")
        return

    username = (
        f"@{order['username']}"
        if order["username"]
        else "بدون اسم مستخدم"
    )

    text = (
        f"📥 الطلب #{order['id']}\n\n"
        f"الخدمة: {order['service_title']}\n"
        f"السعر المسجل: {order['price']}\n"
        f"العميل: {username}\n"
        f"معرّف العميل: {order['user_id']}\n"
        f"الحالة: {order['status']}\n"
        f"التاريخ: {order['created_at']}\n\n"
        f"التفاصيل:\n{order['details'][:2500]}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ قبول",
                    callback_data=f"ordstatus:{order_id}:accepted",
                ),
                InlineKeyboardButton(
                    "🛠️ قيد التنفيذ",
                    callback_data=f"ordstatus:{order_id}:working",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎉 مكتمل",
                    callback_data=f"ordstatus:{order_id}:done",
                ),
                InlineKeyboardButton(
                    "❌ رفض",
                    callback_data=f"ordstatus:{order_id}:rejected",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ كل الطلبات",
                    callback_data="admin_orders",
                )
            ],
        ]
    )

    await query.message.reply_text(
        text,
        reply_markup=keyboard,
    )


async def show_settings(query):
    welcome = get_setting(
        "welcome_msg",
        DEFAULT_WELCOME,
    )

    footer = get_setting(
        "footer",
        DEFAULT_FOOTER,
    )

    text = (
        "⚙️ إعدادات النصوص الحالية\n\n"
        f"رسالة الترحيب:\n{welcome[:1200]}\n\n"
        f"توقيع المنشورات:\n{footer[:500]}\n\n"
        "تُحفظ التعديلات في قاعدة البيانات المحلية."
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✏️ تعديل الترحيب",
                    callback_data="edit_welcome",
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ تعديل توقيع المنشورات",
                    callback_data="edit_footer",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ لوحة الإدارة",
                    callback_data="admin_home",
                )
            ],
        ]
    )

    await query.message.reply_text(
        text,
        reply_markup=keyboard,
    )


# -------------------- معالجة الأزرار --------------------

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    user_id = query.from_user.id
    admin = is_admin_user(user_id)

    if data == "home":
        await query.message.reply_text(
            get_setting("welcome_msg", DEFAULT_WELCOME),
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "show_customer_menu":
        if not admin:
            await query.message.reply_text(
                "هذا الزر مخصص للإدارة."
            )
            return

        await query.message.reply_text(
            get_setting("welcome_msg", DEFAULT_WELCOME),
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "services":
        keyboard, rows = services_keyboard(active_only=True)

        if not rows:
            await query.message.reply_text(
                "لا توجد خدمات متاحة حاليًا. "
                "تواصلي معنا للاستفسار.",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await query.message.reply_text(
                "🛍️ اختاري الخدمة التي تناسبك:",
                reply_markup=keyboard,
            )

        return

    if data.startswith("service:"):
        try:
            service_id = int(data.split(":", 1)[1])
        except ValueError:
            return

        service = db_one(
            "SELECT * FROM services WHERE id = ? AND active = 1",
            (service_id,),
        )

        if not service:
            await query.message.reply_text(
                "الخدمة غير متاحة حاليًا."
            )
            return

        text = (
            f"{service['title']}\n\n"
            f"{service['description'] or 'تواصلي معنا لمعرفة التفاصيل.'}"
            f"\n\nالسعر: {service['price']}"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📩 اطلب الخدمة",
                        callback_data=f"order:{service_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💳 استفسار عن الدفع",
                        url=CONTACT_URL,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ رجوع للخدمات",
                        callback_data="services",
                    )
                ],
            ]
        )

        await query.message.reply_text(
            text,
            reply_markup=keyboard,
        )
        return

    if data.startswith("order:"):
        try:
            service_id = int(data.split(":", 1)[1])
        except ValueError:
            return

        await start_order(update, context, service_id)
        return

    if not admin:
        await query.message.reply_text(
            "عذرًا، هذا الخيار مخصص لإدارة Dua Space."
        )
        return

    if data == "admin_home":
        context.user_data.pop("flow", None)

        await query.message.reply_text(
            "🎛️ لوحة إدارة Dua Space:",
            reply_markup=admin_keyboard(),
        )

    elif data == "admin_services":
        await query.message.reply_text(
            "🛍️ إدارة الخدمات:\n"
            "اختاري خدمة أو أضيفي خدمة جديدة.",
            reply_markup=admin_services_keyboard(),
        )

    elif data == "svc_add":
        await ask_add_service(query, context)

    elif data.startswith("svcadmin:"):
        await show_admin_service(
            query,
            int(data.split(":", 1)[1]),
        )

    elif data.startswith("svcedit_title:"):
        service_id = int(data.split(":", 1)[1])

        context.user_data["flow"] = {
            "kind": "edit_title",
            "service_id": service_id,
        }

        await query.message.reply_text(
            "اكتبي الاسم الجديد للخدمة. "
            "للإلغاء اكتبي /cancel."
        )

    elif data.startswith("svcedit_desc:"):
        service_id = int(data.split(":", 1)[1])

        context.user_data["flow"] = {
            "kind": "edit_desc",
            "service_id": service_id,
        }

        await query.message.reply_text(
            "اكتبي الوصف الجديد للخدمة. "
            "للإلغاء اكتبي /cancel."
        )

    elif data.startswith("svcedit_price:"):
        service_id = int(data.split(":", 1)[1])

        context.user_data["flow"] = {
            "kind": "edit_price",
            "service_id": service_id,
        }

        await query.message.reply_text(
            "اكتبي السعر الجديد أو عبارة مثل: حسب الطلب. "
            "للإلغاء اكتبي /cancel."
        )

    elif data.startswith("svctoggle:"):
        service_id = int(data.split(":", 1)[1])

        row = db_one(
            "SELECT active FROM services WHERE id = ?",
            (service_id,),
        )

        if row:
            new_active = 0 if row["active"] else 1

            db_execute(
                "UPDATE services SET active = ? WHERE id = ?",
                (new_active, service_id),
            )

        await show_admin_service(query, service_id)

    elif data.startswith("svcdeleteask:"):
        service_id = int(data.split(":", 1)[1])

        await query.message.reply_text(
            "هل أنتِ متأكدة من حذف الخدمة؟ "
            "الطلبات القديمة ستظل محفوظة.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "نعم، احذفيها",
                            callback_data=f"svcdelete:{service_id}",
                        ),
                        InlineKeyboardButton(
                            "إلغاء",
                            callback_data=f"svcadmin:{service_id}",
                        ),
                    ]
                ]
            ),
        )

    elif data.startswith("svcdelete:"):
        service_id = int(data.split(":", 1)[1])

        db_execute(
            "DELETE FROM services WHERE id = ?",
            (service_id,),
        )

        await query.message.reply_text(
            "تم حذف الخدمة.",
            reply_markup=admin_services_keyboard(),
        )

    elif data == "admin_orders":
        await show_orders(query)

    elif data.startswith("orderadmin:"):
        await show_admin_order(
            query,
            int(data.split(":", 1)[1]),
        )

    elif data.startswith("ordstatus:"):
        _, raw_id, status_key = data.split(":", 2)
        order_id = int(raw_id)

        status_map = {
            "accepted": "مقبول",
            "working": "قيد التنفيذ",
            "done": "مكتمل",
            "rejected": "مرفوض",
        }

        new_status = status_map.get(status_key)

        if not new_status:
            return

        row = db_one(
            "SELECT user_id, service_title FROM orders WHERE id = ?",
            (order_id,),
        )

        if row:
            db_execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (new_status, order_id),
            )

            try:
                await context.bot.send_message(
                    chat_id=row["user_id"],
                    text=(
                        f"تحديث على طلبك #{order_id} "
                        f"لخدمة {row['service_title']}: "
                        f"الحالة الجديدة هي «{new_status}»."
                    ),
                )
            except Exception:
                logger.info(
                    "Could not notify user for order %s",
                    order_id,
                )

            await query.message.reply_text(
                f"✅ تم تحديث حالة الطلب #{order_id} "
                f"إلى: {new_status}"
            )

            await show_admin_order(query, order_id)

    elif data == "admin_stats":
        await send_stats(query.message, context)

    elif data == "admin_settings":
        await show_settings(query)

    elif data == "edit_welcome":
        context.user_data["flow"] = {
            "kind": "edit_welcome",
        }

        await query.message.reply_text(
            "أرسلي رسالة الترحيب الجديدة. "
            "للإلغاء اكتبي /cancel."
        )

    elif data == "edit_footer":
        context.user_data["flow"] = {
            "kind": "edit_footer",
        }

        await query.message.reply_text(
            "أرسلي توقيع المنشورات الجديد. "
            "لإلغاء التوقيع أرسلي شرطة واحدة: -"
        )

    elif data == "publish_help":
        await query.message.reply_text(
            "📢 للنشر في القناة اكتبي الأمر مع النص، مثل:\n\n"
            "/publish أهلًا بكم في Dua Space ✦\n\n"
            "للنشر والتثبيت استخدمي /pin ثم النص.\n"
            "لنشر صورة أو ملف، أرسليه للبوت مباشرة "
            "خارج خطوات إدخال بيانات الخدمات والطلبات."
        )


# -------------------- معالجة النصوص --------------------

async def text_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    if not message or not message.text:
        return

    flow = context.user_data.get("flow")

    if flow and flow.get("kind") == "order_details":
        await handle_order_text(update, context, flow)
        return

    if is_admin_user(user.id) and flow:
        kind = flow.get("kind")
        value = message.text.strip()

        if kind == "add_title":
            context.user_data.setdefault(
                "pending_service", {}
            )["title"] = value

            context.user_data["flow"] = {
                "kind": "add_desc",
            }

            await message.reply_text(
                "اكتبي وصف الخدمة باختصار. "
                "لو ما في وصف اكتبي -."
            )

        elif kind == "add_desc":
            context.user_data.setdefault(
                "pending_service", {}
            )["description"] = (
                "" if value == "-" else value
            )

            context.user_data["flow"] = {
                "kind": "add_price",
            }

            await message.reply_text(
                "اكتبي السعر أو عبارة مثل: حسب تفاصيل الطلب."
            )

        elif kind == "add_price":
            pending = context.user_data.get(
                "pending_service", {}
            )

            if not pending.get("title"):
                context.user_data.pop("flow", None)
                context.user_data.pop("pending_service", None)

                await message.reply_text(
                    "ما لقيت اسم الخدمة. "
                    "ابدئي من جديد عبر /admin."
                )
                return

            db_execute(
                """
                INSERT INTO services(title, description, price, active)
                VALUES(?, ?, ?, 1)
                """,
                (
                    pending["title"],
                    pending.get("description", ""),
                    value or "حسب الطلب",
                ),
            )

            context.user_data.pop("flow", None)
            context.user_data.pop("pending_service", None)

            await message.reply_text(
                "✅ تمت إضافة الخدمة وحفظها.",
                reply_markup=admin_services_keyboard(),
            )

        elif kind in (
            "edit_title",
            "edit_desc",
            "edit_price",
        ):
            service_id = flow.get("service_id")

            column = {
                "edit_title": "title",
                "edit_desc": "description",
                "edit_price": "price",
            }[kind]

            db_execute(
                f"UPDATE services SET {column} = ? WHERE id = ?",
                (value, service_id),
            )

            context.user_data.pop("flow", None)

            await message.reply_text(
                "✅ تم حفظ التعديل.",
                reply_markup=admin_services_keyboard(),
            )

        elif kind == "edit_welcome":
            set_setting("welcome_msg", value)
            context.user_data.pop("flow", None)

            await message.reply_text(
                "✅ تم حفظ رسالة الترحيب.",
                reply_markup=admin_keyboard(),
            )

        elif kind == "edit_footer":
            set_setting(
                "footer",
                "" if value == "-" else "\n\n" + value,
            )

            context.user_data.pop("flow", None)

            await message.reply_text(
                "✅ تم حفظ توقيع المنشورات.",
                reply_markup=admin_keyboard(),
            )

        return

    if is_admin_user(user.id):
        await message.reply_text(
            "لم أنشر هذه الرسالة لأن النشر النصي يحتاج الأمر /publish.\n"
            "اكتبي /admin لفتح لوحة الإدارة، "
            "أو /cancel لإلغاء أي خطوة معلقة."
        )


# -------------------- النشر في القناة --------------------

def add_footer(text):
    footer = get_setting(
        "footer",
        DEFAULT_FOOTER,
    )

    return f"{text}{footer}" if footer else text


async def publish(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin_user(update.effective_user.id):
        return

    text = " ".join(context.args).strip()

    if not text:
        await update.effective_message.reply_text(
            "اكتبي النص بعد الأمر، مثل:\n"
            "/publish أهلًا بكم في Dua Space"
        )
        return

    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=add_footer(text),
        )

        await update.effective_message.reply_text(
            "✅ تم نشر المنشور في القناة."
        )

    except Exception as exc:
        logger.exception("Publishing failed")

        await update.effective_message.reply_text(
            "❌ تعذر النشر. راجعي صلاحيات البوت ومعرّف القناة.\n"
            f"التفاصيل: {str(exc)[:500]}"
        )


async def post_pin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin_user(update.effective_user.id):
        return

    text = " ".join(context.args).strip()

    if not text:
        await update.effective_message.reply_text(
            "اكتبي النص بعد الأمر، مثل:\n/pin إعلان مهم"
        )
        return

    try:
        sent = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=add_footer(text),
        )

        await context.bot.pin_chat_message(
            chat_id=CHANNEL_ID,
            message_id=sent.message_id,
        )

        await update.effective_message.reply_text(
            "📌 تم نشر الرسالة وتثبيتها في القناة."
        )

    except Exception as exc:
        logger.exception("Pinning post failed")

        await update.effective_message.reply_text(
            "❌ تعذر النشر أو التثبيت.\n"
            f"التفاصيل: {str(exc)[:500]}"
        )


async def set_welcome_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin_user(update.effective_user.id):
        return

    value = " ".join(context.args).strip()

    if not value:
        await update.effective_message.reply_text(
            "اكتبي النص الجديد بعد الأمر /set_welcome"
        )
        return

    set_setting("welcome_msg", value)

    await update.effective_message.reply_text(
        "✅ تم حفظ رسالة الترحيب."
    )


async def set_footer_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin_user(update.effective_user.id):
        return

    value = " ".join(context.args).strip()

    if not value:
        await update.effective_message.reply_text(
            "اكتبي التوقيع بعد /set_footer، "
            "أو اكتبي /set_footer - لإلغاء التوقيع."
        )
        return

    set_setting(
        "footer",
        "" if value == "-" else "\n\n" + value,
    )

    await update.effective_message.reply_text(
        "✅ تم حفظ توقيع المنشورات."
    )


async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin_user(update.effective_user.id):
        return

    await send_stats(update.effective_message, context)


# -------------------- نشر الصور والملفات --------------------

async def media_forwarder(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin_user(update.effective_user.id):
        return

    if context.user_data.get("flow"):
        await update.effective_message.reply_text(
            "أكملي الخطوة الحالية أولًا، أو اكتبي /cancel.\n"
            "لم أنشر الملف لتجنب نشره بالخطأ."
        )
        return

    try:
        await context.bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
        )

        await update.effective_message.reply_text(
            "✅ تم نشر الوسيط في القناة."
        )

    except Exception as exc:
        logger.exception("Media publishing failed")

        await update.effective_message.reply_text(
            "❌ تعذر نشر الملف. تأكدي من صلاحيات البوت.\n"
            f"التفاصيل: {str(exc)[:500]}"
        )


# -------------------- خادم الويب الخاص بـ Render --------------------

async def handle_health(request):
    return web.Response(
        text="Dua Space bot is running.",
        status=200,
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Unhandled bot error: %s",
        context.error,
        exc_info=context.error,
    )


# -------------------- تشغيل البوت --------------------

async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "متغير BOT_TOKEN غير موجود في إعدادات Render."
        )

    if not CHANNEL_ID:
        raise RuntimeError(
            "متغير CHANNEL_ID غير موجود في إعدادات Render."
        )

    if not ADMIN_ID:
        raise RuntimeError(
            "متغير ADMIN_ID غير موجود أو ليس رقم Telegram ID الصحيح."
        )

    init_db()

    web_app = web.Application()

    web_app.router.add_get("/", handle_health)
    web_app.router.add_get("/health", handle_health)

    runner = web.AppRunner(web_app)
    await runner.setup()

    port = int(os.environ.get("PORT", "10000"))

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port,
    )

    await site.start()

    logger.info(
        "Health web server listening on port %s",
        port,
    )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("admin", admin_panel)
    )

    application.add_handler(
        CommandHandler("cancel", cancel)
    )

    application.add_handler(
        CommandHandler("publish", publish)
    )

    application.add_handler(
        CommandHandler("pin", post_pin)
    )

    application.add_handler(
        CommandHandler("set_welcome", set_welcome_command)
    )

    application.add_handler(
        CommandHandler("set_footer", set_footer_command)
    )

    application.add_handler(
        CommandHandler("stats", stats_command)
    )

    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_router,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.ATTACHMENT,
            media_forwarder,
        )
    )

    application.add_error_handler(error_handler)

    initialized = False

    try:
        await application.initialize()
        initialized = True

        await application.start()

        if application.updater is None:
            raise RuntimeError(
                "Telegram updater غير متاح. "
                "تحققي من إعدادات المكتبة."
            )

        await application.updater.start_polling(
            drop_pending_updates=False
        )

        logger.info(
            "Dua Space bot is polling and ready."
        )

        await asyncio.Event().wait()

    finally:
        try:
            if (
                application.updater
                and application.updater.running
            ):
                await application.updater.stop()

            if application.running:
                await application.stop()

            if initialized:
                await application.shutdown()

        finally:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
