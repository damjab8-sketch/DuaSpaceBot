import asyncio
import logging
import os
import random
import sqlite3
from datetime import datetime

from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus
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
logger = logging.getLogger("DuaSpaceUltimateBot")

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

# -------------------- بيانات القرآن الكريم (114 سورة) --------------------

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

# -------------------- قائمة الكتب المضافة تلقائياً --------------------

PRELOADED_BOOKS = [
    ("islamic", "الأربعون النووية", "الإمام النووي", "أهم الأحاديث الجامعة لقواعد وأصول الدين الإسلامي."),
    ("islamic", "رياض الصالحين", "الإمام النووي", "دليل المسلم العملي في الأخلاق والعبادات."),
    ("islamic", "الرحيق المختوم", "صفي الرحمن المباركفوري", "سيرة نبوية عطرة شاملة ومحققة."),
    ("medical", "دليل الإسعافات الأولية الشامل", "منظمة الصحة العالمية", "دليل عملي مصور للتعامل مع الطوارئ الطبية."),
    ("medical", "مبادئ علم التشريح ووظائف الأعضاء", "د. خالد عمارة", "مدخل مبسط لفهم أجهزة وأعضاء جسم الإنسان."),
    ("medical", "المرجع السريع في الأدوية", "نخبة من الأطباء", "دليل مختصر عن تصنيفات واستخدامات الأدوية."),
    ("languages", "قواعد اللغة الإنجليزية (English Grammar)", "Raymond Murphy", "المرجع العالمي الأشهر لتعلم قواعد الإنجليزية."),
    ("languages", "دليل المحادثة التركية اليومية", "إسطنبول لتعليم اللغات", "أهم المفردات والجمل الشائعة للمحادثة اليومية."),
    ("languages", "أساسيات الفرنسية للمبتدئين", "معهد اللغات", "مدخل لأساسيات وقواعد اللغة الفرنسية."),
    ("psychology", "علم النفس المعرفي وسلوك الإنسان", "د. روبرت سولسو", "دراسة شيقة لكيفية عمل العقل والتفكير."),
    ("psychology", "سيكولوجية الجماهير", "غوستاف لوبون", "الكتاب الأهم في فهم حركة وسلوك المجتمعات."),
    ("philosophy", "مقدمة ابن خلدون", "عبد الرحمن بن خلدون", "المرجع التأسيسي الأول في علم الاجتماع وفلسفة التاريخ."),
    ("philosophy", "قصة الفلسفة", "ويل ديورانت", "رحلة ممتعة تستعرض حياة وأفكار كبار الفلاسفة عبر التاريخ."),
    ("selfdev", "العادات الذرية (Atomic Habits)", "جيمس كلير", "منهج عملي لبناء عادات إيجابية والتخلص من السلبية."),
    ("selfdev", "فن إدارة الوقت والإنتاجية العالية", "برايان تريسي", "استراتيجيات عملية لتنظيم المهام وزيادة التركيز."),
    ("novels", "البؤساء (Les Misérables)", "فيكتور هوجو", "ملحمة إنسانية خالدة عن العدالة والرحمة والأمل."),
    ("novels", "الخيميائي", "باولو كويلو", "رواية رمزية ملهمة عن السعي لتحقيق الأحلام."),
    ("topics", "دليل الطالب الناجح للتفوق الدراسي", "Dua Space", "خطوات واستراتيجيات مجربة لتنظيم الدراسة والمراجعة."),
]

AUTO_POSTS = [
    "﴿أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ﴾ ✨\n\nسبحان الله، والحمد لله، ولا إله إلا الله، والله أكبر.",
    "﴿وَتَوَكَّلْ عَلَى الْعَزِيزِ الرَّحِيمِ * الَّذِي يَرَاكَ حِينَ تَقُومُ﴾ 🪐",
    "قال رسول الله ﷺ: «مَن سَلَكَ طَرِيقًا يَلْتَمِسُ فِيهِ عِلْمًا، سَهَّلَ اللَّهُ له به طَرِيقًا إلى الجَنَّةِ». 🌿",
    "قال رسول الله ﷺ: «إنَّ اللهَ يُحِبُّ إذا عمِلَ أحَدُكُم عمَلًا أنْ يُتْقِنَه». 💫",
    "«لا يقاس النجاح بالموقع الذي يتبوأه المرء في حياته، بقدر ما يقاس بالصعاب التي تغلب عليها.» — بوكر واشنطن",
    "«العقل الذي يتسع لفكرة جديدة لا يعود أبداً إلى حجمه الأصلي.» — أوليفر وندل هولمز 💡",
    "«كن أنت التغيير الذي تريد أن تراه في هذا العالم.» — غاندي ✨",
    "﴿إِنَّ مَعَ الْعُسْرِ يُسْرًا﴾ 🌸",
    "«سَيِّدُ الاِسْتِغْفَارِ: اللَّهُمَّ أَنْتَ رَبِّي لاَ إِلَهَ إِلاَّ أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ، وَأَنَا عَلَى عَهْدِكَ وَوَعْدِكَ مَا اسْتَطَعْتُ». 📿",
]

TEXTS = {
    "ar": {
        "welcome": "أهلًا بكم في Dua Space! 🪐\nمساحتكم الشاملة للإبداع والمعرفة والارتقاء.\nيرجى اختيار القسم المطلوب عبر الأزرار أدناه:",
        "must_subscribe": "⚠️ **تنبيه للاستمرار:**\n\nيرجى الانضمام إلى قناة Dua Space الرسمية أولاً لتتمكن من استخدام البوت ومكتباته.\n\nاضغط أدناه للانضمام، ثم اضغط على «✅ تحقّق من الاشتراك»:",
        "sub_btn": "📢 انضم للقناة الآن",
        "check_sub": "✅ تحقّق من الاشتراك",
        "sub_success": "🎉 شكراً لانضمامك! تم تفعيل القائمة بالكامل.",
        "sub_failed": "❌ لم يتم التحقق من اشتراكك بالقناة بعد. انضم أولاً ثم أعد المحاولة.",
        "lang_btn": "🌐 تغيير اللغة / Language",
        "quran_btn": "📖 القرآن الكريم كاملاً (114 سورة)",
        "services": "🛍️ الخدمات والتصميم",
        "portfolio": "🎨 معرض الأعمال",
        "scholarships": "🎓 المنح والفرص التعليمية",
        "islamic_lib": "🕌 المكتبة الإسلامية",
        "medical_lib": "🩺 المكتبة الطبية",
        "lang_lib": "🌍 مكتبة اللغات",
        "psych_lib": "🧠 علم النفس والمجتمع",
        "phil_lib": "🏛️ الفكر والفلسفة",
        "dev_lib": "💡 تطوير الذات والإنتاجية",
        "novels_lib": "📖 روايات وقصص متنوعة",
        "topics_lib": "📑 مكتبة الموضوعات الشاملة",
        "quotes": "✨ اقتباسات عالمية ملهمة",
        "tasbeeh": "📿 السبحة الإلكترونية",
        "pomodoro": "⏱️ مؤقت المذاكرة والتركيز (Pomodoro)",
        "faq": "💡 الأسئلة الشائعة والدعم",
        "recommendations": "🌟 توصيات وترشيحات الأعضاء",
        "share": "📢 مشاركة البوت",
        "follow": "🔗 منصاتنا وحساباتنا (تابعني)",
        "contact": "💬 التواصل المباشر",
        "back": "⬅️ القائمة الرئيسية",
        "empty_sec": "يجري حالياً رفع وتجهيز كتب ومواد هذا القسم.. ترقبوها قريباً! 🪐",
        "rec_prompt": "✍️ نرحب بمقترحاتكم لكتب أو مواد تودون إضافتها في Dua Space:\nاكتب مقترحك في رسالة واحدة:",
        "rec_sent": "✅ شكراً جزيلاً! تم إرسال توصيتك للإدارة بنجاح.",
        "share_text": "🪐 أنصحكم بتجربة بوت Dua Space الشامل! القرآن كاملاً، ومكتبات إسلامية، طبية، لغات، روايات، واقتباسات ملهمة، وخدمات إبداعية:\n\nhttps://t.me/DuaSpaceHelperBot",
        "social_text": "🪐 **منصات وحسابات Dua Space الرسمية:**\n\n• القناة الرسمية: https://t.me/DuaSpace1\n• الإدارة والتواصل المباشر: @xdua1\n• ترقبوا قريباً بقية الروابط والمنصات التابعة لنا!",
        "faq_text": "💡 **الأسئلة الشائعة حول خدمات Dua Space:**\n\n• **كيف أطلب خدمة؟**\nتواصل مباشرة مع الإدارة.\n\n• **هل الكتب مجانية؟**\nنعم، كافة الكتب والمراجع القرآنية والطبية مجانية بالكامل.",
        "scholarships_text": "🎓 **دليل المنح والفرص التعليمية:**\n\n• مصادر موثوقة لأفضل المنح الدولية المجانية (تركيا، قطر، أوروبا).\n• أدلة واختبارات اللغة الدولية (IELTS / TOEFL).",
    },
    "en": {
        "welcome": "Welcome to Dua Space! 🪐\nYour complete space for creativity, learning, and growth.\nPlease select an option below:",
        "must_subscribe": "⚠️ **Subscription Required:**\n\nPlease join our official channel first to unlock all features.\n\nClick below to join, then click '✅ Check Subscription':",
        "sub_btn": "📢 Join Channel",
        "check_sub": "✅ Check Subscription",
        "sub_success": "🎉 Welcome! Access granted.",
        "sub_failed": "❌ Subscription not verified yet. Please try again.",
        "lang_btn": "🌐 Change Language / اللغة",
        "quran_btn": "📖 The Holy Quran (114 Surahs)",
        "services": "🛍️ Services & Design",
        "portfolio": "🎨 Portfolio",
        "scholarships": "🎓 Scholarships & Opportunities",
        "islamic_lib": "🕌 Islamic Library",
        "medical_lib": "🩺 Medical Library",
        "lang_lib": "🌍 Languages Library",
        "psych_lib": "🧠 Psychology & Society",
        "phil_lib": "🏛️ Philosophy & Thought",
        "dev_lib": "💡 Self-Development",
        "novels_lib": "📖 Novels & Stories",
        "topics_lib": "📑 Knowledge Articles",
        "quotes": "✨ World Inspiring Quotes",
        "tasbeeh": "📿 Digital Tasbeeh",
        "pomodoro": "⏱️ Study Focus Timer (Pomodoro)",
        "faq": "💡 FAQ & Support",
        "recommendations": "🌟 Member Recommendations",
        "share": "📢 Share Bot",
        "follow": "🔗 Follow Us",
        "contact": "💬 Direct Contact",
        "back": "⬅️ Main Menu",
        "empty_sec": "Resources are being prepared. Stay tuned! 🪐",
        "rec_prompt": "✍️ Send us your book or content recommendations:",
        "rec_sent": "✅ Thank you! Your recommendation has been received.",
        "share_text": "🪐 Explore Dua Space Bot! Full Quran, libraries, novels, inspiring quotes, and creative services:\n\nhttps://t.me/DuaSpaceHelperBot",
        "social_text": "🪐 **Dua Space Links:**\n• Channel: https://t.me/DuaSpace1\n• Admin: @xdua1",
        "faq_text": "💡 All materials and books are completely free.",
        "scholarships_text": "🎓 International scholarship guides & exam resources.",
    },
    "fr": {
        "welcome": "Bienvenue sur Dua Space ! 🪐\nVeuillez choisir une section :",
        "must_subscribe": "⚠️ **Abonnement requis :** Rejoignez la chaîne officielle.",
        "sub_btn": "📢 Rejoindre la chaîne",
        "check_sub": "✅ Vérifier l'abonnement",
        "sub_success": "🎉 Accès débloqué.",
        "sub_failed": "❌ Abonnement non détecté.",
        "lang_btn": "🌐 Changer de langue",
        "quran_btn": "📖 Le Saint Coran (114 Sourates)",
        "services": "🛍️ Services & Design",
        "portfolio": "🎨 Portfolio",
        "scholarships": "🎓 Bourses & Opportunités",
        "islamic_lib": "🕌 Bibliothèque Islamique",
        "medical_lib": "🩺 Bibliothèque Médicale",
        "lang_lib": "🌍 Langues & Linguistique",
        "psych_lib": "🧠 Psychologie & Société",
        "phil_lib": "🏛️ Philosophie & Pensée",
        "dev_lib": "💡 Développement Personnel",
        "novels_lib": "📖 Romans & Histoires",
        "topics_lib": "📑 Thématiques & Guides",
        "quotes": "✨ Citations Inspirantes",
        "tasbeeh": "📿 Tasbih Numérique",
        "pomodoro": "⏱️ Minuteur d'étude (Pomodoro)",
        "faq": "💡 FAQ & Assistance",
        "recommendations": "🌟 Recommandations",
        "share": "📢 Partager le bot",
        "follow": "🔗 Suivez-nous",
        "contact": "💬 Contact direct",
        "back": "⬅️ Menu principal",
        "empty_sec": "Ressources en cours de préparation. 🪐",
        "rec_prompt": "✍️ Envoyez vos suggestions :",
        "rec_sent": "✅ Recommandation transmise.",
        "share_text": "🪐 Découvrez le bot Dua Space :\nhttps://t.me/DuaSpaceHelperBot",
        "social_text": "🪐 Chaîne: https://t.me/DuaSpace1 | Admin: @xdua1",
        "faq_text": "💡 Toutes les ressources sont gratuites.",
        "scholarships_text": "🎓 Guide des bourses d'études.",
    },
    "it": {
        "welcome": "Benvenuto su Dua Space! 🪐\nScegli una sezione dai pulsanti qui sotto:",
        "must_subscribe": "⚠️ **Iscrizione obbligatoria:** Unisciti al canale ufficiale.",
        "sub_btn": "📢 Unisciti al canale",
        "check_sub": "✅ Verifica iscrizione",
        "sub_success": "🎉 Bot attivo.",
        "sub_failed": "❌ Iscrizione non rilevata.",
        "lang_btn": "🌐 Cambia lingua",
        "quran_btn": "📖 Il Sacro Corano (114 Sure)",
        "services": "🛍️ Servizi & Design",
        "portfolio": "🎨 Portfolio",
        "scholarships": "🎓 Borse di Studio",
        "islamic_lib": "🕌 Biblioteca Islamica",
        "medical_lib": "🩺 Biblioteca Medica",
        "lang_lib": "🌍 Lingue Straniere",
        "psych_lib": "🧠 Psicologia & Società",
        "phil_lib": "🏛️ Filosofia & Pensiero",
        "dev_lib": "💡 Crescita Personale",
        "novels_lib": "📖 Romanzi & Storie",
        "topics_lib": "📑 Articoli & Temi",
        "quotes": "✨ Citazioni Celebri",
        "tasbeeh": "📿 Tasbeeh Digitale",
        "pomodoro": "⏱️ Timer Studio (Pomodoro)",
        "faq": "💡 Domande Frequenti",
        "recommendations": "🌟 Consigli dei membri",
        "share": "📢 Condividi il bot",
        "follow": "🔗 Seguici",
        "contact": "💬 Contatto diretto",
        "back": "⬅️ Menu principale",
        "empty_sec": "Contenuti in arrivo. 🪐",
        "rec_prompt": "✍️ Scrivi qui il tuo consiglio:",
        "rec_sent": "✅ Suggerimento registrato.",
        "share_text": "🪐 Scopri Dua Space Bot:\nhttps://t.me/DuaSpaceHelperBot",
        "social_text": "🪐 Canale: https://t.me/DuaSpace1 | Admin: @xdua1",
        "faq_text": "💡 Tutte le risorse sono gratuite.",
        "scholarships_text": "🎓 Guide per borse di studio.",
    },
}

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

def get_user_lang(user_id):
    row = db_one("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    return row["lang"] if row and row["lang"] in TEXTS else "ar"

def set_user_lang(user_id, lang):
    db_execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))

def get_t(user_id, key):
    lang = get_user_lang(user_id)
    return TEXTS.get(lang, TEXTS["ar"]).get(key, TEXTS["ar"].get(key, ""))

def init_db():
    con = db_connect()
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                lang TEXT DEFAULT 'ar',
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

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
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

        # إدراج الكتب الجاهزة فوراً وتفادي التكرار
        for cat, b_title, b_auth, b_desc in PRELOADED_BOOKS:
            exists = con.execute("SELECT id FROM books WHERE title = ?", (b_title,)).fetchone()
            if not exists:
                con.execute(
                    "INSERT INTO books(category, title, author, description, file_id) VALUES(?, ?, ?, ?, NULL)",
                    (cat, b_title, b_auth, b_desc)
                )
        con.commit()
    finally:
        con.close()

def save_user(user, lang=None):
    if not user:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    current = db_one("SELECT lang FROM users WHERE user_id = ?", (user.id,))
    assigned_lang = lang or (current["lang"] if current else "ar")

    db_execute(
        """
        INSERT INTO users(user_id, username, first_name, lang, first_seen, last_seen)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            lang = excluded.lang,
            last_seen = excluded.last_seen
        """,
        (user.id, user.username or "", user.first_name or "", assigned_lang, now, now),
    )

def is_admin_user(user_id):
    return bool(ADMIN_ID and user_id == ADMIN_ID)

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

def force_sub_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(get_t(user_id, "sub_btn"), url=CHANNEL_URL)],
            [InlineKeyboardButton(get_t(user_id, "check_sub"), callback_data="check_subscription")],
        ]
    )

# -------------------- القوائم والأزرار --------------------

def language_selection_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇸🇦 العربية", callback_data="setlang:ar"),
                InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en"),
            ],
            [
                InlineKeyboardButton("🇫🇷 Français", callback_data="setlang:fr"),
                InlineKeyboardButton("🇮🇹 Italiano", callback_data="setlang:it"),
            ],
        ]
    )

def main_menu_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(get_t(user_id, "quran_btn"), callback_data="quran_groups")],
            [
                InlineKeyboardButton(get_t(user_id, "services"), callback_data="services"),
                InlineKeyboardButton(get_t(user_id, "portfolio"), callback_data="portfolio"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "scholarships"), callback_data="scholarships_info"),
                InlineKeyboardButton(get_t(user_id, "pomodoro"), callback_data="pomodoro_start"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "islamic_lib"), callback_data="cat:islamic"),
                InlineKeyboardButton(get_t(user_id, "medical_lib"), callback_data="cat:medical"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "lang_lib"), callback_data="cat:languages"),
                InlineKeyboardButton(get_t(user_id, "psych_lib"), callback_data="cat:psychology"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "phil_lib"), callback_data="cat:philosophy"),
                InlineKeyboardButton(get_t(user_id, "dev_lib"), callback_data="cat:selfdev"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "novels_lib"), callback_data="cat:novels"),
                InlineKeyboardButton(get_t(user_id, "topics_lib"), callback_data="cat:topics"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "quotes"), callback_data="quotes"),
                InlineKeyboardButton(get_t(user_id, "tasbeeh"), callback_data="tasbeeh"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "recommendations"), callback_data="recommend"),
                InlineKeyboardButton(get_t(user_id, "share"), callback_data="share_bot"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "follow"), callback_data="follow_us"),
                InlineKeyboardButton(get_t(user_id, "faq"), callback_data="faq_info"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "contact"), url=CONTACT_URL),
                InlineKeyboardButton(get_t(user_id, "lang_btn"), callback_data="change_lang"),
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

def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users"),
                InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton("📢 إذاعة عامة (Broadcast)", callback_data="admin_broadcast"),
                InlineKeyboardButton("📥 توصيات الأعضاء", callback_data="admin_recs"),
            ],
            [
                InlineKeyboardButton("📚 إضافة كتاب للمكتبات", callback_data="add_book_flow"),
                InlineKeyboardButton("🎨 إضافة عمل للمعرض", callback_data="add_port_flow"),
            ],
            [
                InlineKeyboardButton("💾 تحميل نسخة قاعدة البيانات", callback_data="admin_backup"),
                InlineKeyboardButton("📢 نشر تذكير فوري بالقناة", callback_data="admin_autopost_now"),
            ],
            [
                InlineKeyboardButton("👀 معاينة واجهة المستخدم", callback_data="home"),
            ],
        ]
    )

# -------------------- أوامر البدء --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    context.user_data.pop("flow", None)

    row = db_one("SELECT lang FROM users WHERE user_id = ?", (user.id,))
    if not row or not row["lang"]:
        await update.effective_message.reply_text(
            "🪐 مرحباً بك في Dua Space!\nالرجاء اختيار لغتك المفضلة / Please select your language:",
            reply_markup=language_selection_keyboard(),
        )
        return

    is_sub = await is_user_subscribed(context.bot, user.id)
    if not is_sub:
        await update.effective_message.reply_text(
            get_t(user.id, "must_subscribe"),
            reply_markup=force_sub_keyboard(user.id),
            parse_mode="Markdown",
        )
        return

    if is_admin_user(user.id):
        await update.effective_message.reply_text(
            "🪐 مرحباً بكِ في لوحة إدارة Dua Space الشاملة:\nيرجى تحديد العملية المطلوبة أدناه:",
            reply_markup=admin_keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            get_t(user.id, "welcome"),
            reply_markup=main_menu_keyboard(user.id),
        )

# -------------------- معالجة نقرات الأزرار --------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    user_id = query.from_user.id

    if data.startswith("setlang:"):
        lang_code = data.split(":", 1)[1]
        set_user_lang(user_id, lang_code)
        is_sub = await is_user_subscribed(context.bot, user_id)
        if not is_sub:
            await query.message.reply_text(
                get_t(user_id, "must_subscribe"),
                reply_markup=force_sub_keyboard(user_id),
                parse_mode="Markdown",
            )
            return

        await query.message.reply_text(
            get_t(user_id, "welcome"),
            reply_markup=main_menu_keyboard(user_id),
        )
        return

    if data == "change_lang":
        await query.message.reply_text(
            "🌐 اختر لغتك المفضلة / Choose your preferred language:",
            reply_markup=language_selection_keyboard(),
        )
        return

    if data == "check_subscription":
        is_sub = await is_user_subscribed(context.bot, user_id)
        if is_sub:
            await query.message.reply_text(get_t(user_id, "sub_success"))
            await query.message.reply_text(
                get_t(user_id, "welcome"),
                reply_markup=main_menu_keyboard(user_id),
            )
        else:
            await query.message.reply_text(
                get_t(user_id, "sub_failed"),
                reply_markup=force_sub_keyboard(user_id),
            )
        return

    if not is_admin_user(user_id) and not await is_user_subscribed(context.bot, user_id):
        await query.message.reply_text(
            get_t(user_id, "must_subscribe"),
            reply_markup=force_sub_keyboard(user_id),
            parse_mode="Markdown",
        )
        return

    if data == "home":
        context.user_data.pop("flow", None)
        await query.message.reply_text(
            get_t(user_id, "welcome"),
            reply_markup=main_menu_keyboard(user_id),
        )
        return

    if data == "quran_groups":
        await query.message.reply_text(
            "📖 **القرآن الكريم كاملاً (114 سورة):**\nيرجى اختيار المجموعة لتصفح السور والاستماع إليها مباشرة بجودة عالية:",
            reply_markup=quran_group_keyboard(),
            parse_mode="Markdown",
        )
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
        await query.message.reply_text(f"✨ سورة **{s_name}** (رقمها في المصحف: {s_num})\nيمكنك الاستماع المباشر أو قراءة الآيات والتفسير عبر الروابط أدناه:", reply_markup=kb, parse_mode="Markdown")
        return

    if data == "pomodoro_start":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⏳ بدء جلسة مذاكرة (25 دقيقة)", callback_data="pomo_run:25")],
                [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
            ]
        )
        await query.message.reply_text(
            "⏱️ **مؤقت المذاكرة والتركيز (Pomodoro Timer):**\n\nتعتمد تقنية بومودورو على التركيز التام لمدة 25 دقيقة في المذاكرة، يليها 5 دقائق استراحة.\nاضغط أدناه للبدء:",
            reply_markup=kb,
            parse_mode="Markdown",
        )
        return

    if data.startswith("pomo_run:"):
        await query.message.reply_text("🚀 بدأت جلسة التركيز الآن (25 دقيقة)!\nركز في هدفك ومذاكرتك، وسيقوم البوت بتنبيهك فور انتهاء الوقت ✨")
        asyncio.create_task(run_pomodoro(query.message.chat_id, context))
        return

    if data == "scholarships_info":
        await query.message.reply_text(
            get_t(user_id, "scholarships_text"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]),
            parse_mode="Markdown",
        )
        return

    if data == "faq_info":
        await query.message.reply_text(
            get_t(user_id, "faq_text"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]),
            parse_mode="Markdown",
        )
        return

    if data.startswith("cat:"):
        cat_key = data.split(":", 1)[1]
        cat_names = {
            "islamic": get_t(user_id, "islamic_lib"),
            "medical": get_t(user_id, "medical_lib"),
            "languages": get_t(user_id, "lang_lib"),
            "psychology": get_t(user_id, "psych_lib"),
            "philosophy": get_t(user_id, "phil_lib"),
            "selfdev": get_t(user_id, "dev_lib"),
            "novels": get_t(user_id, "novels_lib"),
            "topics": get_t(user_id, "topics_lib"),
        }
        name = cat_names.get(cat_key, "المكتبة")
        rows = db_all("SELECT id, title, author FROM books WHERE category = ? ORDER BY id ASC LIMIT 25", (cat_key,))

        if not rows:
            text = f"{name}\n\n{get_t(user_id, 'empty_sec')}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]])
            await query.message.reply_text(text, reply_markup=kb)
            return

        buttons = [
            [InlineKeyboardButton(f"📖 {r['title']} - {r['author']}", callback_data=f"open_book:{r['id']}")]
            for r in rows
        ]
        buttons.append([InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")])
        await query.message.reply_text(f"{name}\nيرجى اختيار الكتاب لعرضه:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("open_book:"):
        b_id = int(data.split(":", 1)[1])
        b = db_one("SELECT * FROM books WHERE id = ?", (b_id,))
        if b:
            caption = f"📖 **{b['title']}**\n✍️ {b['author']}\n\n{b['description']}"
            if b["file_id"]:
                try:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=b["file_id"], caption=caption)
                except Exception:
                    await query.message.reply_text(caption)
            else:
                await query.message.reply_text(caption)
        return

    if data == "quotes":
        quote = random.choice(AUTO_POSTS)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔄 اقتباس آخر", callback_data="quotes")],
                [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")],
            ]
        )
        await query.message.reply_text(f"✨ **إشراقة واقتباس ملهم:**\n\n{quote}", reply_markup=kb)
        return

    if data == "tasbeeh":
        await query.message.reply_text(
            "📿 **السبحة الإلكترونية التفاعلية:**\nاضغط على العداد للتسبيح:",
            reply_markup=tasbeeh_keyboard(0, "سبحان الله"),
            parse_mode="Markdown",
        )
        return

    if data.startswith("tcount:"):
        _, current_count, phrase = data.split(":", 2)
        new_count = int(current_count) + 1
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(new_count, phrase))
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
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text={get_t(user_id, 'share_text')}"
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🚀 إرسال الرابط لأصدقائك الآن", url=share_url)],
                [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")],
            ]
        )
        await query.message.reply_text("🪐 يسعدنا ويشرفنا مشاركتكم Dua Space مع أصدقائكم:", reply_markup=kb)
        return

    if data == "follow_us":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]])
        await query.message.reply_text(get_t(user_id, "social_text"), reply_markup=kb)
        return

    if data == "recommend":
        context.user_data["flow"] = {"kind": "rec_msg"}
        await query.message.reply_text(get_t(user_id, "rec_prompt"))
        return

    if data == "portfolio":
        rows = db_all("SELECT id, title FROM portfolio ORDER BY id DESC LIMIT 15")
        if not rows:
            await query.message.reply_text(
                "🎨 مرحباً بكم في معرض أعمال Dua Space!\nيجري حالياً رفع وتنسيق نماذج أعمالنا وتصاميمنا المميزة قريباً جداً 🪐",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]),
            )
        else:
            buttons = [
                [InlineKeyboardButton(f"🖼️ {r['title']}", callback_data=f"show_port:{r['id']}")]
                for r in rows
            ]
            buttons.append([InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")])
            await query.message.reply_text("🎨 نماذج من أعمال Dua Space:\nاختر العمل لمشاهدته:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("show_port:"):
        p_id = int(data.split(":", 1)[1])
        item = db_one("SELECT * FROM portfolio WHERE id = ?", (p_id,))
        if item:
            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=item["file_id"],
                    caption=f"🎨 **{item['title']}**\n\n{item['description']}",
                    parse_mode="Markdown",
                )
            except Exception:
                await query.message.reply_text(f"🎨 **{item['title']}**\n\n{item['description']}")
        return

    # وظائف الإدارة
    if not is_admin_user(user_id):
        return

    if data == "admin_home":
        await query.message.reply_text("🎛️ لوحة إدارة Dua Space الشاملة:", reply_markup=admin_keyboard())

    elif data == "admin_autopost_now":
        post_text = random.choice(AUTO_POSTS) + "\n\n—\n🪐 Dua Space • مساحتكم للإبداع والمعرفة"
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            await query.message.reply_text("✅ تم إرسال ونشر تذكير فوري في القناة بنجاح.")
        except Exception as exc:
            await query.message.reply_text(f"❌ تعذر النشر في القناة: {exc}")

    elif data == "admin_backup":
        if os.path.exists(DB_PATH):
            await context.bot.send_document(
                chat_id=user_id,
                document=open(DB_PATH, "rb"),
                caption=f"💾 نسخة احتياطية كاملة لقاعدة بيانات Dua Space.\nتاريخ: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            )
        else:
            await query.message.reply_text("ملف قاعدة البيانات غير متوفر حالياً.")

    elif data == "admin_users":
        rows = db_all("SELECT user_id, username, first_name, lang, last_seen FROM users ORDER BY last_seen DESC LIMIT 50")
        if not rows:
            await query.message.reply_text("لا يوجد مستخدمون مسجلون بعد.")
            return
        text = f"👥 **قائمة مستخدمي البوت ({len(rows)}):**\n\n"
        for idx, u in enumerate(rows, 1):
            un = f"@{u['username']}" if u["username"] else "بدون يوزر"
            text += f"{idx}. {u['first_name'] or 'مستخدم'} ({un})\n   • ID: `{u['user_id']}` | اللغة: {u['lang']}\n"
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")]]), parse_mode="Markdown")

    elif data == "admin_stats":
        u_count = db_one("SELECT COUNT(*) AS n FROM users")["n"]
        b_count = db_one("SELECT COUNT(*) AS n FROM books")["n"]
        p_count = db_one("SELECT COUNT(*) AS n FROM portfolio")["n"]
        r_count = db_one("SELECT COUNT(*) AS n FROM recommendations")["n"]
        text = (
            "📊 **تقرير إحصائيات Dua Space الشامل:**\n\n"
            f"• إجمالي المستخدمين: {u_count}\n"
            f"• إجمالي الكتب المسجلة: {b_count}\n"
            f"• أعمال المعرض: {p_count}\n"
            f"• توصيات الأعضاء: {r_count}\n"
        )
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")]]))

    elif data == "admin_broadcast":
        context.user_data["flow"] = {"kind": "broadcast"}
        await query.message.reply_text("📢 أرسلي الرسالة التي تودين بثها لجميع المستخدمين:")

    elif data == "admin_recs":
        rows = db_all("SELECT username, content FROM recommendations ORDER BY id DESC LIMIT 15")
        if not rows:
            await query.message.reply_text("لا توجد توصيات مرسلة حتى الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")]]))
            return
        text = "🌟 **أحدث مقترحات الأعضاء:**\n\n"
        for r in rows:
            u = f"@{r['username']}" if r["username"] else "عضو"
            text += f"• من: {u}\nالتوصية: {r['content']}\n—\n"
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ لوحة الإدارة", callback_data="admin_home")]]))

    elif data == "add_book_flow":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🕌 إسلامية", callback_data="set_bcat:islamic"), InlineKeyboardButton("🩺 طبية", callback_data="set_bcat:medical")],
                [InlineKeyboardButton("🌍 لغات", callback_data="set_bcat:languages"), InlineKeyboardButton("🧠 علم نفس", callback_data="set_bcat:psychology")],
                [InlineKeyboardButton("🏛️ فكر وفلسفة", callback_data="set_bcat:philosophy"), InlineKeyboardButton("💡 تطوير ذات", callback_data="set_bcat:selfdev")],
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

async def run_pomodoro(chat_id, context):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔔 **انتهت الـ 25 دقيقة!**\nعمل رائع، خذ الآن استراحة لمدة 5 دقائق لإنعاش ذهنك ثم واصل إنجازك ✨",
            parse_mode="Markdown",
        )
    except Exception:
        pass

async def channel_auto_poster(bot):
    while True:
        try:
            await asyncio.sleep(4 * 3600)
            selected = random.choice(AUTO_POSTS)
            text = f"{selected}\n\n—\n🪐 Dua Space • مساحتكم للإبداع والمعرفة"
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            logger.info("Auto post published to channel successfully.")
        except Exception as e:
            logger.warning(f"Auto post error: {e}")
            await asyncio.sleep(300)

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not msg.text:
        return

    flow = context.user_data.get("flow")

    if flow and flow.get("kind") == "rec_msg":
        content = msg.text.strip()
        db_execute("INSERT INTO recommendations(user_id, username, content) VALUES(?, ?, ?)", (user.id, user.username or "", content))
        context.user_data.pop("flow", None)
        await msg.reply_text(get_t(user.id, "rec_sent"), reply_markup=main_menu_keyboard(user.id))
        return

    if is_admin_user(user.id) and flow:
        kind = flow.get("kind")
        val = msg.text.strip()

        if kind == "broadcast":
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
            context.user_data["flow"] = {"kind": "b_file"}
            await msg.reply_text("أرسلي ملف الكتاب (PDF)، أو اكتبي (بدون):")
            return

        elif kind == "b_file" and val == "بدون":
            p = context.user_data.pop("pending_book", {})
            context.user_data.pop("flow", None)
            db_execute("INSERT INTO books(category, title, author, description, file_id) VALUES(?, ?, ?, ?, NULL)", (p["category"], p["title"], p["author"], p["description"]))
            await msg.reply_text("✅ تمت إضافة الكتاب بنجاح للمكتبة!", reply_markup=admin_keyboard())
            return

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
        db_execute("INSERT INTO books(category, title, author, description, file_id) VALUES(?, ?, ?, ?, ?)", (p["category"], p["title"], p["author"], p["description"], doc.file_id))
        await update.effective_message.reply_text("✅ تم حفظ ملف الكتاب وربطه بالقسم بنجاح!", reply_markup=admin_keyboard())
        return

async def handle_health(request):
    return web.Response(text="Dua Space Complete Ecosystem Live 🪐", status=200)

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

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", lambda u, c: u.effective_message.reply_text("🎛️ لوحة إدارة Dua Space:", reply_markup=admin_keyboard()) if is_admin_user(u.effective_user.id) else None))
    application.add_handler(CommandHandler("cancel", lambda u, c: u.effective_message.reply_text("تم الإلغاء.") if c.user_data.pop("flow", None) is not None else None))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    application.add_handler(MessageHandler(filters.ATTACHMENT, file_handler))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Dua Space Complete Ecosystem is running.")

        asyncio.create_task(channel_auto_poster(application.bot))

        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
