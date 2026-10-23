import asyncio
import json
import logging
import os
import random
import sqlite3
from datetime import datetime

from aiohttp import web
from telegram import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# -------------------- الإعدادات الأساسية --------------------

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("DuaSpaceUltimateControlBot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@DuaSpace1").strip()

try:
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "0").strip())
except ValueError:
    ADMIN_ID = 0

CONTACT_USERNAME = os.environ.get("CONTACT_USERNAME", "xdua1").strip().lstrip("@")
DB_PATH = os.environ.get("DATABASE_PATH", "duaspace.db")
CONTACT_URL = f"https://t.me/{CONTACT_USERNAME}"
CHANNEL_URL = "https://t.me/DuaSpace1"
BOT_USERNAME = os.environ.get("BOT_USERNAME", "DuaSpaceHelperBot").strip().lstrip("@")

# -------------------- القرآن الكريم (114 سورة) --------------------

QURAN_SURAHS = [
    "الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام", "الأعراف", "الأنفال", "التوبة", "يونس",
    "هود", "يوسف", "الرعد", "إبراهيم", "الحجر", "النحل", "الإسراء", "الكهف", "مريم", "طه",
    "الأنبياء", "الحج", "المؤمنون", "النور", "الفرقان", "الشعراء", "النمل", "القصص", "العنكبوت", "الروم",
    "لقمان", "السجدة", "الأحزاب", "سبأ", "فاطر", "يس", "الصافات", "ص", "الزمر", "غافر",
    "فصلت", "الشورى", "الزخرف", "الدخان", "الجاثية", "الأحقاف", "محمد", "الفتح", "الحجرات", "ق",
    "الذاريات", "الطور", "النجم", "القمر", "الرحمن", "الواقعة", "الحديد", "المجادلة", "الحشر", "الممتحنة",
    "الصف", "الجمعة", "المنافقون", "التغابن", "الطلاق", "التحريم", "الملك", "القلم", "الحاقة", "المعارج",
    "نوح", "الجن", "المزمل", "المدثر", "القيامة", "الإنسان", "المرسلات", "النبأ", "النازعات", "عبس",
    "التكوير", "الانفطار", "المطففين", "الانشقاق", "البروج", "الطارق", "الأعلى", "الغاشية", "الفجر", "البلد",
    "الشمس", "الليل", "الضحى", "الشرح", "التين", "العلق", "القدر", "البينة", "الزلزلة", "العاديات",
    "القارعة", "التكاثر", "العصر", "الهمزة", "الفيل", "قريش", "الماعون", "الكوثر", "الكافرون", "النصر",
    "المسد", "الإخلاص", "الفلق", "الناس"
]

OFFICIAL_LAUNCH_POST = (
    "🪐 انطلاقة جديدة ومساحة متكاملة بين أيديكم!\n\n"
    "يسرّنا أن نعلن لكم رسميًا عن إطلاق وتحديث بوت Dua Space الشامل | بوابتكم الذكية للمعرفة، الإبداع، والارتقاء ✨\n\n"
    "سواء كنت تبحث عن مرجع دراسي، تطمح لتطوير لغاتك، تبحث عن حلول وتصاميم مميزة، أو تريد تحدي عقلك واختبار معلوماتك.. جمعنا كل ذلك في مكان واحد:\n\n"
    "✨ ماذا ينتظركم داخل البوت؟\n"
    "• 📖 القرآن الكريم كاملاً (114 سورة) تلاوة وتفسيراً.\n"
    "• 📐 الصرح الهندسي والتقني: طبية حيوية، برمجيات وذكاء اصطناعي، مدنية، كهربائية، وميكانيكية.\n"
    "• 🩺 مكتبات تخصصية مجانية: طب، لغات، علم نفس شامل، فكر وفلسفة، وروايات عالمية.\n"
    "• 🧠 بنك تحديات الذكاء، تدريب المخ، وألغاز الرياضيات وعلم النفس.\n"
    "• 🎓 دليل المنح الدراسية العالمية والفرص التعليمية بروابطها الرسمية.\n"
    "• 🎌 عالم الأنمي والمانجا والروايات المترجمة.\n"
    "• 🛍️ خدمات التصميم الإبداعي والحلول الرقمية.\n"
    "• ⏱️ رفيق دراستك: مؤقت التركيز (Pomodoro) والسبحة الإلكترونية.\n\n"
    "🌱 هذه خطوتنا الأولى فقط! المنصة في تحديث مستمر، ونعمل دوريًا على إضافة مراجع جديدة وتوسيع الأقسام.\n\n"
    "🚀 جربوا البوت الآن وشاركوا الرابط مع أصدقائكم لتعم الفائدة:\n"
    "🤖 الرابط المباشر: @DuaSpaceHelperBot\n\n"
    "القادم أعظم وأجمل، وكونوا بالقرب دائمًا 🪐💫"
)

AUTO_POSTS = [
    "﴿أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ﴾ ✨\n\nسبحان الله، والحمد لله، ولا إله إلا الله، والله أكبر.",
    "﴿وَتَوَكَّلْ عَلَى الْعَزِيزِ الرَّحِيمِ * الَّذِي يَرَاكَ حِينَ تَقُومُ﴾ 🪐",
    "قال رسول الله ﷺ: «مَن سَلَكَ طَرِيقًا يَلْتَمِسُ فِيهِ عِلْمًا، سَهَّلَ اللَّهُ له به طَرِيقًا إلى الجَنَّةِ». 🌿",
    "قال رسول الله ﷺ: «إنَّ اللهَ يُحِبُّ إذا عمِلَ أحَدُكُم عمَلًا أنْ يُتْقِنَه». 💫",
    "«لا يقاس النجاح بالموقع الذي يتبوأه المرء في حياته، بقدر ما يقاس بالصعاب التي تغلب عليها.» — بوكر واشنطن",
    "«العقل الذي يتسع لفكرة جديدة لا يعود أبداً إلى حجمه الأصلي.» — أوليفر وندل هولمز 💡",
    "«كن أنت التغيير الذي تريد أن تراه في هذا العالم.» — غاندي ✨",
    "﴿إِنَّ مَعَ الْعُسْرِ يُسْرًا﴾ 🌸",
]

DEFAULT_SERVICES = [
    ("🎨 التصميم الجرافيكي والهويات البصرية", "تصميم شعارات احترافية، بطاقات وهوية بصرية متكاملة لمشروعك.", "حسب تفاصيل الطلب"),
    ("🖼️ تصميم بوسترات وبنرات إعلانية", "تصاميم لمنصات التواصل الاجتماعي بجودة وإتقان عالي.", "حسب تفاصيل الطلب"),
    ("💌 بطاقات التهنئة والدعوات الرقمية", "تصاميم مخصصة ومبتكرة للمناسبات الخاصة والاحتفالات.", "حسب تفاصيل الطلب"),
    ("📦 طلب تصميم وحلول مخصصة", "أرسل فكرتك ومتطلباتك ليتم تقدير التكلفة والوقت المناسب.", "يحدد بعد مراجعة الطلب"),
]

# -------------------- قاعدة البيانات --------------------

def db_connect():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def db_execute(sql, params=()):
    con = db_connect()
    try:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

def db_one(sql, params=()):
    con = db_connect()
    try:
        return con.execute(sql, params).fetchone()
    finally:
        con.close()

def db_all(sql, params=()):
    con = db_connect()
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()

def get_setting(key, default_val=""):
    row = db_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default_val

def set_setting(key, val):
    db_execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, val)
    )

def init_db():
    con = db_connect()
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                btn_url TEXT DEFAULT NULL,
                position INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                quiz_score INTEGER DEFAULT 0,
                warns INTEGER DEFAULT 0,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price TEXT NOT NULL DEFAULT 'حسب الطلب',
                active INTEGER NOT NULL DEFAULT 1
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
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT 'غير محدد',
                description TEXT NOT NULL DEFAULT '',
                file_id TEXT,
                url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL,
                answer_index INTEGER NOT NULL,
                explanation TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                file_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        con.commit()

        # ضبط رسالة الترحيب
        welcome_default = (
            "أهلًا بكم في Dua Space! 🪐\n"
            "مساحتكم الشاملة للإبداع، المعرفة، والارتقاء.\n"
            "يرجى اختيار القسم المطلوب عبر الأزرار أدناه:"
        )
        if not con.execute("SELECT key FROM settings WHERE key = 'welcome_msg'").fetchone():
            con.execute("INSERT INTO settings(key, value) VALUES('welcome_msg', ?)", (welcome_default,))

        # الأقسام المخصصة الافتراضية إذا كان الجدول فارغاً
        if con.execute("SELECT COUNT(*) as n FROM sections").fetchone()["n"] == 0:
            init_secs = [
                ("✨ ركن دعاء مجاب | Dua Corner", "✨ **ركن دعاء مجاب الخاص 🪐**\n\n«أهلاً بكم في زاويتي ومساحتي الخاصة. هنا نشارك الشغف، الطموح، ورسائل ملهمة تصنع الفرق.»\n\n📌 ستجدون هنا مقالات ملهمة، ترشيحات لكتب نادرة، وتحديثات دورية تهم كل باحث عن التميز.", None, 1),
                ("🎓 دليل المنح والفرص الشامل", "🎓 **دليل المنح الدولية والفرص التعليمية الشامل:**\n\nبوابتكم للدراسة المجانية والمنح الممولة بالكامل حول العالم (بكالوريوس ودراسات عليا):\n\n• المنحة التركية (Türkiye Bursları)\n• منحة الحكومة المجرية (Stipendium Hungaricum)\n• منحة الحكومة الروسية\n• منح جامعات قطر وحمد بن خليفة\n• منصة «ادرس في السعودية» للطلاب الدوليين", None, 2),
                ("🎌 عالم الأنمي والمانجا", "🎌 **عالم الأنمي والمانجا والروايات الخفيفة:**\n\nمساحتكم الترفيهية لمتابعة أحدث فصول المانجا والروايات المترجمة لأشهر الأعمال العالمية.", None, 3)
            ]
            for t, c, u, p in init_secs:
                con.execute("INSERT INTO sections(title, content, btn_url, position) VALUES(?, ?, ?, ?)", (t, c, u, p))

        # الخدمات
        for title, desc, price in DEFAULT_SERVICES:
            exists = con.execute("SELECT id FROM services WHERE title = ?", (title,)).fetchone()
            if not exists:
                con.execute("INSERT INTO services(title, description, price, active) VALUES(?, ?, ?, 1)", (title, desc, price))

        # أسئلة الكويز التأسيسية
        if con.execute("SELECT COUNT(*) as n FROM questions").fetchone()["n"] == 0:
            init_qs = [
                ("🧠 ذكاء منطقي: ما هو الشيء الذي يملك عيناً واحدة ولكنه لا يستطيع الرؤية بها أبداً؟", ["الإبرة", "الإعصار", "المرآة", "الساعة"], 0, "الإبرة لها عين (ثقب الخيط) ولكنها لا ترى بها!"),
                ("🧩 لغز ذهني: شيء يزداد كلما أخذت ونقصت منه، فما هو؟", ["الحفرة", "العمر", "المعرفة", "المال"], 0, "الحفرة! كلما أخذت منها تراباً زاد حجمها."),
                ("📐 حساب ذهني: عدد إذا ضربته في نفسه ثم أضفت إليه خمسة أصبح الناتج 30، فما هو العدد؟", ["4", "5", "6", "25"], 1, "5 × 5 = 25، و 25 + 5 = 30."),
                ("🧠 علم نفس: ما هو المصطلح الذي يصف ميل الإنسان للبحث عما يؤكد قناعاته وتجاهل العكس؟", ["الانحياز التأكيدي (Confirmation Bias)", "تأثير الهالة", "التنافر المعرفي", "عقدة النقص"], 0, "الانحياز التأكيدي يجعل العقل يبحث فقط عما يوافق هواه ومعتقده المسبق."),
                ("🩺 في جسم الإنسان، ما العضو الذي يستهلك 20% من إجمالي الأكسجين والدم رغم صغر وزنه؟", ["الكبد", "الدماغ", "القلب", "الكليتان"], 1, "الدماغ يستهلك نحو خمس طاقة الجسم لتغذية مليارات الخلايا العصبية."),
                ("📖 سورة في القرآن الكريم تعدل قراءتها ثلث القرآن الكريم، فما هي؟", ["سورة الفاتحة", "سورة الإخلاص", "سورة الكهف", "سورة يس"], 1, "سورة الإخلاص، لاشتمالها الصافي على توحيد الله وتنزيهه.")
            ]
            for q, opts, ans, exp in init_qs:
                con.execute("INSERT INTO questions(question, options_json, answer_index, explanation) VALUES(?, ?, ?, ?)", (q, json.dumps(opts, ensure_ascii=False), ans, exp))

        # الكتب التأسيسية
        init_books = [
            ("psychology", "علم النفس المعرفي وسلوك الإنسان", "د. روبرت سولسو", "دراسة لكيفية عمل الذاكرة والتفكير والقرارات.", "https://ar.wikipedia.org/wiki/%D8%B9%D9%84%D9%85_%D8%A7%D9%84%D9%86%D9%81%D8%B3_%D8%A7%D9%84%D9%85%D8%B9%D8%B1%D9%81%D9%8A"),
            ("psychology", "سيكولوجية الجماهير", "غوستاف لوبون", "الكتاب الكلاسيكي الأهم في فهم حركة الشعوب وتفكير الجماعة.", "https://www.hindawi.org/books/64516358/"),
            ("eng_bio", "مدخل إلى الهندسة الطبية الحيوية", "John Enderle", "المرجع التأسيسي في الأجهزة الطبية والأعضاء الصناعية.", "https://www.elsevier.com/"),
            ("eng_soft", "مقدمة في الخوارزميات (Algorithms)", "Thomas H. Cormen", "الكتاب الأهم عالمياً لبناء التفكير المنطقي البرمجي.", "https://mitpress.mit.edu/"),
            ("medical", "دليل الإسعافات الأولية الشامل", "منظمة الصحة العالمية", "دليل مصور للتعامل مع الحالات الإسعافية وإنقاذ الأرواح.", "https://www.who.int/ar"),
            ("languages", "English Grammar in Use", "Raymond Murphy", "المرجع العالمي الأكثر شهرة لتعلم وضبط قواعد الإنجليزية.", "https://www.cambridge.org/"),
        ]
        for cat, b_title, b_auth, b_desc, b_url in init_books:
            if not con.execute("SELECT id FROM books WHERE title = ?", (b_title,)).fetchone():
                con.execute("INSERT INTO books(category, title, author, description, file_id, url) VALUES(?, ?, ?, ?, NULL, ?)", (cat, b_title, b_auth, b_desc, b_url))

        con.commit()
    finally:
        con.close()

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

async def is_chat_admin(chat, user_id, bot):
    if is_admin_user(user_id):
        return True
    try:
        member = await chat.get_member(user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

# -------------------- فحص الاشتراك الإجباري --------------------

async def is_user_subscribed(bot, user_id):
    if is_admin_user(user_id):
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ]
    except Exception as exc:
        logger.warning(f"Subscription check error for {user_id}: {exc}")
        return True

def force_sub_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 انضم للقناة الآن", url=CHANNEL_URL)],
            [InlineKeyboardButton("✅ تحقّق من الاشتراك", callback_data="check_subscription")],
        ]
    )

# -------------------- بناء القوائم الديناميكية --------------------

def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton("📖 القرآن الكريم كاملاً (114 سورة)", callback_data="quran_groups")],
        [
            InlineKeyboardButton("📐 الصرح الهندسي والتقني", callback_data="eng_hub_view"),
            InlineKeyboardButton("🧠 بنك تحديات الذكاء والمخ", callback_data="quiz_start"),
        ],
        [
            InlineKeyboardButton("🛍️ الخدمات والتصميم", callback_data="services"),
            InlineKeyboardButton("🎨 معرض الأعمال", callback_data="portfolio"),
        ],
        [
            InlineKeyboardButton("⏱️ مؤقت التركيز (Pomodoro)", callback_data="pomodoro_start"),
            InlineKeyboardButton("✨ اقتباسات ملهمة", callback_data="quotes"),
        ],
        [
            InlineKeyboardButton("🕌 المكتبة الإسلامية", callback_data="cat:islamic"),
            InlineKeyboardButton("🩺 المكتبة الطبية", callback_data="cat:medical"),
        ],
        [
            InlineKeyboardButton("🌍 مكتبة اللغات", callback_data="cat:languages"),
            InlineKeyboardButton("🧠 علم النفس والمجتمع", callback_data="cat:psychology"),
        ],
        [
            InlineKeyboardButton("🏛️ الفكر والفلسفة", callback_data="cat:philosophy"),
            InlineKeyboardButton("💡 تطوير الذات", callback_data="cat:selfdev"),
        ],
        [
            InlineKeyboardButton("📖 روايات وقصص", callback_data="cat:novels"),
            InlineKeyboardButton("📑 موضوعات عامة", callback_data="cat:topics"),
        ],
    ]

    # جلب الأقسام الديناميكية المضافة يدوياً من قاعدة البيانات
    custom_sections = db_all("SELECT id, title, btn_url FROM sections ORDER BY position ASC, id ASC")
    for sec in custom_sections:
        if sec["btn_url"]:
            buttons.append([InlineKeyboardButton(sec["title"], url=sec["btn_url"])])
        else:
            buttons.append([InlineKeyboardButton(sec["title"], callback_data=f"csec:{sec['id']}")])

    buttons.extend(
        [
            [
                InlineKeyboardButton("📿 السبحة الإلكترونية", callback_data="tasbeeh"),
                InlineKeyboardButton("🌟 اقتراحات الأعضاء", callback_data="recommend"),
            ],
            [
                InlineKeyboardButton("📢 مشاركة البوت", callback_data="share_bot"),
                InlineKeyboardButton("💡 الأسئلة الشائعة", callback_data="faq_info"),
            ],
            [
                InlineKeyboardButton("🔗 منصاتنا وحساباتنا", callback_data="follow_us"),
                InlineKeyboardButton("💬 التواصل المباشر", url=CONTACT_URL),
            ],
        ]
    )
    return InlineKeyboardMarkup(buttons)

def engineering_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🧬 هندسة طبية حيوية", callback_data="cat:eng_bio"),
                InlineKeyboardButton("💻 برمجيات وذكاء اصطناعي", callback_data="cat:eng_soft"),
            ],
            [
                InlineKeyboardButton("🏗️ هندسة مدنية وإنشائية", callback_data="cat:eng_civil"),
                InlineKeyboardButton("⚡ هندسة كهربائية وإلكترونية", callback_data="cat:eng_elec"),
            ],
            [
                InlineKeyboardButton("⚙️ هندسة ميكانيكية ومواد", callback_data="cat:eng_mech"),
            ],
            [
                InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"),
            ],
        ]
    )

def quran_group_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📗 سور 1 - 30 (الفاتحة إلى الروم)", callback_data="qpage:0"),
                InlineKeyboardButton("📘 سور 31 - 60 (لقمان إلى الممتحنة)", callback_data="qpage:30"),
            ],
            [
                InlineKeyboardButton("📙 سور 61 - 90 (الصف إلى البلد)", callback_data="qpage:60"),
                InlineKeyboardButton("📕 سور 91 - 114 (الشمس إلى الناس)", callback_data="qpage:90"),
            ],
            [
                InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"),
            ],
        ]
    )

def quran_page_keyboard(start_idx):
    end_idx = min(start_idx + 30, 114)
    buttons = []
    current_row = []
    for idx in range(start_idx, end_idx):
        surah_num = idx + 1
        name = QURAN_SURAHS[idx]
        current_row.append(InlineKeyboardButton(f"{surah_num}. {name}", callback_data=f"surah:{surah_num}"))
        if len(current_row) == 3:
            buttons.append(current_row)
            current_row = []
    if current_row:
        buttons.append(current_row)

    buttons.append([InlineKeyboardButton("🔙 العودة لأقسام المصحف", callback_data="quran_groups")])
    return InlineKeyboardMarkup(buttons)

def tasbeeh_keyboard(count=0, phrase="سبحان الله"):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"✨ {phrase}: {count}", callback_data=f"tcount:{count}:{phrase}")],
            [
                InlineKeyboardButton("سبحان الله", callback_data="tset:0:سبحان الله"),
                InlineKeyboardButton("الحمد لله", callback_data="tset:0:الحمد لله"),
            ],
            [
                InlineKeyboardButton("الله أكبر", callback_data="tset:0:الله أكبر"),
                InlineKeyboardButton("أستغفر الله", callback_data="tset:0:أستغفر الله"),
            ],
            [
                InlineKeyboardButton("لا حول ولا قوة إلا بالله", callback_data="tset:0:لا حول ولا قوة إلا بالله"),
            ],
            [
                InlineKeyboardButton("🔄 تصفير العداد", callback_data=f"treset:{phrase}"),
                InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"),
            ],
        ]
    )

# -------------------- لوحة تحكم الإدارة الشاملة --------------------

def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📢 نشر وتثبيت إعلان الإطلاق في القناة", callback_data="admin_pin_official"),
            ],
            [
                InlineKeyboardButton("✏️ تعديل رسالة الترحيب", callback_data="admin_edit_welcome"),
            ],
            [
                InlineKeyboardButton("➕ إضافة قسم مخصص جديد", callback_data="admin_add_section"),
                InlineKeyboardButton("🗑️ حذف قسم مخصص", callback_data="admin_del_section_list"),
            ],
            [
                InlineKeyboardButton("🧠 إضافة سؤال كويز", callback_data="admin_add_question"),
                InlineKeyboardButton("🗑️ حذف سؤال كويز", callback_data="admin_del_question_list"),
            ],
            [
                InlineKeyboardButton("📚 إضافة كتاب للمكتبات", callback_data="add_book_flow"),
                InlineKeyboardButton("🗑️ حذف كتاب من المكتبة", callback_data="admin_del_book_cats"),
            ],
            [
                InlineKeyboardButton("🎨 إضافة عمل للمعرض", callback_data="add_port_flow"),
                InlineKeyboardButton("📥 طلبات العملاء", callback_data="admin_orders"),
            ],
            [
                InlineKeyboardButton("📢 إذاعة عامة (Broadcast)", callback_data="admin_broadcast"),
                InlineKeyboardButton("👥 المستخدمين النشطين", callback_data="admin_users"),
            ],
            [
                InlineKeyboardButton("💾 تحميل نسخة قاعدة البيانات", callback_data="admin_backup"),
                InlineKeyboardButton("📢 نشر تذكير بالقناة", callback_data="admin_autopost_now"),
            ],
            [
                InlineKeyboardButton("👀 معاينة واجهة المستخدم", callback_data="home"),
            ],
        ]
    )

# -------------------- أوامر حماية وإدارة المجموعات (القروبات) --------------------

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return

    if not await is_chat_admin(chat, update.effective_user.id, context.bot):
        await msg.reply_text("❌ هذا الأمر مخصص لمشرفي المجموعة فقط.")
        return

    if not msg.reply_to_message:
        await msg.reply_text("⚠️ يرجى الرد على الرسالة التي ترغب في حذفها عبر الأمر: `/del`")
        return

    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=msg.reply_to_message.message_id)
        await context.bot.delete_message(chat_id=chat.id, message_id=msg.message_id)
    except Exception as exc:
        await msg.reply_text(f"❌ تعذر حذف الرسالة: تأكد من منح البوت صلاحية (حذف الرسائل Delete Messages).")

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return

    if not await is_chat_admin(chat, update.effective_user.id, context.bot):
        await msg.reply_text("❌ هذا الأمر مخصص لمشرفي المجموعة فقط.")
        return

    if not msg.reply_to_message:
        await msg.reply_text("⚠️ يرجى الرد على رسالة العضو المراد حظره عبر الأمر: `/ban`")
        return

    target_user = msg.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user.id)
        await msg.reply_text(f"🚫 تم حظر وطرد العضو {target_user.first_name} بنجاح من المجموعة.")
    except Exception as exc:
        await msg.reply_text(f"❌ تعذر حظر العضو: {exc}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return

    if not await is_chat_admin(chat, update.effective_user.id, context.bot):
        await msg.reply_text("❌ هذا الأمر مخصص لمشرفي المجموعة فقط.")
        return

    if not msg.reply_to_message:
        await msg.reply_text("⚠️ يرجى الرد على رسالة العضو المراد كتمه عبر الأمر: `/mute`")
        return

    target_user = msg.reply_to_message.from_user
    try:
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target_user.id, permissions=permissions)
        await msg.reply_text(f"🔇 تم كتم العضو {target_user.first_name} ومنعه من إرسال الرسائل.")
    except Exception as exc:
        await msg.reply_text(f"❌ تعذر كتم العضو: {exc}")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return

    if not await is_chat_admin(chat, update.effective_user.id, context.bot):
        await msg.reply_text("❌ هذا الأمر مخصص لمشرفي المجموعة فقط.")
        return

    if not msg.reply_to_message:
        await msg.reply_text("⚠️ يرجى الرد على رسالة العضو المراد تحذيره عبر الأمر: `/warn`")
        return

    target_user = msg.reply_to_message.from_user
    row = db_one("SELECT warns FROM users WHERE user_id = ?", (target_user.id,))
    warns = (row["warns"] if row else 0) + 1
    db_execute("UPDATE users SET warns = ? WHERE user_id = ?", (warns, target_user.id))

    if warns >= 3:
        try:
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user.id)
            db_execute("UPDATE users SET warns = 0 WHERE user_id = ?", (target_user.id,))
            await msg.reply_text(f"🚫 تم حظر {target_user.first_name} لتجاوزه الحد الأقصى من التحذيرات (3/3).")
        except Exception:
            pass
    else:
        await msg.reply_text(f"⚠️ تحذير للعضو {target_user.first_name}!\nعدد التحذيرات: ({warns}/3). عند التحذير الثالث سيتم الحظر تلقائياً.")

# -------------------- أوامر البدء والواجهات --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    save_user(user)

    if chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text("🪐 مرحباً! أنا بوت Dua Space لحماية المجموعة وتقديم الخدمات التعليمية والأكاديمية.")
        return

    context.user_data.pop("flow", None)

    is_sub = await is_user_subscribed(context.bot, user.id)
    if not is_sub:
        await update.effective_message.reply_text(
            "⚠️ **تنبيه:** يرجى الانضمام لقناة Dua Space الرسمية أولاً لتتمكن من استخدام البوت وموارده.",
            reply_markup=force_sub_keyboard(),
            parse_mode="Markdown",
        )
        return

    if is_admin_user(user.id):
        await update.effective_message.reply_text(
            "🪐 مرحباً بكِ دعاء في لوحة التحكم الديناميكية الشاملة لـ Dua Space:\nيمكنكِ إدارة القروبات والأقسام وتعديل أي محتوى فوراً من هنا:",
            reply_markup=admin_keyboard(),
        )
    else:
        welcome_text = get_setting("welcome_msg")
        await update.effective_message.reply_text(welcome_text, reply_markup=main_menu_keyboard())

# -------------------- نظام الكويز وتحديات الذكاء --------------------

def get_random_quiz():
    questions = db_all("SELECT * FROM questions")
    return random.choice(questions) if questions else None

def generate_quiz_keyboard(q_id, options):
    buttons = []
    for opt_idx, opt_text in enumerate(options):
        buttons.append([InlineKeyboardButton(f"• {opt_text}", callback_data=f"quiz_ans:{q_id}:{opt_idx}")])
    buttons.append([InlineKeyboardButton("🔄 سؤال آخر", callback_data="quiz_next")])
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

# -------------------- تدفق طلب الخدمات --------------------

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE, service_id: int):
    service = db_one("SELECT * FROM services WHERE id = ? AND active = 1", (service_id,))
    if not service:
        await update.callback_query.message.reply_text("عذرًا، هذه الخدمة غير متوفرة حالياً.")
        return

    context.user_data["flow"] = {"kind": "order_details", "service_id": service_id}
    await update.callback_query.message.reply_text(
        f"📝 تم اختيار: **{service['title']}**\n\n"
        "يرجى كتابة تفاصيل طلبك في رسالة واحدة (المقاسات، الألوان، والمطلوب بالتفصيل):\n"
        "للإلغاء أرسل /cancel."
    )

async def handle_order_text(update: Update, context: ContextTypes.DEFAULT_TYPE, flow):
    details = (update.effective_message.text or "").strip()
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
        f"✅ تم استلام طلبك برقم: #{order_id}\nسنراجعه ونتواصل معك بأقرب وقت 🪐",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💬 متابعة مع الإدارة", url=CONTACT_URL)],
                [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
            ]
        ),
    )

    admin_text = (
        f"📥 **طلب جديد رقم #{order_id}**\n\n"
        f"الخدمة: {service['title']}\n"
        f"العميل: {user.first_name} (@{user.username or 'بدون'})\n"
        f"ID: `{user.id}`\n\n"
        f"التفاصيل:\n{details}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
    except Exception:
        pass

# -------------------- معالجة نقرات الأزرار --------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    user_id = query.from_user.id

    if data == "check_subscription":
        is_sub = await is_user_subscribed(context.bot, user_id)
        if is_sub:
            await query.message.reply_text("🎉 تم التحقق من اشتراكك بنجاح!")
            welcome_text = get_setting("welcome_msg")
            await query.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text("❌ لم يتم التحقق بعد، تأكد من الانضمام للقناة ثم حاول ثانية.", reply_markup=force_sub_keyboard())
        return

    if not is_admin_user(user_id) and not await is_user_subscribed(context.bot, user_id):
        await query.message.reply_text("⚠️ يرجى الانضمام إلى قناة Dua Space أولاً:", reply_markup=force_sub_keyboard())
        return

    if data == "home":
        context.user_data.pop("flow", None)
        welcome_text = get_setting("welcome_msg")
        await query.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())
        return

    # 1. عرض الأقسام المخصصة المضافة يدوياً
    if data.startswith("csec:"):
        sec_id = int(data.split(":", 1)[1])
        sec = db_one("SELECT * FROM sections WHERE id = ?", (sec_id,))
        if sec:
            await query.message.reply_text(sec["content"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]), parse_mode="Markdown")
        return

    # 2. الصرح الهندسي
    if data == "eng_hub_view":
        text = (
            "📐 **الصرح الهندسي والتقني الشامل | Engineering & Tech Hub 🪐**\n\n"
            "مساحتكم التخصصية لأهم فروع ومراجع الهندسة والتكنولوجيا والذكاء الاصطناعي:\n\n"
            "يرجى اختيار التخصص الهندسي المطلوب لتصفح وتحميل أمهات الكتب والمراجع المعتمدة:"
        )
        await query.message.reply_text(text, reply_markup=engineering_menu_keyboard(), parse_mode="Markdown")
        return

    # 3. كويز الذكاء والمخ والمعرفة (ديناميكي)
    if data in ["quiz_start", "quiz_next"]:
        q_row = get_random_quiz()
        if not q_row:
            await query.message.reply_text("يجري تجهيز وإضافة أسئلة جديدة للكويز حالياً 🪐", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")]]))
            return

        opts = json.loads(q_row["options_json"])
        await query.message.reply_text(
            f"🧠 **تحدي الذكاء والمخ والمعرفة:**\n\n{q_row['question']}",
            reply_markup=generate_quiz_keyboard(q_row["id"], opts),
            parse_mode="Markdown",
        )
        return

    if data.startswith("quiz_ans:"):
        _, q_id_str, opt_idx_str = data.split(":")
        q_id = int(q_id_str)
        opt_idx = int(opt_idx_str)

        q_item = db_one("SELECT * FROM questions WHERE id = ?", (q_id,))
        if q_item:
            opts = json.loads(q_item["options_json"])
            if opt_idx == q_item["answer_index"]:
                db_execute("UPDATE users SET quiz_score = quiz_score + 1 WHERE user_id = ?", (user_id,))
                res_text = f"🎉 **إجابة عبقرية وصحيحة!**\n\n💡 {q_item['explanation']}"
            else:
                correct_opt = opts[q_item["answer_index"]]
                res_text = f"❌ **إجابة خاطئة!**\nالصواب هو: **{correct_opt}**\n\n💡 {q_item['explanation']}"

            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🚀 التحدي التالي", callback_data="quiz_next")],
                    [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
                ]
            )
            await query.message.reply_text(res_text, reply_markup=kb, parse_mode="Markdown")
        return

    # 4. الخدمات والتصميم
    if data == "services":
        rows = db_all("SELECT id, title, price FROM services WHERE active = 1 ORDER BY id ASC")
        buttons = [[InlineKeyboardButton(f"{r['title']}", callback_data=f"show_service:{r['id']}")] for r in rows]
        buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
        await query.message.reply_text("🛍️ **خدمات وحلول Dua Space:**\nاختر الخدمة المطلوبة لمعرفة التفاصيل وبدء الطلب:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    if data.startswith("show_service:"):
        s_id = int(data.split(":", 1)[1])
        s = db_one("SELECT * FROM services WHERE id = ?", (s_id,))
        if s:
            text = f"✨ **{s['title']}**\n\nالوصف:\n{s['description']}\n\nالسعر: {s['price']}"
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📩 طلب هذه الخدمة الآن", callback_data=f"order_now:{s_id}")],
                    [InlineKeyboardButton("💬 استفسار مباشر", url=CONTACT_URL)],
                    [InlineKeyboardButton("⬅️ قائمة الخدمات", callback_data="services")],
                ]
            )
            await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if data.startswith("order_now:"):
        await start_order(update, context, int(data.split(":", 1)[1]))
        return

    # 5. القرآن الكريم
    if data == "quran_groups":
        await query.message.reply_text("📖 **القرآن الكريم كاملاً (114 سورة):**\nاختر المجموعة للاستماع والقراءة المباشرة:", reply_markup=quran_group_keyboard(), parse_mode="Markdown")
        return

    if data.startswith("qpage:"):
        start_idx = int(data.split(":", 1)[1])
        await query.message.reply_text("اختر السورة المطلوبة:", reply_markup=quran_page_keyboard(start_idx))
        return

    if data.startswith("surah:"):
        s_num = int(data.split(":", 1)[1])
        s_name = QURAN_SURAHS[s_num - 1]
        surah_padded = f"{s_num:03d}"
        audio_url = f"https://server8.mp3quran.net/afs/{surah_padded}.mp3"
        quran_read_url = f"https://quran.com/{s_num}"

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🎧 استماع مباشر (مشاري العفاسي)", url=audio_url)],
                [InlineKeyboardButton("📖 قراءة وتفسير السورة", url=quran_read_url)],
                [InlineKeyboardButton("🔙 العودة للمصحف", callback_data="quran_groups")],
            ]
        )
        await query.message.reply_text(f"✨ سورة **{s_name}** ({s_num})\nاستمع أو اقرأ عبر الروابط أدناه:", reply_markup=kb, parse_mode="Markdown")
        return

    # 6. المكتبات وعرض الكتب
    if data.startswith("cat:"):
        cat_key = data.split(":", 1)[1]
        cat_names = {
            "eng_bio": "🧬 الهندسة الطبية الحيوية",
            "eng_soft": "💻 هندسة البرمجيات والذكاء الاصطناعي",
            "eng_civil": "🏗️ الهندسة المدنية والإنشائية",
            "eng_elec": "⚡ الهندسة الكهربائية والإلكترونية",
            "eng_mech": "⚙️ الهندسة الميكانيكية وهندسة المواد",
            "islamic": "🕌 المكتبة الإسلامية",
            "medical": "🩺 المكتبة الطبية",
            "languages": "🌍 مكتبة اللغات",
            "psychology": "🧠 علم النفس والمجتمع",
            "philosophy": "🏛️ الفكر والفلسفة",
            "selfdev": "💡 تطوير الذات",
            "novels": "📖 روايات وقصص",
            "topics": "📑 موضوعات عامة",
        }
        name = cat_names.get(cat_key, "المكتبة")
        rows = db_all("SELECT id, title, author FROM books WHERE category = ? ORDER BY id ASC", (cat_key,))
        back_callback = "eng_hub_view" if cat_key.startswith("eng_") else "home"

        if not rows:
            text = f"{name}\n\nيجري حالياً رفع وتجهيز كتب ومواد هذا القسم.. ترقبوها قريباً! 🪐"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data=back_callback)]])
            await query.message.reply_text(text, reply_markup=kb)
            return

        buttons = [[InlineKeyboardButton(f"📖 {r['title']}", callback_data=f"open_book:{r['id']}")] for r in rows]
        buttons.append([InlineKeyboardButton("⬅️ عودة", callback_data=back_callback)])
        await query.message.reply_text(f"{name}\nيرجى اختيار الكتاب لعرضه وتحميله:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("open_book:"):
        b_id = int(data.split(":", 1)[1])
        b = db_one("SELECT * FROM books WHERE id = ?", (b_id,))
        if b:
            caption = f"📖 **{b['title']}**\n✍️ {b['author']}\n\n{b['description']}"
            kb_list = []
            if b["url"]:
                kb_list.append([InlineKeyboardButton("📥 قراءة وتحميل الكتاب", url=b["url"])])
            kb_list.append([InlineKeyboardButton("⬅️ عودة للقسم", callback_data=f"cat:{b['category']}")])

            if b["file_id"]:
                try:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=b["file_id"], caption=caption, reply_markup=InlineKeyboardMarkup(kb_list))
                except Exception:
                    await query.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb_list))
            else:
                await query.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode="Markdown")
        return

    # 7. مؤقت بومودورو والسبحة
    if data == "pomodoro_start":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⏳ بدء جلسة مذاكرة (25 دقيقة)", callback_data="pomo_run:25")],
                [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
            ]
        )
        await query.message.reply_text("⏱️ **مؤقت المذاكرة (Pomodoro):**\n25 دقيقة تركيز تام بدون مشتتات.\nاضغط أدناه للبدء:", reply_markup=kb, parse_mode="Markdown")
        return

    if data.startswith("pomo_run:"):
        await query.message.reply_text("🚀 بدأت الـ 25 دقيقة! ركز في هدفك وسينبهك البوت عند الانتهاء ✨")
        asyncio.create_task(run_pomodoro(query.message.chat_id, context))
        return

    if data == "quotes":
        quote = random.choice(AUTO_POSTS)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 اقتباس آخر", callback_data="quotes")], [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")]])
        await query.message.reply_text(f"✨ **إشراقة واقتباس ملهم:**\n\n{quote}", reply_markup=kb)
        return

    if data == "tasbeeh":
        await query.message.reply_text("📿 **السبحة الإلكترونية التفاعلية:**", reply_markup=tasbeeh_keyboard(0, "سبحان الله"), parse_mode="Markdown")
        return

    if data.startswith("tcount:"):
        _, current_count, phrase = data.split(":", 2)
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(int(current_count) + 1, phrase))
        return

    if data.startswith("tset:"):
        _, _, phrase = data.split(":", 2)
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(0, phrase))
        return

    if data.startswith("treset:"):
        phrase = data.split(":", 1)[1]
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(0, phrase))
        return

    if data == "share_bot":
        share_text = "🪐 أنصحكم بتجربة بوت Dua Space الشامل! القرآن كاملاً، والهندسة، والطب، وعلم النفس، والمانجا، والمنح، وتحديات الذكاء:\n\nhttps://t.me/DuaSpaceHelperBot"
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text={share_text}"
        await query.message.reply_text("🪐 شارك رابط البوت مع أصدقائك:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 إرسال الآن", url=share_url)], [InlineKeyboardButton("⬅️ عودة", callback_data="home")]]))
        return

    if data == "follow_us":
        social_text = "🪐 **منصات وحسابات Dua Space الرسمية:**\n\n• القناة الرسمية: https://t.me/DuaSpace1\n• الإدارة والتواصل المباشر: @xdua1"
        await query.message.reply_text(social_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]))
        return

    if data == "faq_info":
        faq_text = "💡 **الأسئلة الشائعة حول Dua Space:**\n\n• **هل المحتوى مجاني؟** نعم، كافة الكتب والمراجع مجانية تماماً.\n• **كيف أطلب خدمة؟** من قسم الخدمات تختار الخدمة وتكتب التفاصيل."
        await query.message.reply_text(faq_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]))
        return

    if data == "recommend":
        context.user_data["flow"] = {"kind": "rec_msg"}
        await query.message.reply_text("✍️ نرحب بمقترحاتكم لكتب أو أقسام تودون إضافتها:\nاكتب مقترحك في رسالة واحدة:")
        return

    if data == "portfolio":
        rows = db_all("SELECT id, title FROM portfolio ORDER BY id DESC LIMIT 15")
        if not rows:
            await query.message.reply_text("🎨 معرض الأعمال: يجري رفع التصاميم قريباً 🪐", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]))
        else:
            buttons = [[InlineKeyboardButton(f"🖼️ {r['title']}", callback_data=f"show_port:{r['id']}")] for r in rows]
            buttons.append([InlineKeyboardButton("⬅️ عودة", callback_data="home")])
            await query.message.reply_text("🎨 نماذج أعمالنا:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("show_port:"):
        p_id = int(data.split(":", 1)[1])
        item = db_one("SELECT * FROM portfolio WHERE id = ?", (p_id,))
        if item:
            try:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=item["file_id"], caption=f"🎨 **{item['title']}**\n\n{item['description']}", parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(f"🎨 **{item['title']}**\n\n{item['description']}")
        return

    # -------------------- وظائف الإدارة الديناميكية --------------------
    if not is_admin_user(user_id):
        return

    if data == "admin_home":
        await query.message.reply_text("🎛️ لوحة إدارة Dua Space الشاملة:", reply_markup=admin_keyboard())

    elif data == "admin_pin_official":
        try:
            msg = await context.bot.send_message(chat_id=CHANNEL_ID, text=OFFICIAL_LAUNCH_POST)
            await context.bot.pin_chat_message(chat_id=CHANNEL_ID, message_id=msg.message_id)
            await query.message.reply_text("✅ تم نشر المنشور وتثبيته في القناة بنجاح 🪐!")
        except Exception as exc:
            await query.message.reply_text(f"❌ خطأ أثناء التثبيت: {exc}\n(تأكدي من صلاحيات البوت في القناة)")

    elif data == "admin_edit_welcome":
        context.user_data["flow"] = {"kind": "set_welcome"}
        current_w = get_setting("welcome_msg")
        await query.message.reply_text(f"📝 **الرسالة الترحيبية الحالية:**\n\n{current_w}\n\n—\nأرسلي النص الجديد الذي تريدين اعتماده لرسالة الترحيب:")

    elif data == "admin_add_section":
        context.user_data["pending_section"] = {}
        context.user_data["flow"] = {"kind": "sec_title"}
        await query.message.reply_text("➕ أرسلي اسم الزر/القسم الجديد (مثال: 🚀 منحة تشيفنينغ):")

    elif data == "admin_del_section_list":
        secs = db_all("SELECT id, title FROM sections ORDER BY id DESC")
        if not secs:
            await query.message.reply_text("لا توجد أقسام مخصصة حالياً.", reply_markup=admin_keyboard())
            return
        buttons = [[InlineKeyboardButton(f"❌ {s['title']}", callback_data=f"del_sec:{s['id']}")] for s in secs]
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await query.message.reply_text("🗑️ اختاري القسم الذي تودين حذفه نهائياً من القائمة الرئيسية:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("del_sec:"):
        sec_id = int(data.split(":", 1)[1])
        db_execute("DELETE FROM sections WHERE id = ?", (sec_id,))
        await query.message.reply_text("✅ تم حذف القسم بنجاح وإزالته من القائمة الرئيسية!", reply_markup=admin_keyboard())

    elif data == "admin_add_question":
        context.user_data["pending_question"] = {}
        context.user_data["flow"] = {"kind": "q_text"}
        await query.message.reply_text("🧠 أرسلي نص السؤال الجديد:")

    elif data == "admin_del_question_list":
        qs = db_all("SELECT id, question FROM questions ORDER BY id DESC LIMIT 15")
        if not qs:
            await query.message.reply_text("لا توجد أسئلة مسجلة في بنك الكويز حالياً.", reply_markup=admin_keyboard())
            return
        buttons = [[InlineKeyboardButton(f"❌ {q['question'][:35]}...", callback_data=f"del_q:{q['id']}")] for q in qs]
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await query.message.reply_text("🗑️ اختاري السؤال الذي تريدين حذفه نهائياً من الكويز:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("del_q:"):
        qid = int(data.split(":", 1)[1])
        db_execute("DELETE FROM questions WHERE id = ?", (qid,))
        await query.message.reply_text("✅ تم حذف السؤال بنجاح من بنك الكويز!", reply_markup=admin_keyboard())

    elif data == "admin_del_book_cats":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🧠 علم نفس", callback_data="delb_cat:psychology"), InlineKeyboardButton("🧬 هندسة حيوية", callback_data="delb_cat:eng_bio")],
                [InlineKeyboardButton("💻 برمجيات وAI", callback_data="delb_cat:eng_soft"), InlineKeyboardButton("🏗️ مدنية وإنشائية", callback_data="delb_cat:eng_civil")],
                [InlineKeyboardButton("⚡ كهربائية", callback_data="delb_cat:eng_elec"), InlineKeyboardButton("⚙️ ميكانيكية", callback_data="delb_cat:eng_mech")],
                [InlineKeyboardButton("🩺 طبية", callback_data="delb_cat:medical"), InlineKeyboardButton("🕌 إسلامية", callback_data="delb_cat:islamic")],
                [InlineKeyboardButton("🌍 لغات", callback_data="delb_cat:languages"), InlineKeyboardButton("💡 تطوير ذات", callback_data="delb_cat:selfdev")],
                [InlineKeyboardButton("📖 روايات", callback_data="delb_cat:novels"), InlineKeyboardButton("📑 موضوعات", callback_data="delb_cat:topics")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")],
            ]
        )
        await query.message.reply_text("📚 اختاري القسم الذي تودين حذف كتاب منه:", reply_markup=kb)

    elif data.startswith("delb_cat:"):
        cat = data.split(":", 1)[1]
        bks = db_all("SELECT id, title FROM books WHERE category = ? ORDER BY id DESC", (cat,))
        if not bks:
            await query.message.reply_text("لا توجد كتب في هذا القسم حالياً.", reply_markup=admin_keyboard())
            return
        buttons = [[InlineKeyboardButton(f"❌ {b['title']}", callback_data=f"del_book_id:{b['id']}")] for b in bks]
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await query.message.reply_text("اختاري الكتاب المراد حذفه نهائياً:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("del_book_id:"):
        bid = int(data.split(":", 1)[1])
        db_execute("DELETE FROM books WHERE id = ?", (bid,))
        await query.message.reply_text("✅ تم حذف الكتاب بنجاح من المكتبة!", reply_markup=admin_keyboard())

    elif data == "admin_orders":
        rows = db_all("SELECT id, service_title, status FROM orders ORDER BY id DESC LIMIT 10")
        if not rows:
            await query.message.reply_text("لا توجد طلبات مسجلة بعد.", reply_markup=admin_keyboard())
            return
        text = "📥 **طلبات العملاء الواردة:**\n\n"
        for r in rows:
            text += f"• طلب #{r['id']} ({r['status']}) - {r['service_title']}\n"
        await query.message.reply_text(text, reply_markup=admin_keyboard())

    elif data == "admin_autopost_now":
        post_text = random.choice(AUTO_POSTS) + "\n\n—\n🪐 Dua Space • مساحتكم للإبداع والمعرفة"
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            await query.message.reply_text("✅ تم إرسال ونشر تذكير فوري في القناة بنجاح.")
        except Exception as exc:
            await query.message.reply_text(f"❌ تعذر النشر في القناة: {exc}")

    elif data == "admin_backup":
        if os.path.exists(DB_PATH):
            await context.bot.send_document(chat_id=user_id, document=open(DB_PATH, "rb"), caption=f"💾 نسخة احتياطية: {datetime.utcnow().strftime('%Y-%m-%d')}")
        else:
            await query.message.reply_text("ملف قاعدة البيانات غير متوفر.")

    elif data == "admin_users":
        rows = db_all("SELECT user_id, username, first_name, quiz_score FROM users ORDER BY last_seen DESC LIMIT 50")
        text = f"👥 **مستخدمو البوت النشطين ({len(rows)}):**\n\n"
        for idx, u in enumerate(rows, 1):
            un = f"@{u['username']}" if u["username"] else "بدون يوزر"
            text += f"{idx}. {u['first_name'] or 'مستخدم'} ({un}) - نقاط الذكاء: {u['quiz_score']}\n"
        await query.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="Markdown")

    elif data == "admin_broadcast":
        context.user_data["flow"] = {"kind": "broadcast"}
        await query.message.reply_text("📢 أرسلي الرسالة التي تودين بثها لجميع المستخدمين:")

    elif data == "add_book_flow":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🧠 علم نفس", callback_data="set_bcat:psychology"), InlineKeyboardButton("🧬 هندسة حيوية", callback_data="set_bcat:eng_bio")],
                [InlineKeyboardButton("💻 برمجيات وAI", callback_data="set_bcat:eng_soft"), InlineKeyboardButton("🏗️ مدنية وإنشائية", callback_data="set_bcat:eng_civil")],
                [InlineKeyboardButton("⚡ كهربائية", callback_data="set_bcat:eng_elec"), InlineKeyboardButton("⚙️ ميكانيكية", callback_data="set_bcat:eng_mech")],
                [InlineKeyboardButton("🩺 طبية", callback_data="set_bcat:medical"), InlineKeyboardButton("🕌 إسلامية", callback_data="set_bcat:islamic")],
                [InlineKeyboardButton("🌍 لغات", callback_data="set_bcat:languages"), InlineKeyboardButton("💡 تطوير ذات", callback_data="set_bcat:selfdev")],
                [InlineKeyboardButton("📖 روايات", callback_data="set_bcat:novels"), InlineKeyboardButton("📑 موضوعات", callback_data="set_bcat:topics")],
            ]
        )
        await query.message.reply_text("📚 اختاري القسم لإضافة الكتاب:", reply_markup=kb)

    elif data.startswith("set_bcat:"):
        cat = data.split(":", 1)[1]
        context.user_data["pending_book"] = {"category": cat}
        context.user_data["flow"] = {"kind": "b_title"}
        await query.message.reply_text("اكتبي عنوان الكتاب الآن:")

    elif data == "add_port_flow":
        context.user_data["flow"] = {"kind": "p_title"}
        await query.message.reply_text("اكتبي عنوان العمل أو التصميم:")

# -------------------- دالة مؤقت بومودورو والنشر التلقائي --------------------

async def run_pomodoro(chat_id, context):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.send_message(chat_id=chat_id, text="🔔 **انتهت الـ 25 دقيقة!**\nعمل رائع، خذ استراحة 5 دقائق لإنعاش ذهنك ✨", parse_mode="Markdown")
    except Exception:
        pass

async def channel_auto_poster(bot):
    while True:
        try:
            await asyncio.sleep(4 * 3600)
            selected = random.choice(AUTO_POSTS)
            text = f"{selected}\n\n—\n🪐 Dua Space • مساحتكم للإبداع والمعرفة"
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            logger.info("Auto post sent to channel.")
        except Exception as e:
            logger.warning(f"Auto post error: {e}")
            await asyncio.sleep(300)

# -------------------- معالجة النصوص والملفات والمدخلات --------------------

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not msg.text:
        return

    # حفظ تفاعل المستخدم في المجموعات والخاص
    save_user(user)

    if chat.type != ChatType.PRIVATE:
        return

    flow = context.user_data.get("flow")

    if flow and flow.get("kind") == "order_details":
        await handle_order_text(update, context, flow)
        return

    if flow and flow.get("kind") == "rec_msg":
        content = msg.text.strip()
        db_execute("INSERT INTO recommendations(user_id, username, content) VALUES(?, ?, ?)", (user.id, user.username or "", content))
        context.user_data.pop("flow", None)
        await msg.reply_text("✅ تم استلام مقترحك بنجاح، شكراً لك!", reply_markup=main_menu_keyboard())
        return

    if is_admin_user(user.id) and flow:
        kind = flow.get("kind")
        val = msg.text.strip()

        # تعديل الترحيب
        if kind == "set_welcome":
            set_setting("welcome_msg", val)
            context.user_data.pop("flow", None)
            await msg.reply_text("✅ تم تحديث رسالة الترحيب بنجاح!", reply_markup=admin_keyboard())
            return

        # إضافة قسم مخصص
        elif kind == "sec_title":
            context.user_data["pending_section"]["title"] = val
            context.user_data["flow"] = {"kind": "sec_content"}
            await msg.reply_text("أرسلي النص الكامل والمحتوى الذي سيظهر للأعضاء عند فتح هذا القسم:")
            return

        elif kind == "sec_content":
            context.user_data["pending_section"]["content"] = val
            context.user_data["flow"] = {"kind": "sec_url"}
            await msg.reply_text("هل ترغبين بإرفاق رابط خارجي يفتح عند الضغط على الزر مباشرة؟ (أرسلي الرابط، أو اكتبي: بدون):")
            return

        elif kind == "sec_url":
            btn_url = val if val != "بدون" and val.startswith("http") else None
            p = context.user_data.pop("pending_section", {})
            context.user_data.pop("flow", None)
            db_execute("INSERT INTO sections(title, content, btn_url) VALUES(?, ?, ?)", (p["title"], p["content"], btn_url))
            await msg.reply_text("✅ تمت إضافة القسم الجديد بنجاح، وسيظهر فوراً في القائمة الرئيسية للأعضاء!", reply_markup=admin_keyboard())
            return

        # إضافة سؤال كويز
        elif kind == "q_text":
            context.user_data["pending_question"]["q"] = val
            context.user_data["flow"] = {"kind": "q_opts"}
            await msg.reply_text("أرسلي الخيارات مفصولة بفاصلة (مثال: خيار 1، خيار 2، خيار 3، خيار 4):")
            return

        elif kind == "q_opts":
            opts = [o.strip() for o in val.split("،") if o.strip()]
            if len(opts) < 2:
                opts = [o.strip() for o in val.split(",") if o.strip()]
            if len(opts) < 2:
                await msg.reply_text("❌ يرجى إرسال خيارين على الأقل مفصولين بفاصلة (،):")
                return
            context.user_data["pending_question"]["opts"] = opts
            context.user_data["flow"] = {"kind": "q_ans"}
            await msg.reply_text(f"ما هو رقم الإجابة الصحيحة؟ (اكتبي رقماً من 1 إلى {len(opts)}):")
            return

        elif kind == "q_ans":
            try:
                ans_idx = int(val) - 1
                opts_len = len(context.user_data["pending_question"]["opts"])
                if ans_idx < 0 or ans_idx >= opts_len:
                    await msg.reply_text(f"❌ الرجاء كتابة رقم صحيح بين 1 و {opts_len}:")
                    return
            except ValueError:
                await msg.reply_text("❌ الرجاء كتابة رقم فقط:")
                return

            context.user_data["pending_question"]["ans"] = ans_idx
            context.user_data["flow"] = {"kind": "q_exp"}
            await msg.reply_text("اكتبي الشرح أو التوضيح للإجابة الصحيحة:")
            return

        elif kind == "q_exp":
            pq = context.user_data.pop("pending_question", {})
            context.user_data.pop("flow", None)
            db_execute(
                "INSERT INTO questions(question, options_json, answer_index, explanation) VALUES(?, ?, ?, ?)",
                (pq["q"], json.dumps(pq["opts"], ensure_ascii=False), pq["ans"], val)
            )
            await msg.reply_text("✅ تمت إضافة السؤال بنجاح إلى بنك الكويز والتحديات!", reply_markup=admin_keyboard())
            return

        # إذاعة
        elif kind == "broadcast":
            context.user_data.pop("flow", None)
            users = db_all("SELECT user_id FROM users")
            sent = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u["user_id"], text=val)
                    sent += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    pass
            await msg.reply_text(f"📢 تمت الإذاعة بنجاح لـ {sent} مستخدم.", reply_markup=admin_keyboard())
            return

        # إضافة كتاب
        elif kind == "b_title":
            context.user_data["pending_book"]["title"] = val
            context.user_data["flow"] = {"kind": "b_author"}
            await msg.reply_text("اكتبي اسم المؤلف:")
            return

        elif kind == "b_author":
            context.user_data["pending_book"]["author"] = val
            context.user_data["flow"] = {"kind": "b_desc"}
            await msg.reply_text("اكتبي نبذة مختصرة عن الكتاب:")
            return

        elif kind == "b_desc":
            context.user_data["pending_book"]["description"] = val
            context.user_data["flow"] = {"kind": "b_url"}
            await msg.reply_text("أرسلي رابط القراءة والتحميل (أو اكتبي: بدون):")
            return

        elif kind == "b_url":
            book_url = val if val != "بدون" else None
            context.user_data["pending_book"]["url"] = book_url
            context.user_data["flow"] = {"kind": "b_file"}
            await msg.reply_text("أرسلي ملف الـ PDF الآن (أو اكتبي: بدون):")
            return

        elif kind == "b_file" and val == "بدون":
            p = context.user_data.pop("pending_book", {})
            context.user_data.pop("flow", None)
            db_execute("INSERT INTO books(category, title, author, description, file_id, url) VALUES(?, ?, ?, ?, NULL, ?)", (p["category"], p["title"], p["author"], p["description"], p.get("url")))
            await msg.reply_text("✅ تمت إضافة الكتاب بنجاح للمكتبة!", reply_markup=admin_keyboard())
            return

        # إضافة معرض أعمال
        elif kind == "p_title":
            context.user_data["pending_port"] = {"title": val}
            context.user_data["flow"] = {"kind": "p_desc"}
            await msg.reply_text("اكتبي وصفاً للعمل أو التصميم:")
            return

        elif kind == "p_desc":
            context.user_data["pending_port"]["description"] = val
            context.user_data["flow"] = {"kind": "p_file"}
            await msg.reply_text("أرسلي الآن صورة العمل مباشرة:")
            return

    if is_admin_user(user.id):
        await msg.reply_text("أهلاً بكِ دعاء 🪐\nأرسلي /admin لفتح لوحة التحكم، أو /cancel للإلغاء.")

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return

    flow = context.user_data.get("flow")

    if flow and flow.get("kind") == "p_file" and update.effective_message.photo:
        photo = update.effective_message.photo[-1]
        p = context.user_data.pop("pending_port", {})
        context.user_data.pop("flow", None)
        db_execute("INSERT INTO portfolio(title, description, file_id) VALUES(?, ?, ?)", (p["title"], p["description"], photo.file_id))
        await update.effective_message.reply_text("✅ تمت إضافة العمل بنجاح لمعرض الأعمال!", reply_markup=admin_keyboard())
        return

    if flow and flow.get("kind") == "b_file" and update.effective_message.document:
        doc = update.effective_message.document
        p = context.user_data.pop("pending_book", {})
        context.user_data.pop("flow", None)
        db_execute("INSERT INTO books(category, title, author, description, file_id, url) VALUES(?, ?, ?, ?, ?, ?)", (p["category"], p["title"], p["author"], p["description"], doc.file_id, p.get("url")))
        await update.effective_message.reply_text("✅ تم حفظ ملف الكتاب وربطه بالقسم بنجاح!", reply_markup=admin_keyboard())
        return

# -------------------- نقطة التشغيل وخادم الويب --------------------

async def handle_health(request):
    return web.Response(text="Dua Space Ultimate Live Pro 🪐", status=200)

async def main():
    if not BOT_TOKEN or not CHANNEL_ID or not ADMIN_ID:
        raise RuntimeError("تأكد من إعداد متغيرات BOT_TOKEN و CHANNEL_ID و ADMIN_ID")

    init_db()

    app_web = web.Application()
    app_web.router.add_get("/", handle_health)
    app_web.router.add_get("/health", handle_health)

    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    application = Application.builder().token(BOT_TOKEN).build()

    # أوامر البوت الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", lambda u, c: u.effective_message.reply_text("🎛️ لوحة إدارة Dua Space الديناميكية:", reply_markup=admin_keyboard()) if is_admin_user(u.effective_user.id) else None))
    application.add_handler(CommandHandler("cancel", lambda u, c: u.effective_message.reply_text("تم الإلغاء.") if c.user_data.pop("flow", None) is not None else None))

    # أوامر إدارة القروبات والمجموعات
    application.add_handler(CommandHandler("del", cmd_del))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("mute", cmd_mute))
    application.add_handler(CommandHandler("warn", cmd_warn))

    # معالجات الأزرار والرسائل
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    application.add_handler(MessageHandler(filters.ATTACHMENT, file_handler))

    # حذف رسائل الخدمة التلقائية في القروبات (انضم وغادر)
    application.add_handler(MessageHandler(filters.StatusUpdate.ALL, lambda u, c: c.bot.delete_message(chat_id=u.effective_chat.id, message_id=u.effective_message.message_id) if u.effective_chat.type != ChatType.PRIVATE else None))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Dua Space Ultimate Engine is Running.")

        asyncio.create_task(channel_auto_poster(application.bot))

        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
