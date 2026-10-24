# -*- coding: utf-8 -*-
# Dua Space Bot
# Python 3.11+
# python-telegram-bot 21.10

import os
import json
import time
import sqlite3
import logging
import random
import asyncio
from datetime import datetime, timezone, timedelta
from functools import wraps

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================================================
# 1. الإعدادات الأساسية
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@DuaSpace1").strip()
CHANNEL_URL = "https://t.me/DuaSpace1"

BOT_NAME = "Dua Space"
DATABASE_PATH = os.getenv("DATABASE_PATH", "dua_space.db")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("DuaSpace")


# ==================================================
# 2. قاعدة البيانات
# ==================================================

def db_connect():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database():
    with db_connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            joined_at TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            is_banned INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            position INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            url TEXT DEFAULT '',
            file_id TEXT DEFAULT '',
            added_at TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY(category_id)
                REFERENCES categories(category_id)
                ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            details TEXT DEFAULT '',
            status TEXT DEFAULT 'جديد',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'مفتوح',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scheduled_posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            post_type TEXT DEFAULT 'نص',
            enabled INTEGER DEFAULT 1,
            sent_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blocked_words (
            word_id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quiz_scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS group_settings (
            chat_id INTEGER PRIMARY KEY,
            moderation_enabled INTEGER DEFAULT 0,
            links_blocked INTEGER DEFAULT 0,
            bad_words_blocked INTEGER DEFAULT 0,
            warning_limit INTEGER DEFAULT 3
        );
        """)

        defaults = {
            "maintenance": "0",
            "force_subscription": "1",
            "welcome_text": (
                "أهلًا بك في Dua Space 🌙\n\n"
                "مساحتك للمعرفة والقراءة والتعلّم."
            ),
            "auto_posts_enabled": "0",
            "auto_posts_interval_hours": "12",
            "support_username": "",
            "admin_ids": json.dumps([]),
            "daily_quiz_enabled": "1",
        }

        for key, value in defaults.items():
            db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        default_categories = [
            ("إسلاميات", "القرآن والتفسير والسيرة والحديث والأذكار"),
            ("قصص وروايات", "قصص وروايات عربية وعالمية ومترجمة"),
            ("تعلّم اللغات", "الإنجليزية والفرنسية وغيرها"),
            ("الطب والصحة", "كتب ومراجع في الطب والعلوم الصحية"),
            ("العلوم", "العلوم الطبيعية والمعرفة العلمية"),
            ("الهندسة والتقنية", "الهندسة والبرمجة والتكنولوجيا"),
            ("علم النفس", "علم النفس وتطوير الذات"),
            ("فلسفة وتاريخ", "الفلسفة والتاريخ والجغرافيا"),
            ("أدب وشعر", "الأدب والشعر والكتابات الثقافية"),
            ("تصميم وأعمال", "التصميم والإدارة وريادة الأعمال"),
            ("كتب الأطفال", "قصص وكتب مناسبة للأطفال"),
        ]

        for position, (name, description) in enumerate(default_categories):
            db.execute("""
                INSERT INTO categories
                    (name, description, position)
                SELECT ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM categories WHERE name = ?
                )
            """, (name, description, position, name))


def get_setting(key, default=""):
    with db_connect() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()

    return row["value"] if row else default


def set_setting(key, value):
    with db_connect() as db:
        db.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))


def now_text():
    return datetime.now(timezone.utc).isoformat()


# ==================================================
# 3. صلاحيات الإدارة
# ==================================================

def is_owner(user_id):
    return ADMIN_ID != 0 and user_id == ADMIN_ID


def is_admin(user_id):
    if is_owner(user_id):
        return True

    try:
        admin_ids = json.loads(get_setting("admin_ids", "[]"))
        return user_id in admin_ids
    except (ValueError, TypeError):
        return False


def admin_only(func):
    @wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs,
    ):
        user = update.effective_user

        if not user or not is_admin(user.id):
            if update.callback_query:
                await update.callback_query.answer(
                    "هذا القسم للإدارة فقط.",
                    show_alert=True,
                )
            elif update.effective_message:
                await update.effective_message.reply_text(
                    "عذرًا، هذا الأمر متاح للإدارة فقط."
                )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# ==================================================
# 4. تسجيل المستخدمين والإحصائيات
# ==================================================

def register_user(user):
    current_time = now_text()

    with db_connect() as db:
        existing = db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user.id,),
        ).fetchone()

        if existing:
            db.execute("""
                UPDATE users
                SET username = ?, full_name = ?, last_seen = ?
                WHERE user_id = ?
            """, (
                user.username or "",
                user.full_name or "",
                current_time,
                user.id,
            ))
            return False

        db.execute("""
            INSERT INTO users (
                user_id, username, full_name,
                joined_at, last_seen
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.full_name or "",
            current_time,
            current_time,
        ))

        return True


def get_statistics():
    with db_connect() as db:
        total_users = db.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        today = datetime.now(timezone.utc).date().isoformat()

        new_today = db.execute("""
            SELECT COUNT(*) FROM users
            WHERE substr(joined_at, 1, 10) = ?
        """, (today,)).fetchone()[0]

        total_books = db.execute(
            "SELECT COUNT(*) FROM books WHERE enabled = 1"
        ).fetchone()[0]

        total_categories = db.execute(
            "SELECT COUNT(*) FROM categories WHERE enabled = 1"
        ).fetchone()[0]

        open_tickets = db.execute("""
            SELECT COUNT(*) FROM tickets
            WHERE status = 'مفتوح'
        """).fetchone()[0]

    return {
        "users": total_users,
        "new_today": new_today,
        "books": total_books,
        "categories": total_categories,
        "open_tickets": open_tickets,
    }


# ==================================================
# نهاية الجزء الأول
# لا تشغّلي الملف حتى نكمل بقية الأجزاء.
# ===========================================
# ==================================================
# الجزء الثاني: الاشتراك والقوائم والمكتبة والتسبيح
# ==================================================

# ---------- الاشتراك الإجباري ----------

async def check_subscription(
    user_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if get_setting("force_subscription", "1") != "1":
        return True

    if is_owner(user_id):
        return True

    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id,
        )

        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )

    except TelegramError:
        logger.exception("Subscription check failed")
        return False


def subscription_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 الاشتراك في القناة",
                url=CHANNEL_URL,
            )
        ],
        [
            InlineKeyboardButton(
                "✅ تحقّق من الاشتراك",
                callback_data="check_subscription",
            )
        ],
    ])


# ---------- القوائم ----------

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📚 المكتبة", "📖 أقسام المعرفة"],
            ["📿 التسبيح والأذكار", "🧠 الاختبارات"],
            ["⏱️ المؤقت الدراسي", "🎨 خدمات التصميم"],
            ["🆘 الدعم والمساعدة"],
        ],
        resize_keyboard=True,
    )


def inline_main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📚 المكتبة",
                callback_data="menu:library",
            ),
            InlineKeyboardButton(
                "📖 المعرفة",
                callback_data="menu:knowledge",
            ),
        ],
        [
            InlineKeyboardButton(
                "📿 التسبيح",
                callback_data="menu:tasbeeh",
            ),
            InlineKeyboardButton(
                "🧠 الاختبارات",
                callback_data="menu:quiz",
            ),
        ],
        [
            InlineKeyboardButton(
                "🎨 خدمات التصميم",
                callback_data="menu:design",
            ),
            InlineKeyboardButton(
                "🆘 الدعم",
                callback_data="menu:support",
            ),
        ],
    ])


# ---------- أمر البداية ----------

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    is_new = register_user(user)

    if is_new and ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "👤 مستخدم جديد في Dua Space\n\n"
                    f"الاسم: {user.full_name}\n"
                    f"المعرف: {user.id}\n"
                    f"اسم المستخدم: @{user.username or 'غير موجود'}\n"
                    f"إجمالي المستخدمين: {get_statistics()['users']}"
                ),
            )
        except TelegramError:
            logger.exception("Could not notify owner")

    if get_setting("maintenance", "0") == "1" and not is_admin(user.id):
        await message.reply_text(
            "🛠️ البوت تحت الصيانة حاليًا. حاولي لاحقًا."
        )
        return

    if not await check_subscription(user.id, context):
        await message.reply_text(
            "أهلًا بك في Dua Space 🌙\n\n"
            "للاستفادة من خدمات البوت، اشتركي في القناة أولًا، "
            "ثم اضغطي على زر التحقق.",
            reply_markup=subscription_keyboard(),
        )
        return

    welcome = get_setting(
        "welcome_text",
        "أهلًا بك في Dua Space 🌙",
    )

    await message.reply_text(
        welcome,
        reply_markup=main_menu_keyboard(),
    )

    await message.reply_text(
        "اختاري القسم الذي تريدينه:",
        reply_markup=inline_main_menu(),
    )


# ---------- الأقسام ----------

async def show_categories(
    query,
    context: ContextTypes.DEFAULT_TYPE,
):
    with db_connect() as db:
        rows = db.execute("""
            SELECT category_id, name, description
            FROM categories
            WHERE enabled = 1
            ORDER BY position, name
        """).fetchall()

    buttons = []

    for row in rows:
        buttons.append([
            InlineKeyboardButton(
                row["name"],
                callback_data=f"category:{row['category_id']}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ القائمة الرئيسية",
            callback_data="menu:home",
        )
    ])

    await query.edit_message_text(
        "📚 مكتبة Dua Space\n\nاختاري القسم المطلوب:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------- عرض الكتب ----------

async def show_books(
    query,
    category_id: int,
    context: ContextTypes.DEFAULT_TYPE,
):
    with db_connect() as db:
        category = db.execute("""
            SELECT name FROM categories
            WHERE category_id = ? AND enabled = 1
        """, (category_id,)).fetchone()

        books = db.execute("""
            SELECT book_id, title, description, url
            FROM books
            WHERE category_id = ? AND enabled = 1
            ORDER BY book_id DESC
        """, (category_id,)).fetchall()

    if not category:
        await query.edit_message_text(
            "هذا القسم غير موجود أو غير متاح."
        )
        return

    buttons = []

    for book in books:
        buttons.append([
            InlineKeyboardButton(
                f"📖 {book['title']}",
                callback_data=f"book:{book['book_id']}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ الأقسام",
            callback_data="menu:library",
        )
    ])

    text = f"📚 {category['name']}\n\n"

    if not books:
        text += "لا توجد كتب مضافة في هذا القسم حاليًا."
    else:
        text += "اختاري كتابًا لعرض تفاصيله."

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_book_details(
    query,
    book_id: int,
    context: ContextTypes.DEFAULT_TYPE,
):
    with db_connect() as db:
        book = db.execute("""
            SELECT title, description, url, file_id
            FROM books
            WHERE book_id = ? AND enabled = 1
        """, (book_id,)).fetchone()

    if not book:
        await query.edit_message_text("الكتاب غير موجود.")
        return

    text = f"📖 {book['title']}\n\n"

    if book["description"]:
        text += f"{book['description']}\n\n"

    buttons = []

    if book["url"]:
        buttons.append([
            InlineKeyboardButton(
                "📥 فتح الكتاب أو الرابط",
                url=book["url"],
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ رجوع للأقسام",
            callback_data="menu:library",
        )
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    # إذا كان الكتاب ملفًا مرفوعًا إلى تيليجرام، نرسله للمستخدم.
    if book["file_id"]:
        try:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=book["file_id"],
                caption=book["title"],
            )
        except TelegramError:
            logger.exception("Could not send book file")


# ---------- التسبيح ----------

def tasbeeh_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📿 سبّحت",
                callback_data="tasbeeh:count",
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 تصفير العداد",
                callback_data="tasbeeh:reset",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ القائمة الرئيسية",
                callback_data="menu:home",
            )
        ],
    ])


async def open_tasbeeh(
    query,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["tasbeeh_count"] = context.user_data.get(
        "tasbeeh_count", 0
    )

    await query.edit_message_text(
        "📿 التسبيح الإلكتروني\n\n"
        "سبحان الله وبحمده\n\n"
        f"العدد الحالي: {context.user_data['tasbeeh_count']}",
        reply_markup=tasbeeh_keyboard(),
    )


# ---------- التعامل مع أزرار القوائم ----------

async def menu_callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "check_subscription":
        if await check_subscription(user_id, context):
            await query.edit_message_text(
                "✅ تم التحقق من اشتراكك.\n"
                "ارجعي إلى البوت واضغطي /start."
            )
        else:
            await query.answer(
                "لم يتم التأكد من الاشتراك. اشتركي أولًا ثم أعيدي المحاولة.",
                show_alert=True,
            )
        return

    if not is_admin(user_id):
        if get_setting("maintenance", "0") == "1":
            await query.answer(
                "البوت تحت الصيانة.",
                show_alert=True,
            )
            return

        if not await check_subscription(user_id, context):
            await query.answer(
                "اشتركي في القناة أولًا.",
                show_alert=True,
            )
            try:
                await query.message.reply_text(
                    "للاستفادة من البوت، اشتركي أولًا:",
                    reply_markup=subscription_keyboard(),
                )
            except TelegramError:
                pass
            return

    data = query.data

    if data == "menu:home":
        await query.edit_message_text(
            "🌙 Dua Space\n\nاختاري القسم:",
            reply_markup=inline_main_menu(),
        )

    elif data in ("menu:library", "menu:knowledge"):
        await show_categories(query, context)

    elif data == "menu:tasbeeh":
        await open_tasbeeh(query, context)

    elif data == "tasbeeh:count":
        count = context.user_data.get("tasbeeh_count", 0) + 1
        context.user_data["tasbeeh_count"] = count

        await query.edit_message_text(
            "📿 سبحان الله وبحمده\n\n"
            f"العدد الحالي: {count}",
            reply_markup=tasbeeh_keyboard(),
        )

    elif data == "tasbeeh:reset":
        context.user_data["tasbeeh_count"] = 0
        await open_tasbeeh(query, context)

    elif data.startswith("category:"):
        try:
            category_id = int(data.split(":", 1)[1])
            await show_books(query, category_id, context)
        except (ValueError, IndexError):
            await query.edit_message_text("تعذر فتح القسم.")

    elif data.startswith("book:"):
        try:
            book_id = int(data.split(":", 1)[1])
            await show_book_details(query, book_id, context)
        except (ValueError, IndexError):
            await query.edit_message_text("تعذر فتح الكتاب.")

    elif data == "menu:quiz":
        await query.edit_message_text(
            "🧠 قسم الاختبارات\n\n"
            "سيتم تفعيل الاختبارات في الجزء الخاص بها.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "⬅️ القائمة الرئيسية",
                    callback_data="menu:home",
                )
            ]]),
        )

    elif data == "menu:design":
        await query.edit_message_text(
            "🎨 خدمات التصميم\n\n"
            "لإرسال طلب تصميم، اختاري «خدمات التصميم» "
            "من القائمة الرئيسية واكتبي تفاصيل طلبك.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "⬅️ القائمة الرئيسية",
                    callback_data="menu:home",
                )
            ]]),
        )

    elif data == "menu:support":
        await query.edit_message_text(
            "🆘 للدعم، أرسلي رسالتك إلى البوت "
            "وسنجهز استقبال التذاكر في الجزء التالي.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "⬅️ القائمة الرئيسية",
                    callback_data="menu:home",
                )
            ]]),
        )


# ==================================================
# نهاية الجزء الثاني
# ==================================================
# =========================
# الجزء الثالث: لوحة الإدارة
# =========================

def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 إدارة المكتبة", callback_data="admin:library")],
        [InlineKeyboardButton("➕ إضافة قسم", callback_data="admin:add_category"),
         InlineKeyboardButton("➕ إضافة كتاب", callback_data="admin:add_book")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats"),
         InlineKeyboardButton("👥 المستخدمون", callback_data="admin:users")],
        [InlineKeyboardButton("📢 إذاعة رسالة", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin:settings")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="menu:home")]
    ])


@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🛠️ لوحة تحكم Dua Space\n\nاختاري العملية المطلوبة:",
        reply_markup=admin_panel_keyboard()
    )


@admin_only
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin:home":
        await query.edit_message_text(
            "🛠️ لوحة التحكم",
            reply_markup=admin_panel_keyboard()
        )

    elif data == "admin:library":
        conn = db_connect()
        rows = conn.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall()
        conn.close()

        buttons = [
            [InlineKeyboardButton(
                f"📂 {row['name']}",
                callback_data=f"admin:cat:{row['id']}"
            )]
            for row in rows
        ]
        buttons.append([
            InlineKeyboardButton("➕ إضافة قسم", callback_data="admin:add_category")
        ])
        buttons.append([
            InlineKeyboardButton("↩️ رجوع", callback_data="admin:home")
        ])

        await query.edit_message_text(
            "📚 أقسام المكتبة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("admin:cat:"):
        category_id = int(data.split(":")[2])
        conn = db_connect()
        category = conn.execute(
            "SELECT id, name FROM categories WHERE id=?",
            (category_id,)
        ).fetchone()
        books = conn.execute(
            "SELECT id, title FROM books WHERE category_id=? ORDER BY title",
            (category_id,)
        ).fetchall()
        conn.close()

        if not category:
            await query.edit_message_text("القسم غير موجود.")
            return

        context.user_data["admin_category_id"] = category_id

        buttons = [
            [InlineKeyboardButton(
                f"📖 {book['title']}",
                callback_data=f"admin:book:{book['id']}"
            )]
            for book in books
        ]
        buttons.extend([
            [InlineKeyboardButton("➕ إضافة كتاب هنا", callback_data="admin:add_book")],
            [InlineKeyboardButton("✏️ إعادة تسمية القسم", callback_data="admin:rename_category")],
            [InlineKeyboardButton("🗑️ حذف القسم", callback_data="admin:delete_category")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="admin:library")]
        ])

        await query.edit_message_text(
            f"📂 القسم: {category['name']}\nعدد الكتب: {len(books)}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "admin:add_category":
        context.user_data["admin_action"] = "add_category"
        await query.edit_message_text(
            "أرسلي اسم القسم الجديد.\n\nللإلغاء أرسلي /cancel"
        )

    elif data == "admin:add_book":
        category_id = context.user_data.get("admin_category_id")
        if not category_id:
            conn = db_connect()
            row = conn.execute(
                "SELECT id FROM categories ORDER BY id LIMIT 1"
            ).fetchone()
            conn.close()
            category_id = row["id"] if row else None

        if not category_id:
            await query.edit_message_text("أضيفي قسماً أولاً.")
            return

        context.user_data["admin_category_id"] = category_id
        context.user_data["admin_action"] = "add_book_title"
        await query.edit_message_text(
            "أرسلي عنوان الكتاب أو المورد.\n\nللإلغاء أرسلي /cancel"
        )

    elif data.startswith("admin:book:"):
        book_id = int(data.split(":")[2])
        conn = db_connect()
        book = conn.execute(
            "SELECT * FROM books WHERE id=?",
            (book_id,)
        ).fetchone()
        conn.close()

        if not book:
            await query.edit_message_text("الكتاب غير موجود.")
            return

        context.user_data["admin_book_id"] = book_id
        await query.edit_message_text(
            f"📖 {book['title']}\n\n"
            f"الوصف: {book['description'] or 'لا يوجد'}\n"
            f"الرابط: {book['url'] or 'لا يوجد'}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ تعديل العنوان", callback_data="admin:edit_book_title")],
                [InlineKeyboardButton("🔗 تعديل الرابط", callback_data="admin:edit_book_url")],
                [InlineKeyboardButton("📝 تعديل الوصف", callback_data="admin:edit_book_description")],
                [InlineKeyboardButton("🗑️ حذف المورد", callback_data="admin:delete_book")],
                [InlineKeyboardButton("↩️ رجوع", callback_data="admin:library")]
            ])
        )

    elif data == "admin:rename_category":
        context.user_data["admin_action"] = "rename_category"
        await query.edit_message_text("أرسلي الاسم الجديد للقسم.")

    elif data == "admin:delete_category":
        category_id = context.user_data.get("admin_category_id")
        if not category_id:
            await query.edit_message_text("لم يتم تحديد قسم.")
            return

        context.user_data["admin_action"] = "confirm_delete_category"
        await query.edit_message_text(
            "⚠️ حذف القسم سيحذف الكتب التابعة له أيضاً.\n"
            "أرسلي كلمة نعم للتأكيد، أو /cancel للإلغاء."
        )

    elif data == "admin:edit_book_title":
        context.user_data["admin_action"] = "edit_book_title"
        await query.edit_message_text("أرسلي العنوان الجديد.")

    elif data == "admin:edit_book_url":
        context.user_data["admin_action"] = "edit_book_url"
        await query.edit_message_text(
            "أرسلي الرابط الجديد، أو أرسلي - لإزالة الرابط."
        )

    elif data == "admin:edit_book_description":
        context.user_data["admin_action"] = "edit_book_description"
        await query.edit_message_text(
            "أرسلي الوصف الجديد، أو أرسلي - لإزالة الوصف."
        )

    elif data == "admin:delete_book":
        context.user_data["admin_action"] = "confirm_delete_book"
        await query.edit_message_text(
            "أرسلي نعم لتأكيد حذف المورد، أو /cancel للإلغاء."
        )

    elif data == "admin:stats":
        stats = get_statistics()
        await query.edit_message_text(
            "📊 إحصائيات البوت\n\n"
            f"👥 إجمالي المستخدمين: {stats.get('total_users', 0)}\n"
            f"🆕 المستخدمون اليوم: {stats.get('today_users', 0)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ رجوع", callback_data="admin:home")]
            ])
        )

    elif data == "admin:users":
        stats = get_statistics()
        await query.edit_message_text(
            f"👥 إجمالي المسجلين: {stats.get('total_users', 0)}\n\n"
            "يمكنك استخدام الإذاعة لإرسال إعلان للمستخدمين.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 إذاعة رسالة", callback_data="admin:broadcast")],
                [InlineKeyboardButton("↩️ رجوع", callback_data="admin:home")]
            ])
        )

    elif data == "admin:broadcast":
        context.user_data["admin_action"] = "broadcast"
        await query.edit_message_text(
            "📢 أرسلي الرسالة التي تريدين نشرها للمستخدمين.\n"
            "سيتم إرسالها كنص.\n\nللإلغاء أرسلي /cancel"
        )

    elif data == "admin:settings":
        maintenance = get_setting("maintenance", "0")
        subscription = get_setting("force_subscription", "1")
        await query.edit_message_text(
            "⚙️ إعدادات البوت\n\n"
            f"🔧 وضع الصيانة: {'مفعّل' if maintenance == '1' else 'متوقف'}\n"
            f"🔐 الاشتراك الإجباري: {'مفعّل' if subscription == '1' else 'متوقف'}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 تبديل الصيانة", callback_data="admin:toggle_maintenance")],
                [InlineKeyboardButton("🔐 تبديل الاشتراك الإجباري", callback_data="admin:toggle_subscription")],
                [InlineKeyboardButton("↩️ رجوع", callback_data="admin:home")]
            ])
        )

    elif data == "admin:toggle_maintenance":
        current = get_setting("maintenance", "0")
        set_setting("maintenance", "0" if current == "1" else "1")
        await query.edit_message_text(
            "تم تحديث وضع الصيانة.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin:settings")],
                [InlineKeyboardButton("↩️ لوحة التحكم", callback_data="admin:home")]
            ])
        )

    elif data == "admin:toggle_subscription":
        current = get_setting("force_subscription", "1")
        set_setting("force_subscription", "0" if current == "1" else "1")
        await query.edit_message_text(
            "تم تحديث إعداد الاشتراك الإجباري.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin:settings")],
                [InlineKeyboardButton("↩️ لوحة التحكم", callback_data="admin:home")]
            ])
        )


async def cancel_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("admin_action", None)
    context.user_data.pop("admin_category_id", None)
    context.user_data.pop("admin_book_id", None)
    await update.effective_message.reply_text("تم إلغاء العملية.")


@admin_only
async def admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("admin_action")
    if not action:
        return

    text_value = (update.effective_message.text or "").strip()
    if not text_value:
        await update.effective_message.reply_text("أرسلي نصاً صحيحاً.")
        return

    conn = db_connect()

    try:
        if action == "add_category":
            conn.execute(
                "INSERT INTO categories (name) VALUES (?)",
                (text_value,)
            )
            conn.commit()
            await update.effective_message.reply_text(
                f"✅ تمت إضافة القسم: {text_value}"
            )

        elif action == "rename_category":
            category_id = context.user_data.get("admin_category_id")
            if not category_id:
                await update.effective_message.reply_text("لم يتم تحديد القسم.")
                return
            conn.execute(
                "UPDATE categories SET name=? WHERE id=?",
                (text_value, category_id)
            )
            conn.commit()
            await update.effective_message.reply_text("✅ تم تعديل اسم القسم.")

        elif action == "confirm_delete_category":
            if text_value != "نعم":
                await update.effective_message.reply_text("تم إلغاء الحذف.")
                return
            category_id = context.user_data.get("admin_category_id")
            conn.execute("DELETE FROM books WHERE category_id=?", (category_id,))
            conn.execute("DELETE FROM categories WHERE id=?", (category_id,))
            conn.commit()
            context.user_data.pop("admin_category_id", None)
            await update.effective_message.reply_text("🗑️ تم حذف القسم وموارده.")

        elif action == "add_book_title":
            context.user_data["pending_book_title"] = text_value
            context.user_data["admin_action"] = "add_book_url"
            await update.effective_message.reply_text(
                "أرسلي رابط الكتاب أو المورد، أو أرسلي - إذا ما عنده رابط."
            )
            return

        elif action == "add_book_url":
            context.user_data["pending_book_url"] = "" if text_value == "-" else text_value
            context.user_data["admin_action"] = "add_book_description"
            await update.effective_message.reply_text(
                "أرسلي وصفاً مختصراً، أو أرسلي - بدون وصف."
            )
            return

        elif action == "add_book_description":
            category_id = context.user_data.get("admin_category_id")
            title = context.user_data.get("pending_book_title", "بدون عنوان")
            url = context.user_data.get("pending_book_url", "")
            description = "" if text_value == "-" else text_value

            conn.execute(
                "INSERT INTO books (category_id, title, url, description) VALUES (?, ?, ?, ?)",
                (category_id, title, url, description)
            )
            conn.commit()

            context.user_data.pop("pending_book_title", None)
            context.user_data.pop("pending_book_url", None)
            await update.effective_message.reply_text(
                f"✅ تمت إضافة المورد: {title}"
            )

        elif action in ("edit_book_title", "edit_book_url", "edit_book_description"):
            book_id = context.user_data.get("admin_book_id")
            if not book_id:
                await update.effective_message.reply_text("لم يتم تحديد المورد.")
                return

            if action == "edit_book_title":
                conn.execute("UPDATE books SET title=? WHERE id=?", (text_value, book_id))
            elif action == "edit_book_url":
                value = "" if text_value == "-" else text_value
                conn.execute("UPDATE books SET url=? WHERE id=?", (value, book_id))
            else:
                value = "" if text_value == "-" else text_value
                conn.execute("UPDATE books SET description=? WHERE id=?", (value, book_id))

            conn.commit()
            await update.effective_message.reply_text("✅ تم تعديل المورد.")

        elif action == "confirm_delete_book":
            if text_value != "نعم":
                await update.effective_message.reply_text("تم إلغاء الحذف.")
                return

            book_id = context.user_data.get("admin_book_id")
            conn.execute("DELETE FROM books WHERE id=?", (book_id,))
            conn.commit()
            await update.effective_message.reply_text("🗑️ تم حذف المورد.")

        elif action == "broadcast":
            conn.execute("SELECT telegram_id FROM users")
            users = conn.execute("SELECT telegram_id FROM users").fetchall()
            sent = 0
            failed = 0

            for user in users:
                try:
                    await context.bot.send_message(
                        chat_id=user["telegram_id"],
                        text=text_value
                    )
                    sent += 1
                    await asyncio.sleep(0.04)
                except TelegramError:
                    failed += 1

            await update.effective_message.reply_text(
                f"📢 انتهت الإذاعة.\n✅ أُرسلت: {sent}\n❌ تعذّر الإرسال: {failed}"
            )

        else:
            await update.effective_message.reply_text("العملية غير معروفة.")

    except sqlite3.IntegrityError:
        await update.effective_message.reply_text("هذا الاسم موجود بالفعل.")
    except Exception as exc:
        logger.exception("Admin action failed: %s", exc)
        await update.effective_message.reply_text(
            "حدث خطأ أثناء تنفيذ العملية. راجعي سجل التشغيل."
        )
    finally:
        conn.close()
        context.user_data.pop("admin_action", None)


# نهاية الجزء الثالث
# =========================
# الجزء الرابع: الاختبارات والدعم والنشر التلقائي
# =========================

def quiz_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 سؤال جديد", callback_data="quiz:new")],
        [InlineKeyboardButton("🏆 لوحة المتصدرين", callback_data="quiz:leaders")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="menu:home")]
    ])


QUIZ_QUESTIONS = [
    {
        "question": "كم عدد أركان الإسلام؟",
        "options": ["أربعة", "خمسة", "ستة", "سبعة"],
        "answer": 1,
        "explanation": "أركان الإسلام خمسة."
    },
    {
        "question": "ما أكبر كوكب في المجموعة الشمسية؟",
        "options": ["الأرض", "المريخ", "المشتري", "زحل"],
        "answer": 2,
        "explanation": "المشتري هو أكبر كواكب المجموعة الشمسية."
    },
    {
        "question": "ما ناتج 12 × 8؟",
        "options": ["86", "96", "108", "88"],
        "answer": 1,
        "explanation": "12 × 8 = 96."
    },
    {
        "question": "ما العضو المسؤول عن ضخ الدم في جسم الإنسان؟",
        "options": ["الرئة", "الكبد", "القلب", "الكلى"],
        "answer": 2,
        "explanation": "القلب يضخ الدم إلى أنحاء الجسم."
    },
    {
        "question": "ما اللغة المستخدمة لتنسيق صفحات الويب؟",
        "options": ["CSS", "SQL", "Python فقط", "Bash"],
        "answer": 0,
        "explanation": "تُستخدم CSS لتنسيق مظهر صفحات الويب."
    }
]


async def send_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = random.choice(QUIZ_QUESTIONS)
    context.user_data["current_quiz"] = question

    buttons = []
    for index, option in enumerate(question["options"]):
        buttons.append([
            InlineKeyboardButton(
                option,
                callback_data=f"quiz:answer:{index}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🏠 الرئيسية", callback_data="menu:home")
    ])

    message = (
        "🧠 تحدّي Dua Space\n\n"
        f"{question['question']}\n\n"
        "اختاري الإجابة الصحيحة:"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await update.effective_message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(buttons)
        )


async def quiz_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "quiz:new":
        await send_quiz(update, context)
        return

    if data == "quiz:leaders":
        conn = db_connect()
        rows = conn.execute("""
            SELECT telegram_id, SUM(score) AS points
            FROM quiz_scores
            GROUP BY telegram_id
            ORDER BY points DESC
            LIMIT 10
        """).fetchall()
        conn.close()

        if not rows:
            await query.edit_message_text(
                "🏆 لا توجد نتائج حتى الآن.",
                reply_markup=quiz_keyboard()
            )
            return

        lines = ["🏆 لوحة المتصدرين\n"]
        for rank, row in enumerate(rows, start=1):
            lines.append(f"{rank}. المستخدم {row['telegram_id']} — {row['points']} نقطة")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=quiz_keyboard()
        )
        return

    if data.startswith("quiz:answer:"):
        question = context.user_data.get("current_quiz")
        if not question:
            await query.edit_message_text(
                "انتهى السؤال. اختاري سؤالاً جديداً.",
                reply_markup=quiz_keyboard()
            )
            return

        selected = int(data.split(":")[2])
        user_id = update.effective_user.id
        correct = selected == question["answer"]

        conn = db_connect()
        if correct:
            conn.execute("""
                INSERT INTO quiz_scores (telegram_id, score)
                VALUES (?, 1)
            """, (user_id,))
        conn.commit()
        conn.close()

        context.user_data.pop("current_quiz", None)

        if correct:
            result = "✅ إجابة صحيحة! حصلتِ على نقطة."
        else:
            correct_answer = question["options"][question["answer"]]
            result = f"❌ الإجابة الصحيحة هي: {correct_answer}"

        await query.edit_message_text(
            f"{result}\n\n💡 {question['explanation']}",
            reply_markup=quiz_keyboard()
        )


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["support_waiting"] = True
    await update.effective_message.reply_text(
        "💬 اكتبي رسالتك أو المشكلة التي تواجهك، وسأرسلها للإدارة.\n\n"
        "للإلغاء أرسلي /cancel"
    )


async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("support_waiting"):
        return

    message = (update.effective_message.text or "").strip()
    if not message:
        await update.effective_message.reply_text("أرسلي المشكلة كنص.")
        return

    user = update.effective_user
    conn = db_connect()
    cursor = conn.execute("""
        INSERT INTO tickets (telegram_id, message, status, created_at)
        VALUES (?, ?, 'open', ?)
    """, (user.id, message, now_text()))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()

    context.user_data.pop("support_waiting", None)

    await update.effective_message.reply_text(
        f"✅ تم إرسال رسالتك للإدارة.\nرقم التذكرة: {ticket_id}"
    )

    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "📩 رسالة دعم جديدة\n\n"
                    f"رقم التذكرة: {ticket_id}\n"
                    f"الاسم: {user.full_name}\n"
                    f"المعرف: {user.id}\n"
                    f"اسم المستخدم: @{user.username or 'غير متوفر'}\n\n"
                    f"الرسالة:\n{message}"
                )
            )
        except TelegramError:
            logger.exception("Could not notify admin about support ticket")


@admin_only
async def tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_connect()
    rows = conn.execute("""
        SELECT id, telegram_id, message, created_at
        FROM tickets
        WHERE status='open'
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()
    conn.close()

    if not rows:
        await update.effective_message.reply_text("لا توجد تذاكر دعم مفتوحة.")
        return

    for row in rows:
        await update.effective_message.reply_text(
            f"📩 تذكرة رقم {row['id']}\n"
            f"المستخدم: {row['telegram_id']}\n"
            f"التاريخ: {row['created_at']}\n\n"
            f"{row['message']}\n\n"
            f"للرد: /reply {row['id']} نص الرد\n"
            f"للإغلاق: /close_ticket {row['id']}"
        )


@admin_only
async def reply_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "الاستخدام: /reply رقم_التذكرة نص الرد"
        )
        return

    try:
        ticket_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("رقم التذكرة غير صحيح.")
        return

    reply_text = " ".join(context.args[1:])

    conn = db_connect()
    ticket = conn.execute(
        "SELECT telegram_id FROM tickets WHERE id=?",
        (ticket_id,)
    ).fetchone()
    conn.close()

    if not ticket:
        await update.effective_message.reply_text("التذكرة غير موجودة.")
        return

    try:
        await context.bot.send_message(
            chat_id=ticket["telegram_id"],
            text=f"💬 رد الإدارة على تذكرتك رقم {ticket_id}:\n\n{reply_text}"
        )
        await update.effective_message.reply_text("✅ تم إرسال الرد.")
    except TelegramError:
        await update.effective_message.reply_text(
            "تعذّر إرسال الرد. ربما المستخدم حظر البوت."
        )


@admin_only
async def close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text(
            "الاستخدام: /close_ticket رقم_التذكرة"
        )
        return

    try:
        ticket_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("رقم التذكرة غير صحيح.")
        return

    conn = db_connect()
    cursor = conn.execute(
        "UPDATE tickets SET status='closed' WHERE id=?",
        (ticket_id,)
    )
    conn.commit()
    changed = cursor.rowcount
    conn.close()

    if changed:
        await update.effective_message.reply_text("✅ تم إغلاق التذكرة.")
    else:
        await update.effective_message.reply_text("التذكرة غير موجودة.")


async def scheduled_channel_post(context: ContextTypes.DEFAULT_TYPE):
    if get_setting("auto_posts_enabled", "0") != "1":
        return

    conn = db_connect()
    row = conn.execute("""
        SELECT id, content
        FROM scheduled_posts
        WHERE sent = 0
        ORDER BY id
        LIMIT 1
    """).fetchone()
    conn.close()

    if not row:
        return

    try:
        sent_message = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=row["content"]
        )

        conn = db_connect()
        conn.execute(
            "UPDATE scheduled_posts SET sent=1 WHERE id=?",
            (row["id"],)
        )
        conn.commit()
        conn.close()

        logger.info(
            "Scheduled post %s sent as Telegram message %s",
            row["id"], sent_message.message_id
        )
    except TelegramError:
        logger.exception("Scheduled channel post failed")


@admin_only
async def add_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = " ".join(context.args).strip()

    if not content:
        await update.effective_message.reply_text(
            "الاستخدام: /addpost نص المنشور"
        )
        return

    conn = db_connect()
    cursor = conn.execute("""
        INSERT INTO scheduled_posts (content, sent, created_at)
        VALUES (?, 0, ?)
    """, (content, now_text()))
    post_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await update.effective_message.reply_text(
        f"✅ أُضيف المنشور إلى قائمة الانتظار.\nرقمه: {post_id}\n"
        "لن يُنشر تلقائياً إلا بعد تفعيل النشر التلقائي."
    )


@admin_only
async def auto_posts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = get_setting("auto_posts_enabled", "0")
    new_value = "0" if current == "1" else "1"
    set_setting("auto_posts_enabled", new_value)

    await update.effective_message.reply_text(
        "✅ النشر التلقائي أصبح "
        + ("مفعّلاً." if new_value == "1" else "متوقفاً.")
        + "\nاستخدمي /addpost لإضافة منشورات."
    )


# نهاية الجزء الرابع
# =========================
# الجزء الخامس: الإشراف والتشغيل
# =========================

# ---------- أوامر عامة ----------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "✦ Dua Space — المساعدة\n\n"
        "/start — بدء استخدام البوت\n"
        "/help — المساعدة\n"
        "/library — المكتبة\n"
        "/quiz — تحدّي الأسئلة\n"
        "/support — التواصل مع الإدارة\n"
        "/tasbeeh — المسبحة الإلكترونية\n"
        "/id — معرفة معرّفك\n\n"
        "أوامر الإدارة:\n"
        "/admin — لوحة التحكم\n"
        "/addpost — إضافة منشور للقناة\n"
        "/autoposts — تشغيل أو إيقاف النشر التلقائي\n"
        "/tickets — عرض طلبات الدعم\n"
        "/reply — الرد على تذكرة\n"
        "/close_ticket — إغلاق تذكرة\n\n"
        "أوامر المجموعات للمشرفين:\n"
        "/rules — قوانين المجموعة\n"
        "/warn — تحذير عضو\n"
        "/warnings — عرض تحذيرات عضو\n"
        "/ban — حظر عضو بالرد على رسالته\n"
        "/unban — إلغاء حظر عضو باستخدام معرّفه\n"
        "/mute — كتم عضو بالرد على رسالته\n"
        "/unmute — إلغاء كتم عضو بالرد على رسالته\n"
        "/kick — إخراج عضو بالرد على رسالته\n"
        "/del — حذف رسالة بالرد عليها\n"
        "/pin — تثبيت رسالة بالرد عليها\n"
        "/unpin — إلغاء تثبيت رسالة بالرد عليها\n"
        "/purge — حذف الرسائل السابقة بالرد على رسالة"
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    await update.effective_message.reply_text(
        f"👤 معرّفك: {user.id}\n"
        f"💬 معرّف المحادثة: {chat.id}"
    )


async def library_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_categories(update, context)


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_quiz(update, context)


async def tasbeeh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await open_tasbeeh(update, context)


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📌 قوانين المجموعة\n\n"
        "1. احترام جميع الأعضاء.\n"
        "2. منع الإساءة والتنمر.\n"
        "3. منع الإعلانات غير المصرح بها.\n"
        "4. عدم إغراق المجموعة بالرسائل المتكررة.\n"
        "5. الالتزام بموضوع المجموعة."
    )


# ---------- أدوات الإشراف ----------

def replied_user(update: Update):
    message = update.effective_message
    if message and message.reply_to_message:
        return message.reply_to_message.from_user
    return None


async def group_admin_required(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text(
            "الأمر ده مخصص للمجموعات."
        )
        return False

    if is_owner(user.id) or is_admin(user.id):
        return True

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return True
    except TelegramError:
        pass

    await update.effective_message.reply_text(
        "❌ الأمر ده متاح لمشرفي المجموعة فقط."
    )
    return False


async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    target = replied_user(update)
    if not target:
        await update.effective_message.reply_text(
            "استخدمي الأمر بالرد على رسالة العضو:\n/warn"
        )
        return

    if target.is_bot:
        await update.effective_message.reply_text("لا يمكن تحذير بوت.")
        return

    chat_id = update.effective_chat.id

    conn = db_connect()
    conn.execute("""
        INSERT INTO warnings (chat_id, user_id, reason, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        chat_id,
        target.id,
        "تحذير بواسطة مشرف",
        now_text()
    ))

    count = conn.execute("""
        SELECT COUNT(*) AS total
        FROM warnings
        WHERE chat_id=? AND user_id=?
    """, (chat_id, target.id)).fetchone()["total"]

    conn.commit()
    conn.close()

    await update.effective_message.reply_text(
        f"⚠️ تم تحذير {target.full_name}.\n"
        f"عدد التحذيرات المسجلة: {count}"
    )


async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    target = replied_user(update)

    if not target and context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.effective_message.reply_text("معرّف العضو غير صحيح.")
            return
    elif target:
        target_id = target.id
    else:
        await update.effective_message.reply_text(
            "استخدمي /warnings بالرد على رسالة العضو، "
            "أو اكتبي /warnings معرّف_العضو"
        )
        return

    conn = db_connect()
    count = conn.execute("""
        SELECT COUNT(*) AS total
        FROM warnings
        WHERE chat_id=? AND user_id=?
    """, (update.effective_chat.id, target_id)).fetchone()["total"]
    conn.close()

    await update.effective_message.reply_text(
        f"⚠️ عدد التحذيرات المسجلة للعضو {target_id}: {count}"
    )


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    target = replied_user(update)
    if not target:
        await update.effective_message.reply_text(
            "استخدمي /ban بالرد على رسالة العضو."
        )
        return

    if target.id == update.effective_user.id or target.is_bot:
        await update.effective_message.reply_text("لا يمكن تنفيذ الحظر على هذا العضو.")
        return

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id
        )
        await update.effective_message.reply_text(
            f"🚫 تم حظر {target.full_name}."
        )
    except TelegramError:
        await update.effective_message.reply_text(
            "تعذّر الحظر. تأكدي من صلاحيات البوت وترتيب المشرفين."
        )


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    if not context.args:
        await update.effective_message.reply_text(
            "الاستخدام: /unban معرّف_العضو"
        )
        return

    try:
        target_id = int(context.args[0])
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_id
        )
        await update.effective_message.reply_text("✅ تم إلغاء الحظر.")
    except (ValueError, TelegramError):
        await update.effective_message.reply_text(
            "تعذّر إلغاء الحظر. راجعي المعرّف والصلاحيات."
        )


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    target = replied_user(update)
    if not target:
        await update.effective_message.reply_text(
            "استخدمي /mute بالرد على رسالة العضو."
        )
        return

    try:
        until = int(time.time()) + 3600
        from telegram import ChatPermissions

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await update.effective_message.reply_text(
            f"🔇 تم كتم {target.full_name} لمدة ساعة."
        )
    except TelegramError:
        await update.effective_message.reply_text(
            "تعذّر الكتم. تأكدي من صلاحيات البوت."
        )


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    target = replied_user(update)
    if not target:
        await update.effective_message.reply_text(
            "استخدمي /unmute بالرد على رسالة العضو."
        )
        return

    try:
        from telegram import ChatPermissions

        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        )
        await update.effective_message.reply_text(
            f"🔊 تم إلغاء كتم {target.full_name}."
        )
    except TelegramError:
        await update.effective_message.reply_text(
            "تعذّر إلغاء الكتم. تأكدي من صلاحيات البوت."
        )


async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    target = replied_user(update)
    if not target:
        await update.effective_message.reply_text(
            "استخدمي /kick بالرد على رسالة العضو."
        )
        return

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id
        )
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id
        )
        await update.effective_message.reply_text(
            f"👢 تم إخراج {target.full_name}."
        )
    except TelegramError:
        await update.effective_message.reply_text(
            "تعذّر إخراج العضو. تأكدي من صلاحيات البوت."
        )


async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    message = update.effective_message
    if not message.reply_to_message:
        await message.reply_text("استخدمي /del بالرد على الرسالة المطلوب حذفها.")
        return

    try:
        await message.reply_to_message.delete()
        await message.delete()
    except TelegramError:
        await message.reply_text("تعذّر حذف الرسالة. تأكدي من صلاحيات البوت.")


async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    message = update.effective_message
    if not message.reply_to_message:
        await message.reply_text("استخدمي /pin بالرد على الرسالة.")
        return

    try:
        await message.reply_to_message.pin()
        await message.reply_text("📌 تم تثبيت الرسالة.")
    except TelegramError:
        await message.reply_text("تعذّر التثبيت. تأكدي من صلاحيات البوت.")


async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    try:
        await context.bot.unpin_all_chat_messages(
            chat_id=update.effective_chat.id
        )
        await update.effective_message.reply_text("تم إلغاء تثبيت الرسائل.")
    except TelegramError:
        await update.effective_message.reply_text(
            "تعذّر إلغاء التثبيت. تأكدي من صلاحيات البوت."
        )


async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_required(update, context):
        return

    message = update.effective_message
    if not message.reply_to_message:
        await message.reply_text(
            "استخدمي /purge بالرد على أول رسالة تريدين حذفها."
        )
        return

    start_id = message.reply_to_message.message_id
    end_id = message.message_id

    if end_id - start_id > 100:
        await message.reply_text("يمكن حذف 100 رسالة كحد أقصى في العملية الواحدة.")
        return

    deleted = 0
    for message_id in range(start_id, end_id + 1):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=message_id
            )
            deleted += 1
        except TelegramError:
            pass

    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🧹 اكتملت العملية. عدد الرسائل المحذوفة: {deleted}"
        )
    except TelegramError:
        pass


# ---------- إدارة رسائل المستخدمين ----------

async def private_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_user:
        return

    if update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id

    if is_admin(user_id) and context.user_data.get("admin_action"):
        await admin_text_input(update, context)
        return

    if context.user_data.get("support_waiting"):
        await support_message(update, context)
        return


# ---------- ربط الأزرار والمهام ----------

async def post_init(application: Application):
    init_database()

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing. Set it in the hosting environment.")
        return

    if application.job_queue:
        application.job_queue.run_repeating(
            scheduled_channel_post,
            interval=60 * 60,
            first=30,
            name="scheduled_channel_posts"
        )

    logger.info("Dua Space initialized.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception while processing update", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN غير موجود. أضيفي التوكن في متغيرات البيئة على الاستضافة."
        )

    init_database()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # أوامر المستخدمين
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("library", library_command))
    application.add_handler(CommandHandler("quiz", quiz_command))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("tasbeeh", tasbeeh_command))
    application.add_handler(CommandHandler("cancel", cancel_admin_action))

    # لوحة الإدارة
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("tickets", tickets_command))
    application.add_handler(CommandHandler("reply", reply_ticket))
    application.add_handler(CommandHandler("close_ticket", close_ticket))
    application.add_handler(CommandHandler("addpost", add_post_command))
    application.add_handler(CommandHandler("autoposts", auto_posts_command))

    # أوامر المجموعات
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("warn", warn_command))
    application.add_handler(CommandHandler("warnings", warnings_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("kick", kick_command))
    application.add_handler(CommandHandler("del", del_command))
    application.add_handler(CommandHandler("pin", pin_command))
    application.add_handler(CommandHandler("unpin", unpin_command))
    application.add_handler(CommandHandler("purge", purge_command))

    # أزرار المكتبة والقائمة والمسبحة
    application.add_handler(CallbackQueryHandler(
        menu_callbacks,
        pattern=r"^(check_subscription|menu:|category:|book:|tasbeeh:)"
    ))

    # أزرار الإدارة
    application.add_handler(CallbackQueryHandler(
        admin_callbacks,
        pattern=r"^admin:"
    ))

    # أزرار الاختبارات
    application.add_handler(CallbackQueryHandler(
        quiz_callbacks,
        pattern=r"^quiz:"
    ))

    # الرسائل النصية الخاصة بالإدارة والدعم
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        private_text_router
    ))

    application.add_error_handler(error_handler)

    logger.info("Starting Dua Space...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False
    )


if __name__ == "__main__":
    main()

# نهاية الجزء الخامس
