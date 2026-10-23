import asyncio
import logging
import os
import random
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
    "أهلًا بكم في Dua Space! 🪐\n"
    "مساحتكم للإبداع والتصميم والمعرفة.\n\n"
    "يرجى اختيار القسم المطلوب عبر الأزرار أدناه:"
)

DEFAULT_FOOTER = "\n\n—\n🪐 Dua Space • مساحتكم للإبداع"

DEFAULT_SERVICES = [
    (
        "🎨 التصميم الجرافيكي والهويات البصرية",
        "تصميمات وهوية بصرية متكاملة تناسب مشاريعكم وأعمالكم.",
        "حسب تفاصيل الطلب",
    ),
    (
        "🖼️ تصميم الشعارات والإعلانات",
        "تصميم شعارات احترافية وإعلانات تسويقية مبتكرة.",
        "حسب تفاصيل الطلب",
    ),
    (
        "💌 تصميم الدعوات والبطاقات",
        "تصميم بطاقات معايدة ودعوات مناسبات بلمسة فنية مميزة.",
        "حسب تفاصيل الطلب",
    ),
    (
        "📦 خدمات تصميم أخرى",
        "يرجى إرسال تفاصيل الفكرة أو الخدمة المطلوبة لمراجعتها وتحديد التكلفة.",
        "يُحدد بعد مراجعة الطلب",
    ),
]

DEFAULT_ADHIKAR = [
    (
        "أذكار الصباح",
        "🌅 أذكار الصباح:\n\n"
        "1. «أَصْبَحْنَا وَأَصْبَحَ المُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ لاَ إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لاَ شَرِيكَ لَهُ، لَهُ المُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ»\n\n"
        "2. «اللّهُـمَّ بِكَ أَصْـبَحْنا وَبِكَ أَمْسَـينا، وَبِكَ نَحْـيا وَبِكَ نَمُـوتُ وَإِلَـيْكَ النُّـشُور»\n\n"
        "3. «سَيِّدُ الاِسْتِغْفَارِ: اللَّهُمَّ أَنْتَ رَبِّي لاَ إِلَهَ إِلاَّ أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ، وَأَنَا عَلَى عهدك ووعدك ما استطعت، أعوذ بك من شر ما صنعت، أبوء لك بنعمتك علي، وأبوء بذنبي فاغفر لي فإنه لا يغفر الذنوب إلا أنت»\n\n"
        "4. «بِسـمِ اللهِ الذي لا يَضُـرُّ مَعَ اسمِـهِ شَيءٌ في الأرْضِ وَلا في السّمـاءِ وَهـوَ السّمـيعُ العَلـيم» (3 مرات)\n\n"
        "5. «رَضيـتُ بِاللهِ رَبَّـاً وَبِالإسْلامِ ديـناً وَبِمُحَـمَّدٍ صلى الله عليه وسلم نَبِيّـاً» (3 مرات)"
    ),
    (
        "أذكار المساء",
        "🌇 أذكار المساء:\n\n"
        "1. «أَمْسَيْنَا وَأَمْسَى المُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ لاَ إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لاَ شَرِيكَ لَهُ، لَهُ المُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ»\n\n"
        "2. «اللّهُـمَّ بِكَ أَمْسَـينا، وَبِكَ أَصْـبَحْنا، وَبِكَ نَحْـيا، وَبِكَ نَمُـوتُ وَإِلَـيْكَ المَصِـير»\n\n"
        "3. «أَعُوذُ بِكَلِمَاتِ اللهِ التَّامَّاتِ مِنْ شَرِّ مَا خَلَقَ» (3 مرات)\n\n"
        "4. «اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَافِيَةَ فِي الدُّنْيَا وَالآخِرَةِ»"
    ),
    (
        "أذكار بعد الصلاة",
        "🕌 أذكار ما بعد الصلوات المكتوبة:\n\n"
        "• «أستغفرُ الله (ثلاثاً)، اللهم أنت السلام ومنك السلام، تباركت يا ذا الجلال والإكرام»\n"
        "• «لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير»\n"
        "• تسبيح (33)، تحميد (33)، تكبير (33)، وتمام المائة: «لا إله إلا الله وحده لا شريك له»\n"
        "• قراءة آية الكرسي والمعوذات."
    ),
    (
        "أذكار النوم والاستيقاظ",
        "🌙 أذكار النوم:\n"
        "«بِاسْمِكَ رَبِّـي وَضَعْـتُ جَنْـبي، وَبِكَ أَرْفَعُـه، فَإِن أَمْسَـكْتَ نَفْسـي فارْحَمْـها، وَإِنْ أَرْسَلْتَـها فاحْفَظْـها بِمـا تَحْفَـظُ بِه عِبـادَكَ الصّـالِحـين»\n\n"
        "☀️ أذكار الاستيقاظ:\n"
        "«الحَمْـدُ لِلّهِ الَّذِي أَحْـيَانَا بَعْـدَ مَا أَمَاتَـنَا وَإِلَيْـهِ النُّـشُور»"
    ),
    (
        "أدعية مأثورة وجوامع الدعاء",
        "🤲 أدعية مأثورة نافعة:\n\n"
        "• «رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ»\n"
        "• «يَا مُقَلِّبَ الْقُلُوبِ ثَبِّتْ قَلْبِي عَلَى دِينِكَ»\n"
        "• «اللَّهُمَّ إِنِّي أَسْأَلُكَ عِلْمًا نَافِعًا، وَرِزْقًا طَيِّبًا، وَعَمَلًا مُتَقَبَّلًا»"
    ),
]

DEFAULT_SEERAH = [
    (
        "1. المولد الشريف والنشأة",
        "🌿 المولد والنشأة:\n\n"
        "• وُلِدَ النبي محمد ﷺ في عام الفيل في مكة المكرمة يتيم الأب.\n"
        "• أرضعته حليمة السعدية في بني سعد ونشأ في فصاحة البادية.\n"
        "• توفيت والدته آمنة بنت وهب وعمره 6 سنوات، فكفله جده عبدالمطلب ثم عمه أبو طالب.\n"
        "• عُرف بالصادق الأمين وعمل في رعي الغنم والتجارة."
    ),
    (
        "2. البعثة النبوية وبدء الوحي",
        "📖 نزول الوحي والدعوة بمكة:\n\n"
        "• نزل عليه الوحي جبريل عليه السلام في غار حراء في سن الأربعين بأول آيات القرآن: ﴿اقْرَأْ بِاسْمِ رَبِّكَ الَّذِي خَلَقَ﴾.\n"
        "• بدأت الدعوة سراً ثم جهراً وواجه المسلمون الأوائل الأذى بصبر وثبات.\n"
        "• رحلة الإسراء والمعراج وفرض الصلوات الخمس."
    ),
    (
        "3. الهجرة النبوية الشريفة",
        "🐪 الهجرة إلى المدينة المنورة:\n\n"
        "• بعد بيعتي العقبة، أذن الله بالهجرة إلى يثرب، وهاجر ﷺ بصحبة أبي بكر الصديق.\n"
        "• استقبلهم الأنصار وبُني المسجد النبوي وتمت المؤاخاة ووثيقة المدينة."
    ),
    (
        "4. الغزوات والعهود وبناء الأمة",
        "⚔️ الغزوات الكبرى وفتح مكة:\n\n"
        "• دافع المسلمون عن رسالتهم في بدر وأحد والخندق والحديبية.\n"
        "• في السنة الثامنة للهجرة فتح النبي ﷺ مكة سلماً وعفا عن أهلها."
    ),
    (
        "5. حجة الوداع والوفاة الشريفة",
        "🕊️ حجة الوداع والرفيق الأعلى:\n\n"
        "• في السنة العاشرة للهجرة ألقى ﷺ خطبة الوداع الخالدة.\n"
        "• في السنة الحادية عشرة للهجرة انتقل إلى الرفيق الأعلى بعد أن بلغ الرسالة وأدى الأمانة."
    ),
]

QUOTES = [
    "«وَتَوَكَّلْ عَلَى الْحَيِّ الَّذِي لَا يَمُوتُ» ✨",
    "«إِنَّ مَعَ الْعُسْرِ يُسْرًا» 🪐",
    "قال رسول الله ﷺ: «إنَّ اللهَ يُحِبُّ إذا عمِلَ أحَدُكُم عمَلًا أنْ يُتْقِنَه».",
    "قال رسول الله ﷺ: «مَن سَلَكَ طَرِيقًا يَلْتَمِسُ فِيهِ عِلْمًا، سَهَّلَ اللَّهُ له به طَرِيقًا إلى الجَنَّةِ».",
    "«التصميم ليس فقط مظهراً، بل هو أثر ورسالة واضحة تُخلد في الأذهان.» 🎨",
    "«ابدأ بما لديك، وكن مؤمناً بأن خطوتك البسيطة تصنع فارقاً عظيماً.» ✨",
]

FAQ_TEXT = (
    "💡 **الأسئلة الشائعة حول Dua Space:**\n\n"
    "• **كيف يمكنني طلب خدمة تصميم؟**\n"
    "من قائمة «🛍️ تصفح الخدمات»، اختر الخدمة ثم اضغط «📩 طلب هذه الخدمة»، واكتب التفاصيل.\n\n"
    "• **ما هي آلية الدفع المتوفرة؟**\n"
    "يتم الاتفاق والتأكيد حول طرق الدفع المتاحة عبر التواصل المباشر مع الإدارة.\n\n"
    "• **كم تستغرق مدة تنفيذ التصميم؟**\n"
    "تعتمد على نوع وحجم العمل، وتتراوح عادة بين 24 إلى 48 ساعة للتصاميم الفردية."
)


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
    row = db_one("SELECT value FROM settings WHERE key = ?", (key,))
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

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT 'غير محدد',
                description TEXT NOT NULL DEFAULT '',
                file_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                file_id TEXT NOT NULL,
                media_type TEXT NOT NULL DEFAULT 'photo',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                rating INTEGER NOT NULL,
                comment TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS adhkar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS seerah (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL
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

    if db_one("SELECT key FROM settings WHERE key = 'seeded_services'") is None:
        for title, description, price in DEFAULT_SERVICES:
            db_execute(
                "INSERT INTO services(title, description, price, active) VALUES(?, ?, ?, 1)",
                (title, description, price),
            )
        set_setting("seeded_services", "1")

    if db_one("SELECT key FROM settings WHERE key = 'seeded_adhkar'") is None:
        for cat, content in DEFAULT_ADHIKAR:
            db_execute(
                "INSERT INTO adhkar(category, content) VALUES(?, ?)",
                (cat, content),
            )
        set_setting("seeded_adhkar", "1")

    if db_one("SELECT key FROM settings WHERE key = 'seeded_seerah'") is None:
        for title, content in DEFAULT_SEERAH:
            db_execute(
                "INSERT INTO seerah(title, content) VALUES(?, ?)",
                (title, content),
            )
        set_setting("seeded_seerah", "1")

    if db_one("SELECT key FROM settings WHERE key = 'welcome_msg'") is None:
        set_setting("welcome_msg", DEFAULT_WELCOME)

    if db_one("SELECT key FROM settings WHERE key = 'footer'") is None:
        set_setting("footer", DEFAULT_FOOTER)


def save_user(user):
    if not user:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    db_execute(
        """
        INSERT INTO users(user_id, username, first_name, first_seen, last_seen)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_seen = excluded.last_seen
        """,
        (user.id, user.username or "", user.first_name or "", now, now),
    )


def is_admin_user(user_id):
    return bool(ADMIN_ID and user_id == ADMIN_ID)


# -------------------- القوائم والأزرار --------------------

def main_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🛍️ تصفح الخدمات", callback_data="services"),
                InlineKeyboardButton("🎨 معرض الأعمال", callback_data="portfolio"),
            ],
            [
                InlineKeyboardButton("📚 مكتبتي", callback_data="library"),
                InlineKeyboardButton("📿 السبحة الإلكترونية", callback_data="tasbeeh"),
            ],
            [
                InlineKeyboardButton("🌸 الأذكار والأدعية", callback_data="adhkar_menu"),
                InlineKeyboardButton("📜 السيرة النبوية", callback_data="seerah_menu"),
            ],
            [
                InlineKeyboardButton("⭐ آراء العملاء", callback_data="reviews_list"),
                InlineKeyboardButton("✨ فائدة اليوم", callback_data="daily_quote"),
            ],
            [
                InlineKeyboardButton("💡 أسئلة شائعة", callback_data="faq"),
                InlineKeyboardButton("💬 التواصل المباشر", url=CONTACT_URL),
            ],
            [
                InlineKeyboardButton("📢 قناة Dua Space الرسمية", url=CHANNEL_URL),
            ],
        ]
    )


def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🛍️ إدارة الخدمات", callback_data="admin_services"),
                InlineKeyboardButton("📥 طلبات العملاء", callback_data="admin_orders"),
            ],
            [
                InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users"),
                InlineKeyboardButton("📢 إذاعة عامة (Broadcast)", callback_data="admin_broadcast"),
            ],
            [
                InlineKeyboardButton("🎨 إدارة المعرض", callback_data="admin_portfolio"),
                InlineKeyboardButton("📚 إدارة المكتبة", callback_data="admin_books"),
            ],
            [
                InlineKeyboardButton("📿 إدارة الأذكار", callback_data="admin_adhkar"),
                InlineKeyboardButton("📜 إدارة السيرة", callback_data="admin_seerah"),
            ],
            [
                InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
                InlineKeyboardButton("⚙️ إعدادات النصوص", callback_data="admin_settings"),
            ],
            [
                InlineKeyboardButton("📢 النشر في القناة", callback_data="publish_help"),
                InlineKeyboardButton("👀 معاينة واجهة المستخدم", callback_data="show_customer_menu"),
            ],
        ]
    )


def tasbeeh_keyboard(count=0, phrase="سبحان الله"):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"✨ {phrase}: {count}", callback_data=f"tasbeeh_count:{count}:{phrase}")
            ],
            [
                InlineKeyboardButton("سبحان الله", callback_data=f"tasbeeh_set:0:سبحان الله"),
                InlineKeyboardButton("الحمد لله", callback_data=f"tasbeeh_set:0:الحمد لله"),
            ],
            [
                InlineKeyboardButton("الله أكبر", callback_data=f"tasbeeh_set:0:الله أكبر"),
                InlineKeyboardButton("أستغفر الله", callback_data=f"tasbeeh_set:0:أستغفر الله"),
            ],
            [
                InlineKeyboardButton("لا حول ولا قوة إلا بالله", callback_data=f"tasbeeh_set:0:لا حول ولا قوة إلا بالله"),
            ],
            [
                InlineKeyboardButton("🔄 تصفير العداد", callback_data=f"tasbeeh_reset:{phrase}"),
                InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"),
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
        [InlineKeyboardButton(row["title"][:60], callback_data=f"service:{row['id']}")]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(buttons), rows


def library_keyboard():
    rows = db_all("SELECT id, title FROM books ORDER BY id DESC LIMIT 30")
    buttons = [
        [InlineKeyboardButton(f"📖 {row['title'][:50]}", callback_data=f"book:{row['id']}")]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(buttons), rows


def portfolio_keyboard():
    rows = db_all("SELECT id, title FROM portfolio ORDER BY id DESC LIMIT 20")
    buttons = [
        [InlineKeyboardButton(f"🖼️ {row['title'][:40]}", callback_data=f"view_port:{row['id']}")]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(buttons), rows


def adhkar_keyboard():
    rows = db_all("SELECT id, category FROM adhkar ORDER BY id ASC")
    buttons = [
        [InlineKeyboardButton(f"🌸 {row['category']}", callback_data=f"zekr:{row['id']}")]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def seerah_keyboard():
    rows = db_all("SELECT id, title FROM seerah ORDER BY id ASC")
    buttons = [
        [InlineKeyboardButton(f"📖 {row['title']}", callback_data=f"seerah_part:{row['id']}")]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(buttons)


def admin_services_keyboard():
    rows = db_all("SELECT id, title, active FROM services ORDER BY id DESC LIMIT 50")
    buttons = []
    for row in rows:
        status = "✅" if row["active"] else "⏸️"
        buttons.append([InlineKeyboardButton(f"{status} {row['title'][:48]}", callback_data=f"svcadmin:{row['id']}")])
    buttons.extend([
        [InlineKeyboardButton("➕ إضافة خدمة جديدة", callback_data="svc_add")],
        [InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")],
    ])
    return InlineKeyboardMarkup(buttons)


# -------------------- أوامر البدء والمساعدة --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    context.user_data.pop("flow", None)

    if is_admin_user(user.id):
        await update.effective_message.reply_text(
            "🪐 أهلًا بك في لوحة إدارة Dua Space.\n"
            "يرجى تحديد العملية المطلوبة من الخيارات أدناه:",
            reply_markup=admin_keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            get_setting("welcome_msg", DEFAULT_WELCOME),
            reply_markup=main_menu_keyboard(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin_user(update.effective_user.id):
        text = (
            "🛠️ **أوامر الإدارة المباشرة:**\n\n"
            "/admin — لوحة التحكم الشاملة\n"
            "/users — عرض قائمة المستخدمين المسجلين\n"
            "/publish [النص] — نشر رسالة في القناة بتوقيعكِ\n"
            "/pin [النص] — نشر الرسالة وتثبيتها في القناة\n"
            "/stats — تقرير الإحصائيات الشامل\n"
            "/set_welcome [النص] — تعديل الترحيب العام\n"
            "/set_footer [النص] — تعديل توقيع المنشورات\n"
            "/cancel — إلغاء أي إجراء جاري\n\n"
            "• لنشر صورة أو تصميم بالقناة: أرسليه للبوت مباشرة خارج خطوات الإدخال."
        )
    else:
        text = (
            "أهلًا بكم في Dua Space 🪐\n\n"
            "يمكنكم استخدام الأزرار لتصفح الخدمات، المعرض، المكتبة، والسبحة، أو كتابة أي كلمة للبحث الفوري عنها."
        )
    await update.effective_message.reply_text(text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("flow", None)
    context.user_data.pop("pending_service", None)
    context.user_data.pop("pending_book", None)
    context.user_data.pop("pending_portfolio", None)
    await update.effective_message.reply_text(
        "تم إلغاء الخطوة الجارية بنجاح.\nيرجى إرسال /start للعودة إلى القائمة الرئيسية."
    )


# -------------------- عرض المستخدمين --------------------

async def show_users_list(target, context):
    rows = db_all(
        "SELECT user_id, username, first_name, last_seen FROM users ORDER BY last_seen DESC LIMIT 50"
    )
    if not rows:
        await target.reply_text("لا يوجد مستخدمون مسجلون حتى الآن.")
        return

    text = f"👥 **قائمة آخر مستخدمي البوت النشطين ({len(rows)}):**\n\n"
    for idx, u in enumerate(rows, 1):
        uname = f"@{u['username']}" if u["username"] else "بدون يوزر"
        fname = u["first_name"] or "مستخدم"
        last_date = u["last_seen"][:16] if u["last_seen"] else ""
        text += f"{idx}. {fname} ({uname})\n   • الـ ID: `{u['user_id']}` | نشاط: {last_date}\n\n"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")]])
    await target.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


# -------------------- تدفق الطلبات والتقييمات --------------------

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE, service_id: int):
    service = db_one("SELECT * FROM services WHERE id = ? AND active = 1", (service_id,))
    if not service:
        await update.callback_query.message.reply_text("عذرًا، هذه الخدمة غير متوفرة حالياً.")
        return

    context.user_data["flow"] = {"kind": "order_details", "service_id": service_id}
    await update.callback_query.message.reply_text(
        f"📝 تم اختيار خدمة: {service['title']}\n\n"
        "يرجى كتابة تفاصيل الطلب في رسالة واحدة (المطلوب بدقة، الألوان، المقاسات، والموعد المطلوب).\n\n"
        "للإلغاء أرسل /cancel."
    )


async def handle_order_text(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    details = (update.effective_message.text or "").strip()
    if not details:
        await update.effective_message.reply_text("يرجى كتابة تفاصيل الطلب كنص، أو إرسال /cancel للإلغاء.")
        return

    service = db_one("SELECT * FROM services WHERE id = ? AND active = 1", (flow["service_id"],))
    if not service:
        context.user_data.pop("flow", None)
        await update.effective_message.reply_text("عذرًا، الخدمة لم تعد متاحة.")
        return

    user = update.effective_user
    save_user(user)

    order_id = db_execute(
        """
        INSERT INTO orders(user_id, username, service_id, service_title, price, details, status)
        VALUES(?, ?, ?, ?, ?, ?, 'جديد')
        """,
        (user.id, user.username or "", service["id"], service["title"], service["price"], details),
    )
    context.user_data.pop("flow", None)

    await update.effective_message.reply_text(
        f"✅ تم استلام طلبكم برقم: #{order_id}.\n"
        "سنراجع التفاصيل ونتواصل معكم قريباً.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 التواصل بشأن الدفع والطلب", url=CONTACT_URL)],
                [InlineKeyboardButton("🛍️ العودة للخدمات", callback_data="services")],
            ]
        ),
    )

    username_text = f"@{user.username}" if user.username else "بدون معرّف"
    admin_text = (
        f"📥 طلب جديد رقم #{order_id}\n\n"
        f"الخدمة: {service['title']}\n"
        f"السعر التقديري: {service['price']}\n"
        f"العميل: {user.first_name or 'مستخدم'} ({username_text})\n"
        f"معرّف العميل: {user.id}\n\n"
        f"التفاصيل:\n{details[:2500]}"
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("فتح الطلب وإدارته", callback_data=f"orderadmin:{order_id}")]]
            ),
        )
    except Exception:
        logger.exception("Unable to notify admin about order %s", order_id)


# -------------------- معالجة نقرات الأزرار --------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    user_id = query.from_user.id
    admin = is_admin_user(user_id)

    # 1. الواجهات العامة
    if data in ("home", "show_customer_menu"):
        await query.message.reply_text(
            get_setting("welcome_msg", DEFAULT_WELCOME),
            reply_markup=main_menu_keyboard(),
        )
        return

    # 2. الخدمات
    if data == "services":
        keyboard, rows = services_keyboard(active_only=True)
        if not rows:
            await query.message.reply_text(
                "لا توجد خدمات متاحة حالياً. يرجى التواصل معنا للاستفسار.",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await query.message.reply_text("🛍️ يرجى اختيار الخدمة المطلوبة:", reply_markup=keyboard)
        return

    if data.startswith("service:"):
        service_id = int(data.split(":", 1)[1])
        service = db_one("SELECT * FROM services WHERE id = ? AND active = 1", (service_id,))
        if not service:
            await query.message.reply_text("الخدمة غير متاحة.")
            return

        text = (
            f"✨ {service['title']}\n\n"
            f"الوصف:\n{service['description'] or 'يرجى التواصل معنا لمعرفة التفاصيل.'}\n\n"
            f"السعر: {service['price']}"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📩 طلب هذه الخدمة", callback_data=f"order:{service_id}")],
                [InlineKeyboardButton("💳 استفسار عن الدفع", url=CONTACT_URL)],
                [InlineKeyboardButton("⬅️ رجوع للخدمات", callback_data="services")],
            ]
        )
        await query.message.reply_text(text, reply_markup=keyboard)
        return

    if data.startswith("order:"):
        await start_order(update, context, int(data.split(":", 1)[1]))
        return

    # 3. السبحة الإلكترونية التفاعلية
    if data == "tasbeeh":
        await query.message.reply_text(
            "📿 **السبحة الإلكترونية:**\nاضغط على العداد للتسبيح، أو اختر الذكر المفضل:",
            reply_markup=tasbeeh_keyboard(0, "سبحان الله"),
            parse_mode="Markdown",
        )
        return

    if data.startswith("tasbeeh_count:"):
        _, current_count, phrase = data.split(":", 2)
        new_count = int(current_count) + 1
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(new_count, phrase))
        return

    if data.startswith("tasbeeh_set:"):
        _, _, phrase = data.split(":", 2)
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(0, phrase))
        return

    if data.startswith("tasbeeh_reset:"):
        phrase = data.split(":", 1)[1]
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(0, phrase))
        return

    # 4. معرض الأعمال (Portfolio)
    if data == "portfolio":
        keyboard, rows = portfolio_keyboard()
        if not rows:
            await query.message.reply_text(
                "🎨 مرحباً بكم في معرض أعمال Dua Space!\nيجري حالياً رفع نماذج الأعمال والتصاميم المميزة قريباً جداً 🪐",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")]]),
            )
        else:
            await query.message.reply_text("🎨 نماذج من أعمال وتصاميم Dua Space:\nيرجى اختيار العمل لمشاهدته:", reply_markup=keyboard)
        return

    if data.startswith("view_port:"):
        port_id = int(data.split(":", 1)[1])
        item = db_one("SELECT * FROM portfolio WHERE id = ?", (port_id,))
        if item:
            caption = f"🎨 **{item['title']}**\n\n{item['description']}"
            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=item["file_id"],
                    caption=caption,
                    parse_mode="Markdown",
                )
            except Exception:
                await query.message.reply_text(caption)
        return

    # 5. المكتبة
    if data == "library":
        keyboard, rows = library_keyboard()
        if not rows:
            await query.message.reply_text(
                "📚 مكتبة Dua Space الرقمية.\nيجري تجهيز باقة الكتب حالياً وستكون متاحة للتحميل قريباً جداً 🪐",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")]]),
            )
        else:
            await query.message.reply_text("📚 قائمة الكتب المتاحة للقراءة والتحميل:", reply_markup=keyboard)
        return

    if data.startswith("book:"):
        book_id = int(data.split(":", 1)[1])
        book = db_one("SELECT * FROM books WHERE id = ?", (book_id,))
        if book:
            caption = f"📖 كتاب: {book['title']}\n✍️ المؤلف: {book['author']}\n\n{book['description']}"
            if book["file_id"]:
                try:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=book["file_id"],
                        caption=caption,
                    )
                except Exception:
                    await query.message.reply_text(caption)
            else:
                await query.message.reply_text(caption)
        return

    # 6. الأذكار والسيرة
    if data == "adhkar_menu":
        await query.message.reply_text("📿 حصن المسلم - يرجى اختيار باب الأذكار المطلوب:", reply_markup=adhkar_keyboard())
        return

    if data.startswith("zekr:"):
        zekr_id = int(data.split(":", 1)[1])
        zekr = db_one("SELECT * FROM adhkar WHERE id = ?", (zekr_id,))
        if zekr:
            await query.message.reply_text(
                zekr["content"],
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ العودة للأذكار", callback_data="adhkar_menu")]]),
            )
        return

    if data == "seerah_menu":
        await query.message.reply_text(
            "📜 السيرة النبوية العطرة - على صاحبها أفضل الصلاة وأتم التسليم:\nيرجى اختيار المحطة التاريخية:",
            reply_markup=seerah_keyboard(),
        )
        return

    if data.startswith("seerah_part:"):
        part_id = int(data.split(":", 1)[1])
        part = db_one("SELECT * FROM seerah WHERE id = ?", (part_id,))
        if part:
            await query.message.reply_text(
                part["content"],
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ العودة لمحطات السيرة", callback_data="seerah_menu")]]),
            )
        return

    # 7. التقييمات (Reviews)
    if data == "reviews_list":
        rows = db_all("SELECT user_name, rating, comment, created_at FROM reviews ORDER BY id DESC LIMIT 10")
        if not rows:
            review_text = "⭐ لا توجد تقييمات مسجلة بعد. كونوا أول من يشاركنا رأيه!"
        else:
            review_text = "⭐ **آراء وتجارب عملائنا الكرام:**\n\n"
            for r in rows:
                stars = "⭐" * r["rating"]
                review_text += f"{r['user_name'] or 'عميل'}: {stars}\n«{r['comment']}»\n—\n"

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✍️ شاركنا برأيك وتقييمك", callback_data="add_review")],
                [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
            ]
        )
        await query.message.reply_text(review_text, reply_markup=keyboard, parse_mode="Markdown")
        return

    if data == "add_review":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⭐ 1", callback_data="rate:1"),
                    InlineKeyboardButton("⭐⭐ 2", callback_data="rate:2"),
                    InlineKeyboardButton("⭐⭐⭐ 3", callback_data="rate:3"),
                    InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data="rate:4"),
                    InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data="rate:5"),
                ],
                [InlineKeyboardButton("⬅️ إلغاء", callback_data="reviews_list")],
            ]
        )
        await query.message.reply_text("يرجى اختيار تقييمك من 1 إلى 5 نجوم:", reply_markup=keyboard)
        return

    if data.startswith("rate:"):
        rating = int(data.split(":", 1)[1])
        context.user_data["flow"] = {"kind": "review_comment", "rating": rating}
        await query.message.reply_text("نسعد برأيكم دائماً! يرجى كتابة تعليقكم أو رأيكم في رسالة واحدة:")
        return

    # 8. الفائدة والأسئلة الشائعة
    if data == "daily_quote":
        selected_quote = random.choice(QUOTES)
        await query.message.reply_text(
            f"✨ **فائدة / إشراقة اليوم:**\n\n{selected_quote}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔄 فائدة أخرى", callback_data="daily_quote")],
                    [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
                ]
            ),
        )
        return

    if data == "faq":
        await query.message.reply_text(
            FAQ_TEXT,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")]]),
        )
        return

    # -------------------- أوامر الإدارة الحصرية --------------------
    if not admin:
        await query.message.reply_text("عذرًا، هذا الخيار مخصص لإدارة Dua Space.")
        return

    if data == "admin_home":
        context.user_data.pop("flow", None)
        await query.message.reply_text("🎛️ لوحة إدارة Dua Space:", reply_markup=admin_keyboard())

    elif data == "admin_users":
        await show_users_list(query.message, context)

    elif data == "admin_broadcast":
        context.user_data["flow"] = {"kind": "broadcast_message"}
        await query.message.reply_text(
            "📢 **نظام الإذاعة العامة:**\n"
            "يرجى إرسال الرسالة التي تودين بثها لجميع مستخدمي البوت.\n"
            "(للإلغاء أرسلي /cancel)"
        )

    # إدارة المعرض
    elif data == "admin_portfolio":
        rows = db_all("SELECT id, title FROM portfolio ORDER BY id DESC LIMIT 20")
        buttons = [
            [InlineKeyboardButton(f"🗑️ حذف: {row['title'][:35]}", callback_data=f"delport:{row['id']}")]
            for row in rows
        ]
        buttons.append([InlineKeyboardButton("➕ إضافة عمل جديد للمعرض", callback_data="add_port")])
        buttons.append([InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")])
        await query.message.reply_text("🎨 إدارة معرض الأعمال:\nيمكنك إضافة عمل جديد بصورة أو حذف أعمال سابقة:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "add_port":
        context.user_data["flow"] = {"kind": "port_title"}
        await query.message.reply_text("يرجى كتابة عنوان العمل أو التصميم:\n(للإلغاء أرسل /cancel)")

    elif data.startswith("delport:"):
        port_id = int(data.split(":", 1)[1])
        db_execute("DELETE FROM portfolio WHERE id = ?", (port_id,))
        await query.message.reply_text("✅ تم حذف العمل من المعرض بنجاح.", reply_markup=admin_keyboard())

    # إدارة الخدمات
    elif data == "admin_services":
        await query.message.reply_text(
            "🛍️ إدارة الخدمات:\nيرجى اختيار خدمة للتعديل أو إضافة خدمة جديدة.",
            reply_markup=admin_services_keyboard(),
        )

    elif data == "svc_add":
        context.user_data["pending_service"] = {}
        context.user_data["flow"] = {"kind": "add_title"}
        await query.message.reply_text("يرجى إرسال اسم الخدمة الجديدة.\nللإلغاء يرجى كتابة /cancel.")

    elif data.startswith("svcadmin:"):
        service_id = int(data.split(":", 1)[1])
        service = db_one("SELECT * FROM services WHERE id = ?", (service_id,))
        if service:
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
                        InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"svcedit_title:{service_id}"),
                        InlineKeyboardButton("✏️ تعديل الوصف", callback_data=f"svcedit_desc:{service_id}"),
                    ],
                    [
                        InlineKeyboardButton("💰 تعديل السعر", callback_data=f"svcedit_price:{service_id}"),
                        InlineKeyboardButton("⏯️ تفعيل/إيقاف", callback_data=f"svctoggle:{service_id}"),
                    ],
                    [
                        InlineKeyboardButton("🗑️ حذف الخدمة", callback_data=f"svcdelete:{service_id}"),
                        InlineKeyboardButton("⬅️ قائمة الخدمات", callback_data="admin_services"),
                    ],
                ]
            )
            await query.message.reply_text(text, reply_markup=keyboard)

    elif data.startswith("svctoggle:"):
        service_id = int(data.split(":", 1)[1])
        row = db_one("SELECT active FROM services WHERE id = ?", (service_id,))
        if row:
            db_execute("UPDATE services SET active = ? WHERE id = ?", (0 if row["active"] else 1, service_id))
        await query.message.reply_text("✅ تم تحديث حالة الخدمة بنجاح.", reply_markup=admin_services_keyboard())

    elif data.startswith("svcdelete:"):
        service_id = int(data.split(":", 1)[1])
        db_execute("DELETE FROM services WHERE id = ?", (service_id,))
        await query.message.reply_text("✅ تم حذف الخدمة بنجاح.", reply_markup=admin_services_keyboard())

    elif data.startswith("svcedit_title:"):
        context.user_data["flow"] = {"kind": "edit_title", "service_id": int(data.split(":", 1)[1])}
        await query.message.reply_text("يرجى إرسال الاسم الجديد للخدمة:")

    elif data.startswith("svcedit_desc:"):
        context.user_data["flow"] = {"kind": "edit_desc", "service_id": int(data.split(":", 1)[1])}
        await query.message.reply_text("يرجى إرسال الوصف الجديد للخدمة:")

    elif data.startswith("svcedit_price:"):
        context.user_data["flow"] = {"kind": "edit_price", "service_id": int(data.split(":", 1)[1])}
        await query.message.reply_text("يرجى إرسال السعر الجديد للخدمة:")

    # إدارة المكتبة
    elif data == "admin_books":
        rows = db_all("SELECT id, title FROM books ORDER BY id DESC LIMIT 20")
        buttons = [
            [InlineKeyboardButton(f"🗑️ حذف: {row['title'][:35]}", callback_data=f"delbook:{row['id']}")]
            for row in rows
        ]
        buttons.append([InlineKeyboardButton("➕ إضافة كتاب جديد", callback_data="add_book")])
        buttons.append([InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")])
        await query.message.reply_text("📚 إدارة المكتبة:\nيمكنك إضافة كتاب جديد مع ملف PDF أو حذف كتب سابقة:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "add_book":
        context.user_data["flow"] = {"kind": "book_title"}
        await query.message.reply_text("يرجى كتابة عنوان الكتاب الجديد:")

    elif data.startswith("delbook:"):
        book_id = int(data.split(":", 1)[1])
        db_execute("DELETE FROM books WHERE id = ?", (book_id,))
        await query.message.reply_text("✅ تم حذف الكتاب بنجاح.", reply_markup=admin_keyboard())

    # إدارة السيرة والأذكار
    elif data == "admin_seerah":
        context.user_data["flow"] = {"kind": "add_seerah_title"}
        await query.message.reply_text("📜 لإضافة محطة جديدة بالسيرة، يرجى كتابة عنوان المحطة:")

    elif data == "admin_adhkar":
        context.user_data["flow"] = {"kind": "add_adhkar_cat"}
        await query.message.reply_text("📿 لإضافة ذكر جديد، يرجى كتابة اسم الباب أو التصنيف:")

    # إدارة الطلبات
    elif data == "admin_orders":
        rows = db_all("SELECT id, service_title, status, created_at FROM orders ORDER BY id DESC LIMIT 20")
        if not rows:
            await query.message.reply_text(
                "لا توجد طلبات مسجلة حتى الآن.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")]]),
            )
            return

        buttons = [
            [InlineKeyboardButton(f"#{row['id']} | {row['status']} | {row['service_title'][:30]}", callback_data=f"orderadmin:{row['id']}")]
            for row in rows
        ]
        buttons.append([InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")])
        await query.message.reply_text("📥 قائمة آخر الطلبات الواردة:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("orderadmin:"):
        order_id = int(data.split(":", 1)[1])
        order = db_one("SELECT * FROM orders WHERE id = ?", (order_id,))
        if not order:
            await query.message.reply_text("الطلب غير موجود.")
            return

        username = f"@{order['username']}" if order["username"] else "بدون معرّف"
        text = (
            f"📥 الطلب رقم #{order['id']}\n\n"
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
                    InlineKeyboardButton("✅ قبول", callback_data=f"ordstatus:{order_id}:accepted"),
                    InlineKeyboardButton("🛠️ قيد التنفيذ", callback_data=f"ordstatus:{order_id}:working"),
                ],
                [
                    InlineKeyboardButton("🎉 مكتمل", callback_data=f"ordstatus:{order_id}:done"),
                    InlineKeyboardButton("❌ اعتذار/رفض", callback_data=f"ordstatus:{order_id}:rejected"),
                ],
                [InlineKeyboardButton("⬅️ كل الطلبات", callback_data="admin_orders")],
            ]
        )
        await query.message.reply_text(text, reply_markup=keyboard)

    elif data.startswith("ordstatus:"):
        _, raw_id, status_key = data.split(":", 2)
        order_id = int(raw_id)
        status_map = {
            "accepted": "مقبول",
            "working": "قيد التنفيذ",
            "done": "مكتمل",
            "rejected": "معتذر عنه",
        }
        new_status = status_map.get(status_key, "قيد المراجعة")
        row = db_one("SELECT user_id, service_title FROM orders WHERE id = ?", (order_id,))
        if row:
            db_execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
            try:
                await context.bot.send_message(
                    chat_id=row["user_id"],
                    text=f"تحديث بخصوص طلبكم رقم #{order_id} لخدمة ({row['service_title']}):\nالحالة الحالية هي: «{new_status}».",
                )
            except Exception:
                pass
            await query.message.reply_text(f"✅ تم تحديث حالة الطلب #{order_id} إلى: {new_status}")
            await query.message.reply_text("🎛️ لوحة إدارة Dua Space:", reply_markup=admin_keyboard())

    elif data == "admin_stats":
        users_count = db_one("SELECT COUNT(*) AS n FROM users")["n"]
        total_orders = db_one("SELECT COUNT(*) AS n FROM orders")["n"]
        new_orders = db_one("SELECT COUNT(*) AS n FROM orders WHERE status = 'جديد'")["n"]
        active_services = db_one("SELECT COUNT(*) AS n FROM services WHERE active = 1")["n"]
        books_count = db_one("SELECT COUNT(*) AS n FROM books")["n"]
        port_count = db_one("SELECT COUNT(*) AS n FROM portfolio")["n"]

        text = (
            "📊 **إحصائيات Dua Space الشاملة:**\n\n"
            f"• عدد مستخدمي البوت: {users_count}\n"
            f"• إجمالي الطلبات: {total_orders}\n"
            f"• الطلبات الجديدة: {new_orders}\n"
            f"• الخدمات المفعلة: {active_services}\n"
            f"• الكتب في المكتبة: {books_count}\n"
            f"• الأعمال في المعرض: {port_count}\n"
        )
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")]]))

    elif data == "admin_settings":
        welcome = get_setting("welcome_msg", DEFAULT_WELCOME)
        footer = get_setting("footer", DEFAULT_FOOTER)
        text = (
            "⚙️ **إعدادات النصوص الحالية:**\n\n"
            f"**رسالة الترحيب:**\n{welcome[:1000]}\n\n"
            f"**توقيع المنشورات:**\n{footer[:300]}"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✏️ تعديل الترحيب", callback_data="edit_welcome")],
                [InlineKeyboardButton("✏️ تعديل توقيع المنشورات", callback_data="edit_footer")],
                [InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")],
            ]
        )
        await query.message.reply_text(text, reply_markup=keyboard)

    elif data == "edit_welcome":
        context.user_data["flow"] = {"kind": "edit_welcome"}
        await query.message.reply_text("يرجى إرسال نص رسالة الترحيب الجديدة:")

    elif data == "edit_footer":
        context.user_data["flow"] = {"kind": "edit_footer"}
        await query.message.reply_text("يرجى إرسال توقيع المنشورات الجديد، أو إرسال شرطة واحدة (-) لإلغائه:")

    elif data == "publish_help":
        await query.message.reply_text(
            "📢 **دليل النشر المباشر في القناة:**\n\n"
            "• للنشر النصي المباشر: أرسل الأمر مع النص، مثال:\n"
            "`/publish مرحباً بكم في Dua Space`\n\n"
            "• للنشر مع التثبيت: استخدم الأمر `/pin` ثم النص.\n\n"
            "• لنشر صورة أو تصميم أو ملف PDF: أرسله للبوت مباشرة مع التعليق وسينشر فوراً بالقناة مع التوقيع."
        )


# -------------------- البحث الذكي ومعالجة النصوص --------------------

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not message.text:
        return

    flow = context.user_data.get("flow")

    # 1. إرسال تعليق التقييم
    if flow and flow.get("kind") == "review_comment":
        rating = flow.get("rating", 5)
        comment = message.text.strip()
        user_name = user.first_name or "عميل مجهول"
        db_execute(
            "INSERT INTO reviews(user_id, user_name, rating, comment) VALUES(?, ?, ?, ?)",
            (user.id, user_name, rating, comment),
        )
        context.user_data.pop("flow", None)
        await message.reply_text(
            "🌟 شكراً جزيلاً لمشاركتنا تقييمكم ورأيكم! نقدر ثقتكم دائماً.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # 2. تفاصيل الطلب
    if flow and flow.get("kind") == "order_details":
        await handle_order_text(update, context, flow)
        return

    # 3. عمليات الإدارة النصية
    if is_admin_user(user.id) and flow:
        kind = flow.get("kind")
        val = message.text.strip()

        # الإذاعة العامة
        if kind == "broadcast_message":
            users = db_all("SELECT user_id FROM users")
            context.user_data.pop("flow", None)
            sent_count = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u["user_id"], text=val)
                    sent_count += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    pass
            await message.reply_text(f"📢 تمت الإذاعة بنجاح! وصلت الرسالة إلى {sent_count} مستخدم.", reply_markup=admin_keyboard())
            return

        # إضافة المعرض
        elif kind == "port_title":
            context.user_data["pending_portfolio"] = {"title": val}
            context.user_data["flow"] = {"kind": "port_desc"}
            await message.reply_text("يرجى كتابة وصف موجز للتصميم أو العمل (أو إرسال -):")
            return

        elif kind == "port_desc":
            context.user_data["pending_portfolio"]["description"] = "" if val == "-" else val
            context.user_data["flow"] = {"kind": "port_file"}
            await message.reply_text("يرجى الآن إرسال صورة التصميم مباشرة في المحادثة:")
            return

        # إضافة خدمة
        elif kind == "add_title":
            context.user_data.setdefault("pending_service", {})["title"] = val
            context.user_data["flow"] = {"kind": "add_desc"}
            await message.reply_text("يرجى كتابة وصف الخدمة بإيجاز (أو إرسال - إذا لم يتوفر وصف):")
            return

        elif kind == "add_desc":
            context.user_data.setdefault("pending_service", {})["description"] = "" if val == "-" else val
            context.user_data["flow"] = {"kind": "add_price"}
            await message.reply_text("يرجى تحديد السعر أو كتابة: حسب تفاصيل الطلب:")
            return

        elif kind == "add_price":
            pending = context.user_data.get("pending_service", {})
            db_execute(
                "INSERT INTO services(title, description, price, active) VALUES(?, ?, ?, 1)",
                (pending.get("title", "خدمة جديدة"), pending.get("description", ""), val or "حسب الطلب"),
            )
            context.user_data.pop("flow", None)
            context.user_data.pop("pending_service", None)
            await message.reply_text("✅ تمت إضافة الخدمة بنجاح.", reply_markup=admin_services_keyboard())
            return

        elif kind in ("edit_title", "edit_desc", "edit_price"):
            service_id = flow.get("service_id")
            column = {"edit_title": "title", "edit_desc": "description", "edit_price": "price"}[kind]
            db_execute(f"UPDATE services SET {column} = ? WHERE id = ?", (val, service_id))
            context.user_data.pop("flow", None)
            await message.reply_text("✅ تم حفظ التعديل بنجاح.", reply_markup=admin_services_keyboard())
            return

        # إضافة كتاب
        elif kind == "book_title":
            context.user_data["pending_book"] = {"title": val}
            context.user_data["flow"] = {"kind": "book_author"}
            await message.reply_text("يرجى كتابة اسم المؤلف:")
            return

        elif kind == "book_author":
            context.user_data["pending_book"]["author"] = val
            context.user_data["flow"] = {"kind": "book_desc"}
            await message.reply_text("يرجى كتابة نبذة مختصرة عن الكتاب:")
            return

        elif kind == "book_desc":
            context.user_data["pending_book"]["description"] = val
            context.user_data["flow"] = {"kind": "book_file"}
            await message.reply_text("يرجى الآن إرسال ملف الكتاب (PDF) في المحادثة، أو إرسال كلمة (بدون):")
            return

        elif kind == "book_file" and val == "بدون":
            p = context.user_data.pop("pending_book", {})
            context.user_data.pop("flow", None)
            db_execute(
                "INSERT INTO books(title, author, description, file_id) VALUES(?, ?, ?, NULL)",
                (p.get("title"), p.get("author"), p.get("description")),
            )
            await message.reply_text("✅ تمت إضافة الكتاب إلى المكتبة بنجاح.", reply_markup=admin_keyboard())
            return

        # إضافة سيرة وأذكار
        elif kind == "add_seerah_title":
            context.user_data["pending_seerah"] = {"title": val}
            context.user_data["flow"] = {"kind": "add_seerah_content"}
            await message.reply_text("يرجى كتابة النص الكامل لهذه المحطة النبوية:")
            return

        elif kind == "add_seerah_content":
            p = context.user_data.pop("pending_seerah", {})
            context.user_data.pop("flow", None)
            db_execute("INSERT INTO seerah(title, content) VALUES(?, ?)", (p.get("title"), val))
            await message.reply_text("✅ تم حفظ المحطة النبوية بنجاح.", reply_markup=admin_keyboard())
            return

        elif kind == "add_adhkar_cat":
            context.user_data["pending_adhkar"] = {"category": val}
            context.user_data["flow"] = {"kind": "add_adhkar_content"}
            await message.reply_text("يرجى كتابة نصوص الأدعية والأذكار لهذا الباب:")
            return

        elif kind == "add_adhkar_content":
            p = context.user_data.pop("pending_adhkar", {})
            context.user_data.pop("flow", None)
            db_execute("INSERT INTO adhkar(category, content) VALUES(?, ?)", (p.get("category"), val))
            await message.reply_text("✅ تمت إضافة باب الأذكار بنجاح.", reply_markup=admin_keyboard())
            return

        elif kind == "edit_welcome":
            set_setting("welcome_msg", val)
            context.user_data.pop("flow", None)
            await message.reply_text("✅ تم تحديث رسالة الترحيب بنجاح.", reply_markup=admin_keyboard())
            return

        elif kind == "edit_footer":
            set_setting("footer", "" if val == "-" else "\n\n" + val)
            context.user_data.pop("flow", None)
            await message.reply_text("✅ تم حفظ توقيع المنشورات بنجاح.", reply_markup=admin_keyboard())
            return

    # 4. محرك البحث الذكي التلقائي (يبحث في الكتب والأذكار والسيرة)
    search_term = message.text.strip()
    if len(search_term) >= 2 and not is_admin_user(user.id):
        books_found = db_all("SELECT id, title FROM books WHERE title LIKE ? OR author LIKE ?", (f"%{search_term}%", f"%{search_term}%"))
        adhkar_found = db_all("SELECT id, category FROM adhkar WHERE category LIKE ? OR content LIKE ?", (f"%{search_term}%", f"%{search_term}%"))
        seerah_found = db_all("SELECT id, title FROM seerah WHERE title LIKE ? OR content LIKE ?", (f"%{search_term}%", f"%{search_term}%"))

        if books_found or adhkar_found or seerah_found:
            results_buttons = []
            for b in books_found[:3]:
                results_buttons.append([InlineKeyboardButton(f"📖 كتاب: {b['title']}", callback_data=f"book:{b['id']}")])
            for a in adhkar_found[:3]:
                results_buttons.append([InlineKeyboardButton(f"🌸 ذكر: {a['category']}", callback_data=f"zekr:{a['id']}")])
            for s in seerah_found[:3]:
                results_buttons.append([InlineKeyboardButton(f"📜 سيرة: {s['title']}", callback_data=f"seerah_part:{s['id']}")])

            results_buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
            await message.reply_text(f"🔍 نتائج البحث عن «{search_term}»:", reply_markup=InlineKeyboardMarkup(results_buttons))
            return

    if is_admin_user(user.id):
        await message.reply_text(
            "لم يتم نشر هذه الرسالة لأن النشر المباشر يتطلب الأمر `/publish`.\n"
            "يرجى إرسال `/admin` لفتح لوحة التحكم، أو `/cancel` لإلغاء أي خطوة معلقة."
        )


# -------------------- معالجة الصور والملفات --------------------

async def file_and_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return

    flow = context.user_data.get("flow")

    # رفع صورة للمعرض
    if flow and flow.get("kind") == "port_file" and update.effective_message.photo:
        photo = update.effective_message.photo[-1]
        p = context.user_data.pop("pending_portfolio", {})
        context.user_data.pop("flow", None)

        db_execute(
            "INSERT INTO portfolio(title, description, file_id, media_type) VALUES(?, ?, ?, 'photo')",
            (p.get("title", "عمل جديد"), p.get("description", ""), photo.file_id),
        )
        await update.effective_message.reply_text("✅ تمت إضافة العمل بنجاح إلى معرض الأعمال!", reply_markup=admin_keyboard())
        return

    # رفع ملف كتاب PDF
    if flow and flow.get("kind") == "book_file" and update.effective_message.document:
        doc = update.effective_message.document
        p = context.user_data.pop("pending_book", {})
        context.user_data.pop("flow", None)

        db_execute(
            "INSERT INTO books(title, author, description, file_id) VALUES(?, ?, ?, ?)",
            (p.get("title", doc.file_name or "كتاب جديد"), p.get("author", "غير محدد"), p.get("description", ""), doc.file_id),
        )
        await update.effective_message.reply_text("✅ تم حفظ ملف الكتاب وربطه بالمكتبة بنجاح!", reply_markup=admin_keyboard())
        return

    if flow:
        await update.effective_message.reply_text(
            "يرجى استكمال الخطوة الجارية أولاً أو إرسال /cancel للإلغاء.\nتم إيقاف النشر التلقائي لتفادي الأخطاء."
        )
        return

    # نشر الوسائط مباشرة في القناة
    try:
        await context.bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
        )
        await update.effective_message.reply_text("✅ تم نشر الملف/الوسيط في القناة بنجاح.")
    except Exception as exc:
        logger.exception("Media publishing failed")
        await update.effective_message.reply_text(f"❌ تعذر نشر الملف بالقناة.\nالتفاصيل: {str(exc)[:400]}")


# -------------------- أوامر القناة --------------------

def add_footer(text):
    footer = get_setting("footer", DEFAULT_FOOTER)
    return f"{text}{footer}" if footer else text


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("يرجى كتابة النص بعد الأمر: /publish النص")
        return
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=add_footer(text))
        await update.effective_message.reply_text("✅ تم نشر المنشور في القناة بنجاح.")
    except Exception as exc:
        logger.exception("Publishing failed")
        await update.effective_message.reply_text(f"❌ تعذر النشر في القناة.\nالتفاصيل: {str(exc)[:400]}")


async def post_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("يرجى كتابة النص بعد الأمر: /pin النص")
        return
    try:
        sent = await context.bot.send_message(chat_id=CHANNEL_ID, text=add_footer(text))
        await context.bot.pin_chat_message(chat_id=CHANNEL_ID, message_id=sent.message_id)
        await update.effective_message.reply_text("📌 تم نشر الرسالة وتثبيتها في أعلى القناة.")
    except Exception as exc:
        logger.exception("Pinning failed")
        await update.effective_message.reply_text(f"❌ تعذر التثبيت.\nالتفاصيل: {str(exc)[:400]}")


async def set_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return
    val = " ".join(context.args).strip()
    if not val:
        await update.effective_message.reply_text("يرجى كتابة النص بعد الأمر: /set_welcome النص")
        return
    set_setting("welcome_msg", val)
    await update.effective_message.reply_text("✅ تم حفظ رسالة الترحيب.")


async def set_footer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return
    val = " ".join(context.args).strip()
    if not val:
        await update.effective_message.reply_text("يرجى كتابة التوقيع بعد الأمر أو /set_footer - لإلغائه.")
        return
    set_setting("footer", "" if val == "-" else "\n\n" + val)
    await update.effective_message.reply_text("✅ تم حفظ توقيع المنشورات.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return
    users_count = db_one("SELECT COUNT(*) AS n FROM users")["n"]
    total_orders = db_one("SELECT COUNT(*) AS n FROM orders")["n"]
    await update.effective_message.reply_text(f"📊 إجمالي المستخدمين: {users_count}\n📥 إجمالي الطلبات: {total_orders}")


# -------------------- خادم الويب (Render Web Service) --------------------

async def handle_health(request):
    return web.Response(text="Dua Space bot is running with advanced features 🪐", status=200)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled error: %s", context.error, exc_info=context.error)


# -------------------- نقطة التشغيل الرئيسية --------------------

async def main():
    if not BOT_TOKEN or not CHANNEL_ID or not ADMIN_ID:
        raise RuntimeError("يرجى التأكد من ضبط متغيرات البيئة BOT_TOKEN و CHANNEL_ID و ADMIN_ID في Render.")

    init_db()

    web_app = web.Application()
    web_app.router.add_get("/", handle_health)
    web_app.router.add_get("/health", handle_health)

    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Web health server listening on port %s", port)

    application = Application.builder().token(BOT_TOKEN).build()

    # الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", lambda u, c: u.effective_message.reply_text("🎛️ لوحة إدارة Dua Space:", reply_markup=admin_keyboard()) if is_admin_user(u.effective_user.id) else None))
    application.add_handler(CommandHandler("users", lambda u, c: show_users_list(u.effective_message, c) if is_admin_user(u.effective_user.id) else None))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("publish", publish))
    application.add_handler(CommandHandler("pin", post_pin))
    application.add_handler(CommandHandler("set_welcome", set_welcome_command))
    application.add_handler(CommandHandler("set_footer", set_footer_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # الأزرار والرسائل
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    application.add_handler(MessageHandler(filters.ATTACHMENT, file_and_media_handler))

    application.add_error_handler(error_handler)

    initialized = False
    try:
        await application.initialize()
        initialized = True
        await application.start()

        if application.updater is None:
            raise RuntimeError("Telegram updater غير متاح.")

        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Dua Space advanced bot is running.")
        await asyncio.Event().wait()

    finally:
        try:
            if application.updater and application.updater.running:
                await application.updater.stop()
            if application.running:
                await application.stop()
            if initialized:
                await application.shutdown()
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
