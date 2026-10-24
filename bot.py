# -*- coding: utf-8 -*-
# Dua Space Engine - Ultimate Multi-Language & Fully Managed Edition
# Python 3.11+ | PTB 21.10 | Render Free Compatible

import os
import sqlite3
import logging
import asyncio
from datetime import datetime, timezone
from functools import wraps

from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# الآيدي الخاص بكِ مثبت مباشرة لضمان الصلاحيات الإدارية المطلقة
HARDCODED_ADMIN = 8669779200
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

try:
    ENV_ADMIN = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ENV_ADMIN = 0

ADMIN_ID = ENV_ADMIN if ENV_ADMIN != 0 else HARDCODED_ADMIN
CHANNEL_ID = os.getenv("CHANNEL_ID", "@DuaSpace1").strip()
CHANNEL_URL = "https://t.me/DuaSpace1"
DATABASE_PATH = os.getenv("DATABASE_PATH", "dua_space.db")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("DuaSpace")

# ==================================================
# قاعدة البيانات والزرع التلقائي للبيانات المتكاملة
# ==================================================

def db_connect():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def now_text():
    return datetime.now(timezone.utc).isoformat()

def init_database():
    with db_connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            language TEXT DEFAULT 'ar',
            joined_at TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            description_ar TEXT DEFAULT '',
            description_en TEXT DEFAULT '',
            position INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title_ar TEXT NOT NULL,
            title_en TEXT NOT NULL,
            description_ar TEXT DEFAULT '',
            description_en TEXT DEFAULT '',
            url TEXT DEFAULT '',
            file_id TEXT DEFAULT '',
            media_type TEXT DEFAULT 'text',
            added_at TEXT NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS designs (
            design_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_ar TEXT NOT NULL,
            title_en TEXT NOT NULL,
            description_ar TEXT DEFAULT '',
            description_en TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS adhkar (
            dhikr_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            text TEXT NOT NULL,
            reward TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS quiz (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_ar TEXT NOT NULL,
            question_en TEXT NOT NULL,
            opt1 TEXT NOT NULL,
            opt2 TEXT NOT NULL,
            opt3 TEXT NOT NULL,
            opt4 TEXT NOT NULL,
            answer INTEGER NOT NULL,
            explanation_ar TEXT NOT NULL,
            explanation_en TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # الإعدادات الافتراضية
        defaults = {
            "maintenance": "0",
            "force_subscription": "1",
            "welcome_ar": "أهلًا بكِ في Dua Space 🌙\n\nمساحتكِ المعرفية المتكاملة للتعلم، اللغات، الكتب، وخدمات التصميم الرقمي.",
            "welcome_en": "Welcome to Dua Space 🌙\n\nYour comprehensive space for learning, languages, books, and creative design services.",
            "design_intro_ar": "🎨 **خدمات التصميم الاحترافي من Dua Space:**\nنقدم تصاميم إبداعية عالية الدقة والاحترافية. يتم تحديد السعر والتفاصيل بالاتفاق المباشر وفق متطلباتكِ المحددة.",
            "design_intro_en": "🎨 **Creative Design Services by Dua Space:**\nWe provide high-quality custom graphic designs. Pricing and specifications are tailored directly to your project needs.",
        }
        for k, v in defaults.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # زرع أقسام المكتبة المعرفية مع 6 لغات أساسية
        default_cats = [
            ("إسلاميات وعلوم دينية", "Islamic Studies", "المصاحف، التفسير، الحديث النبوي، والفقه", "Quran, Hadith, Tafsir and Islamic Jurisprudence", 1),
            ("الطب والعلوم الصحية", "Medicine & Health", "مراجع التشريح، وظائف الأعضاء، وعلم الأحياء", "Anatomy, Physiology, Biology, and Medical Resources", 2),
            ("تعلّم اللغات (6 لغات)", "Language Learning", "العربية، الإنجليزية، التركية، الكورية، اليابانية، والصينية", "Arabic, English, Turkish, Korean, Japanese, Chinese", 3),
            ("الهندسة والتقنية", "Engineering & Tech", "البرمجة، الخوارزميات، والذكاء الاصطناعي", "Programming, Algorithms, AI, and Software Engineering", 4),
            ("الأدب والروايات وتطوير الذات", "Literature & Self-Dev", "روائع الأدب العالمي، بناء العادات، والفلسفة", "Global Literature, Habit Building, and Personal Growth", 5),
        ]
        for c_ar, c_en, d_ar, d_en, pos in default_cats:
            row = db.execute("SELECT category_id FROM categories WHERE name_ar = ?", (c_ar,)).fetchone()
            if not row:
                db.execute("INSERT INTO categories (name_ar, name_en, description_ar, description_en, position) VALUES (?, ?, ?, ?, ?)",
                           (c_ar, c_en, d_ar, d_en, pos))

        # كتب ومراجع حقيقية ومصادر عالمية مباشرة (بدون روابط داخلية)
        books_seed = [
            # إسلاميات
            ("إسلاميات وعلوم دينية", "المصحف الشريف والتفاسير (مجمع الملك فهد)", "The Holy Quran & Tafsir", "تصفح وتحميل القرآن الكريم وتفاسيره المعتمدة", "King Fahd Complex Digital Quran", "https://qurancomplex.gov.sa/"),
            ("إسلاميات وعلوم دينية", "جامع صحيح البخاري وصحيح مسلم", "Sahih al-Bukhari & Muslim", "متون الحديث الصحيحة مع الشرح والتخريج", "Authentic Hadith Collections", "https://sunnah.com/"),
            # الطب والعلوم
            ("الطب والعلوم الصحية", "المكتبة الطبية الوطنية العالمية (PubMed)", "National Library of Medicine", "أكبر قاعدة أبحاث ومراجع طبية مجانية في العالم", "Global Biomedical Research Database", "https://pubmed.ncbi.nlm.nih.gov/"),
            ("الطب والعلوم الصحية", "أطلس تشريح جسم الإنسان (OpenStax)", "Anatomy & Physiology Textbook", "كتاب منهجي مفتوح المصدر في تشريح ووظائف الأعضاء", "Peer-reviewed OpenStax Textbook", "https://openstax.org/details/books/anatomy-and-physiology-2e"),
            # اللغات الستة
            ("تعلّم اللغات (6 لغات)", "اللغة العربية: المعاجم وعلوم النحو (الباحث العربي)", "Arabic Lexicons & Grammar", "معاجم لسان العرب والقاموس المحيط وقواعد الفصحى", "Comprehensive Arabic Dictionaries", "https://baheth.net/"),
            ("تعلّم اللغات (6 لغات)", "English: Oxford Open Learning & Grammar Guide", "English Grammar & Vocabulary", "دليل أوكسفورد الشامل لقواعد الإنجليزية وبناء المفردات", "Comprehensive Grammar Reference", "https://www.oxfordlearnersdictionaries.com/"),
            ("تعلّم اللغات (6 لغات)", "Türkçe: Yunus Emre Enstitüsü Türkçe Öğrenim", "Turkish Language Portal", "المنهج التركي الرسمي لتعلم اللغة التركية من الصفر", "Official Turkish Learning Resources", "https://turkce.yee.org.tr/"),
            ("تعلّم اللغات (6 لغات)", "한국어: National Institute of Korean Language (K-Learners)", "Korean Study Guide", "المعهد الوطني للغة الكورية وقواعد الهانغول للمبتدئين", "Official Korean Language Resources", "https://www.korean.go.kr/"),
            ("تعلّم اللغات (6 لغات)", "日本語: Japan Foundation Japanese-Language Guide", "Japanese Learning Portal", "مؤسسة اليابان الرسمية لتعلم الهيراغانا والكانجي والمحادثة", "Official Japan Foundation Resources", "https://www.jpf.go.jp/"),
            ("تعلّم اللغات (6 لغات)", "中文: Chinese Grammar Wiki & Hanzi Guide", "Mandarin Chinese Wiki", "مرجع قواعد لغة الماندرين وكتابة الرموز الصينية", "Mandarin Grammar & Stroke Order Portal", "https://resources.allsetlearning.com/chinese/grammar/"),
            # الهندسة
            ("الهندسة والتقنية", "بايثون الرسمية: توثيق ودروس المبتدئين", "Python Official Documentation", "المرجع الشامل للغة بايثون والمكتبات القياسية", "Official Python 3 Docs & Tutorials", "https://docs.python.org/3/tutorial/"),
            ("الهندسة والتقنية", "MIT OpenCourseWare: علوم الحاسوب والبرمجة", "MIT Computer Science Portal", "محاضرات ومراجع معهد ماساتشوستس للتقنية مجاناً", "Free MIT Course Materials", "https://ocw.mit.edu/courses/electrical-engineering-and-computer-science/"),
            # الأدب وتطوير الذات
            ("الأدب والروايات وتطوير الذات", "مكتبة غوتنبرغ العالمية (Project Gutenberg)", "Project Gutenberg Global Classics", "أكثر من 70 ألف كتاب ورواية كلاسيكية عالمية مجانية", "Free Classic World eBooks", "https://www.gutenberg.org/"),
            ("الأدب والروايات وتطوير الذات", "مكتبة هنداوي المفتوحة (روايات وفلسفة)", "Hindawi Digital Library", "آلاف الروايات العربية والمترجمة وكتب تطوير الشخصية", "Free Arabic & Translated eBooks", "https://www.hindawi.org/books/"),
        ]
        for cat_ar, t_ar, t_en, d_ar, d_en, url in books_seed:
            row = db.execute("SELECT category_id FROM categories WHERE name_ar = ?", (cat_ar,)).fetchone()
            if row:
                cid = row["category_id"]
                exists = db.execute("SELECT 1 FROM books WHERE title_ar = ?", (t_ar,)).fetchone()
                if not exists:
                    db.execute("INSERT INTO books (category_id, title_ar, title_en, description_ar, description_en, url, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (cid, t_ar, t_en, d_ar, d_en, url, now_text()))

        # خدمات التصميم (بدون أسعار محددة مسبقاً)
        design_services = [
            ("تصميم الهويات البصرية والشعارات", "Brand Identity & Logo Design", "ابتكار شعارات احترافية، اختيار الألوان، وتصميم كتيب الهوية الكامل", "Custom logos, color schemes, and full corporate branding identity"),
            ("تصاميم السوشيال ميديا والإعلانات", "Social Media & Ad Creative", "تصميم منشورات، بنرات، وقوالب إعلانية جذابة لمنصات التواصل", "High-conversion post graphics, covers, and promotional creative"),
            ("تصميم أغلفة الكتب والمجلات", "Book & Publication Covers", "تصاميم أغلفة إبداعية جاهزة للطباعة والنشر الرقمي بجودة فائقة", "Striking front and back covers designed for print and digital publishing"),
            ("تصميم العروض التقديمية والملفات التفاعلية", "Presentations & Pitch Decks", "تصميم شرائح PowerPoint و PDF تفاعلية للمشاريع والمحاضرات", "Professional, visually compelling slide decks and documents"),
            ("تصميم بطاقات وتطبيقات المطبوعات", "Print & Stationery Materials", "تصميم كروت شخصية، فلايرات، بروشورات، ورول أب احترافي", "Business cards, flyers, brochures, and commercial print materials"),
        ]
        for t_ar, t_en, d_ar, d_en in design_services:
            exists = db.execute("SELECT 1 FROM designs WHERE title_ar = ?", (t_ar,)).fetchone()
            if not exists:
                db.execute("INSERT INTO designs (title_ar, title_en, description_ar, description_en) VALUES (?, ?, ?, ?)",
                           (t_ar, t_en, d_ar, d_en))

        # باقة الأذكار
        adhkar_seed = [
            ("أذكار", "أَصْبَحْنَا وَأَصْبَحَ المُلْكُ لِلَّهِ، وَالحَمْدُ لِلَّهِ لا إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لا شَرِيكَ لَهُ.", "حفظ ونماء وطمأنينة اليوم وبركته"),
            ("أذكار", "اللَّهُمَّ لا سَهْلَ إِلاَّ ما جَعَلْتَهُ سَهْلاً، وأَنْتَ تَجْعَلُ الحَزْنَ إِذَا شِئْتَ سَهْلاً.", "تيسير الحفظ والدراسة والأمور الصعبة"),
            ("أذكار", "أَسْتَغْفِرُ اللَّهَ العَظِيمَ الَّذِي لا إِلَهَ إِلاَّ هُوَ الحَيُّ القَيُّومُ وَأَتُوبُ إِلَيْهِ.", "مغفرة الذنوب، سعة الرزق، وانشراح الصدر"),
            ("أذكار", "لا حَوْلَ وَلا قُوَّةَ إِلاَّ بِاللَّهِ العَلِيِّ العَظِيمِ.", "كنز من كنوز الجنة ودفع للهم والحزن"),
            ("أذكار", "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ العَظِيمِ.", "كلمتان خفيفتان على اللسان ثقيلتان في الميزان"),
        ]
        for c, t, r in adhkar_seed:
            exists = db.execute("SELECT 1 FROM adhkar WHERE text = ?", (t,)).fetchone()
            if not exists:
                db.execute("INSERT INTO adhkar (category, text, reward) VALUES (?, ?, ?)", (c, t, r))

        # بنك الأسئلة باللغتين
        quizzes = [
            ("ما هو العضو الذي يضخ الدم لجميع أنحاء الجسم؟", "Which organ pumps blood throughout the human body?", "الرئة (Lung)", "القلب (Heart)", "الكبد (Liver)", "الكلى (Kidney)", 2, "القلب هو العضلة المركزية في جهاز الدوران.", "The heart is the central muscular organ of the circulatory system."),
            ("كم عدد أركان الإسلام الأساسية؟", "How many are the fundamental Pillars of Islam?", "4", "5", "6", "7", 2, "بني الإسلام على خمس دعائم أساسية.", "Islam is founded upon five essential pillars."),
            ("ما هي أصغر وحدة بنائية في الكائن الحي؟", "What is the basic structural unit of all living organisms?", "الخلية (Cell)", "الذرة (Atom)", "النسيج (Tissue)", "العضو (Organ)", 1, "الخلية هي الوحدة التركيبية والوظيفية الأساسية للحياة.", "The cell is the basic structural and functional unit of life."),
            ("ما هو أكبر كواكب مجموعتنا الشمسية حجماً؟", "Which planet is the largest in our solar system?", "الأرض (Earth)", "زحل (Saturn)", "المشتري (Jupiter)", "المريخ (Mars)", 3, "كوكب المشتري هو الأكبر حجماً وكتلة في المجموعة الشمسية.", "Jupiter is by far the most massive and largest planet in the solar system."),
        ]
        for q_ar, q_en, o1, o2, o3, o4, ans, exp_ar, exp_en in quizzes:
            exists = db.execute("SELECT 1 FROM quiz WHERE question_ar = ?", (q_ar,)).fetchone()
            if not exists:
                db.execute("INSERT INTO quiz (question_ar, question_en, opt1, opt2, opt3, opt4, answer, explanation_ar, explanation_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (q_ar, q_en, o1, o2, o3, o4, ans, exp_ar, exp_en))

def get_setting(key, default=""):
    with db_connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    with db_connect() as db:
        db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))

def get_user_lang(user_id):
    with db_connect() as db:
        row = db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return row["language"] if row and row["language"] else "ar"

def set_user_lang(user_id, lang):
    with db_connect() as db:
        db.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))

# ==================================================
# نظام الصلاحيات الإدارية المطلقة
# ==================================================

def is_owner(user_id: int) -> bool:
    return int(user_id) in (ADMIN_ID, HARDCODED_ADMIN)

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not is_owner(user.id):
            if update.callback_query:
                await update.callback_query.answer("⚠️ هذه اللوحة مخصصة لإدارة المنصة فقط.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text("⚠️ عذراً، هذا الأمر مخصص لمالكة المنصة فقط.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def register_user(user):
    with db_connect() as db:
        db.execute("""
            INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name, last_seen=excluded.last_seen
        """, (user.id, user.username or "", user.full_name or "", now_text(), now_text()))

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if get_setting("force_subscription", "1") != "1" or is_owner(user_id):
        return True
    try:
        m = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return m.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return True

# ==================================================
# القوائم والواجهات متعددة اللغات
# ==================================================

def main_menu_keyboard(lang="ar"):
    if lang == "en":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 Dua Space Library", callback_data="nav:library"), InlineKeyboardButton("🎨 Design Services", callback_data="nav:design")],
            [InlineKeyboardButton("📿 Adhkar & Tasbeeh", callback_data="nav:adhkar"), InlineKeyboardButton("🧠 Quizzes & Trivia", callback_data="nav:quiz")],
            [InlineKeyboardButton("⏱️ Focus Timer (Pomodoro)", callback_data="nav:pomo"), InlineKeyboardButton("💬 Contact Support", callback_data="nav:support")],
            [InlineKeyboardButton("🌐 Language / اللغة", callback_data="nav:lang")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 مكتبة Dua Space المعرفية", callback_data="nav:library"), InlineKeyboardButton("🎨 خدمات التصميم", callback_data="nav:design")],
        [InlineKeyboardButton("📿 الأذكار والسبحة الرقمية", callback_data="nav:adhkar"), InlineKeyboardButton("🧠 التحديات والمسابقات", callback_data="nav:quiz")],
        [InlineKeyboardButton("⏱️ مؤقت التركيز (Pomodoro)", callback_data="nav:pomo"), InlineKeyboardButton("💬 تواصل مع الإدارة", callback_data="nav:support")],
        [InlineKeyboardButton("🌐 تغيير اللغة / Language", callback_data="nav:lang")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    register_user(user)
    lang = get_user_lang(user.id)

    if get_setting("maintenance", "0") == "1" and not is_owner(user.id):
        txt = "🛠️ البوت حالياً في وضع التحديث والصيانة لتحسين التجربة. نعود إليكم بعد قليل!" if lang == "ar" else "🛠️ Dua Space is currently under maintenance. We will be back shortly!"
        await msg.reply_text(txt)
        return

    if not await check_subscription(user.id, context):
        if lang == "en":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join our Official Channel", url=CHANNEL_URL)],
                [InlineKeyboardButton("✅ Joined, Activate Bot", callback_data="nav:check_sub")]
            ])
            await msg.reply_text("Welcome to Dua Space 🌙\nPlease join our official channel to access all features:", reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 اشتركي في قناتنا الرسمية", url=CHANNEL_URL)],
                [InlineKeyboardButton("✅ تم الاشتراك، تفعيل البوت", callback_data="nav:check_sub")]
            ])
            await msg.reply_text("أهلاً بكِ في Dua Space 🌙\nيرجى الانضمام لقناتنا الرسمية للاستفادة من كامل خدمات البوت:", reply_markup=kb)
        return

    welcome = get_setting("welcome_en" if lang == "en" else "welcome_ar")
    await msg.reply_text(welcome, reply_markup=main_menu_keyboard(lang))

# ==================================================
# التصفح والتفاعل
# ==================================================

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    lang = get_user_lang(uid)

    if data == "nav:check_sub":
        if await check_subscription(uid, context):
            welcome = get_setting("welcome_en" if lang == "en" else "welcome_ar")
            await query.edit_message_text(welcome, reply_markup=main_menu_keyboard(lang))
        else:
            await query.answer("لم يتم التحقق من الاشتراك في القناة بعد." if lang == "ar" else "Subscription check failed. Please join the channel.", show_alert=True)

    elif data == "nav:home":
        context.user_data.pop("state", None)
        welcome = get_setting("welcome_en" if lang == "en" else "welcome_ar")
        await query.edit_message_text(welcome, reply_markup=main_menu_keyboard(lang))

    # --- تبديل اللغة ---
    elif data == "nav:lang":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="setlang:ar"), InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en")],
            [InlineKeyboardButton("↩️ Back / رجوع", callback_data="nav:home")]
        ])
        await query.edit_message_text("🌐 **اختر لغة العرض / Choose your display language:**", reply_markup=kb, parse_mode="Markdown")

    elif data.startswith("setlang:"):
        new_lang = data.split(":")[1]
        set_user_lang(uid, new_lang)
        await query.answer("تم تغيير اللغة بنجاح!" if new_lang == "ar" else "Language updated successfully!")
        welcome = get_setting("welcome_en" if new_lang == "en" else "welcome_ar")
        await query.edit_message_text(welcome, reply_markup=main_menu_keyboard(new_lang))

    # --- مكتبة الكتب والمراجع المفتوحة ---
    elif data == "nav:library":
        with db_connect() as db:
            cats = db.execute("SELECT category_id, name_ar, name_en FROM categories ORDER BY position, category_id").fetchall()
        kb = []
        for c in cats:
            name = c["name_en"] if lang == "en" else c["name_ar"]
            kb.append([InlineKeyboardButton(f"📂 {name}", callback_data=f"lib:cat:{c['category_id']}")])
        kb.append([InlineKeyboardButton("🏠 Main Menu" if lang == "en" else "🏠 القائمة الرئيسية", callback_data="nav:home")])
        header = "📚 **Dua Space Digital Library:**\nSelect a field to view textbooks, research databases, and learning portals:" if lang == "en" else "📚 **مكتبة Dua Space الرقمية والمعرفية:**\nاختاري المجال المطلوب لتصفح المراجع، المصاحف، معاجم اللغات، والمصادر العالمية:"
        await query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("lib:cat:"):
        cid = int(data.split(":")[2])
        with db_connect() as db:
            cat = db.execute("SELECT * FROM categories WHERE category_id = ?", (cid,)).fetchone()
            bks = db.execute("SELECT * FROM books WHERE category_id = ? ORDER BY book_id DESC", (cid,)).fetchall()

        c_name = cat["name_en"] if lang == "en" else cat["name_ar"]
        c_desc = cat["description_en"] if lang == "en" else cat["description_ar"]

        kb = []
        for b in bks:
            btitle = b["title_en"] if lang == "en" and b["title_en"] else b["title_ar"]
            kb.append([InlineKeyboardButton(f"📖 {btitle}", callback_data=f"lib:view:{b['book_id']}")])
        kb.append([InlineKeyboardButton("⬅️ Back to Categories" if lang == "en" else "⬅️ رجوع للأقسام", callback_data="nav:library")])

        if lang == "en":
            text = f"📂 **Category: {c_name}**\n_{c_desc}_\n\n"
            text += "Available References & Materials:" if bks else "No materials added in this section yet."
        else:
            text = f"📂 **قسم: {c_name}**\n_{c_desc}_\n\n"
            text += "المراجع والمصادر المتوفرة في هذا القسم:" if bks else "لا توجد مواد مضافة في هذا القسم حالياً."

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("lib:view:"):
        bid = int(data.split(":")[2])
        with db_connect() as db:
            bk = db.execute("SELECT * FROM books WHERE book_id = ?", (bid,)).fetchone()

        btitle = bk["title_en"] if lang == "en" and bk["title_en"] else bk["title_ar"]
        bdesc = bk["description_en"] if lang == "en" and bk["description_en"] else bk["description_ar"]

        kb = []
        if bk["url"]:
            btn_txt = "🌐 Open Direct Source / المرجع المباشر" if lang == "en" else "🌐 الدخول للمصدر المباشر المعتمد"
            kb.append([InlineKeyboardButton(btn_txt, url=bk["url"])])
        kb.append([InlineKeyboardButton("⬅️ Back" if lang == "en" else "⬅️ رجوع", callback_data=f"lib:cat:{bk['category_id']}")])

        caption_txt = f"📖 **{btitle}**\n\n{bdesc or ''}"

        # إرسال الملف المباشر (PDF / فيديو / صورة) في الشات إن وجد
        if bk["file_id"]:
            cid = query.from_user.id
            try:
                if bk["media_type"] == "document":
                    await context.bot.send_document(chat_id=cid, document=bk["file_id"], caption=caption_txt, parse_mode="Markdown")
                elif bk["media_type"] == "video":
                    await context.bot.send_video(chat_id=cid, video=bk["file_id"], caption=caption_txt, parse_mode="Markdown")
                elif bk["media_type"] == "photo":
                    await context.bot.send_photo(chat_id=cid, photo=bk["file_id"], caption=caption_txt, parse_mode="Markdown")
            except Exception as e:
                logger.error("Failed sending media file: %s", e)
        else:
            await query.edit_message_text(caption_txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    # --- خدمات التصميم (بدون أسعار محددة) ---
    elif data == "nav:design":
        with db_connect() as db:
            items = db.execute("SELECT * FROM designs").fetchall()
        intro = get_setting("design_intro_en" if lang == "en" else "design_intro_ar")
        text = f"{intro}\n\n"
        for itm in items:
            t = itm["title_en"] if lang == "en" else itm["title_ar"]
            d = itm["description_en"] if lang == "en" else itm["description_ar"]
            text += f"▫️ **{t}**\n_{d}_\n\n"

        if lang == "en":
            text += "📩 To request any design service or discuss details, click the button below:"
            kb = [
                [InlineKeyboardButton("✍️ Request a Design Service", callback_data="order:design")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="nav:home")]
            ]
        else:
            text += "📩 لطلب أي خدمة وتحديد المواصفات والاتفاق المباشر، اضغطي على زر طلب تصميم:"
            kb = [
                [InlineKeyboardButton("✍️ طلب خدمة تصميم الآن", callback_data="order:design")],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="nav:home")]
            ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "order:design":
        context.user_data["state"] = "waiting_design_order"
        prompt = "🎨 Please write your design requirements in one message, and our team will get in touch directly:" if lang == "en" else "🎨 أرسلي مواصفات التصميم الذي ترغبين به وسنتواصل معكِ للاتفاق على التفاصيل فوراً:"
        await query.message.reply_text(prompt)

    # --- واحة الأذكار والسبحة ---
    elif data == "nav:adhkar":
        with db_connect() as db:
            adh = db.execute("SELECT * FROM adhkar ORDER BY RANDOM() LIMIT 1").fetchone()
        c = context.user_data.get("tasbeeh_count", 0)
        text = (
            "📿 **واحة الذكر والتسبيح الإلكتروني**\n\n"
            f"🌿 *ذكر مختار:*\n« {adh['text']} »\n\n"
            f"💡 *الفضل:* {adh['reward']}\n\n"
            f"🔢 **عداد التسبيح الحالي:** `{c}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📿 سبّح (+1)", callback_data="tasbeeh:inc")],
            [InlineKeyboardButton("🔄 تصفير العداد", callback_data="tasbeeh:zero"), InlineKeyboardButton("🌿 ذكر آخر", callback_data="nav:adhkar")],
            [InlineKeyboardButton("🏠 الرئيسية / Main Menu", callback_data="nav:home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "tasbeeh:inc":
        c = context.user_data.get("tasbeeh_count", 0) + 1
        context.user_data["tasbeeh_count"] = c
        await query.answer(f"سبحان الله وبحمده ({c})")
        with db_connect() as db:
            adh = db.execute("SELECT * FROM adhkar ORDER BY RANDOM() LIMIT 1").fetchone()
        text = (
            "📿 **واحة الذكر والتسبيح الإلكتروني**\n\n"
            f"🌿 *ذكر مختار:*\n« {adh['text']} »\n\n"
            f"💡 *الفضل:* {adh['reward']}\n\n"
            f"🔢 **عداد التسبيح الحالي:** `{c}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📿 سبّح (+1)", callback_data="tasbeeh:inc")],
            [InlineKeyboardButton("🔄 تصفير العداد", callback_data="tasbeeh:zero"), InlineKeyboardButton("🌿 ذكر آخر", callback_data="nav:adhkar")],
            [InlineKeyboardButton("🏠 الرئيسية / Main Menu", callback_data="nav:home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "tasbeeh:zero":
        context.user_data["tasbeeh_count"] = 0
        await query.answer("تم تصفير العداد.")
        await handle_navigation(update, context)

    # --- مؤقت بومودورو للتركيز والمذاكرة ---
    elif data == "nav:pomo":
        txt = "⏱️ Focus timer started for 25 minutes! Work hard and stay focused 🎯" if lang == "en" else "⏱️ بدأ مؤقت التركيز لمدة 25 دقيقة! استثمري وقتكِ في الإنجاز والدراسة 🎯"
        await query.message.reply_text(txt)
        asyncio.create_task(pomo_timer(query.message.chat_id, context, lang))

    # --- بنك المسابقات والتحديات ---
    elif data == "nav:quiz":
        with db_connect() as db:
            q = db.execute("SELECT * FROM quiz ORDER BY RANDOM() LIMIT 1").fetchone()
        context.user_data["current_q"] = dict(q)
        q_title = q["question_en"] if lang == "en" else q["question_ar"]
        kb = [
            [InlineKeyboardButton(q["opt1"], callback_data="q:ans:1")],
            [InlineKeyboardButton(q["opt2"], callback_data="q:ans:2")],
            [InlineKeyboardButton(q["opt3"], callback_data="q:ans:3")],
            [InlineKeyboardButton(q["opt4"], callback_data="q:ans:4")],
            [InlineKeyboardButton("🏠 Main Menu" if lang == "en" else "🏠 الرئيسية", callback_data="nav:home")]
        ]
        text = f"🧠 **{q_title}**\n\nChoose the correct answer:" if lang == "en" else f"🧠 **{q_title}**\n\nاختاري الإجابة الصحيحة:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("q:ans:"):
        choice = int(data.split(":")[2])
        q = context.user_data.get("current_q")
        if not q:
            await query.edit_message_text("Session expired.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 New Question", callback_data="nav:quiz")]]))
            return
        correct = (choice == q["answer"])
        exp = q["explanation_en"] if lang == "en" else q["explanation_ar"]
        header = ("🎉 Correct! Outstanding." if correct else "❌ Incorrect answer.") if lang == "en" else ("🎉 إجابة صحيحة وممتازة جداً!" if correct else "❌ إجابة غير صحيحة.")
        text = f"{header}\n\n💡 **Explanation / الشرح:**\n{exp}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 Next Question / سؤال آخر", callback_data="nav:quiz")],
            [InlineKeyboardButton("🏠 Main Menu / الرئيسية", callback_data="nav:home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # --- الدعم والتواصل ---
    elif data == "nav:support":
        context.user_data["state"] = "waiting_support_ticket"
        txt = "💬 Send your inquiry or feedback, and administration will review it immediately:" if lang == "en" else "💬 اكتبي رسالتكِ أو استفساركِ بالتفصيل وسيصل مباشرة للإدارة للرد عليكِ:"
        await query.message.reply_text(txt)

async def pomo_timer(chat_id, context, lang="ar"):
    await asyncio.sleep(25 * 60)
    try:
        txt = "🔔 **25-minute focus session finished!** Take a 5-minute break to recharge ✨" if lang == "en" else "🔔 **انتهت جلسة الـ 25 دقيقة!** أحسنتِ، خذي استراحة 5 دقائق لتجديد النشاط ✨"
        await context.bot.send_message(chat_id=chat_id, text=txt, parse_mode="Markdown")
    except Exception:
        pass

# ==================================================
# لوحة القيادة الإدارية الشاملة والمطلقة (/admin)
# ==================================================

def admin_home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات المنصة الحية", callback_data="adm:stats")],
        [InlineKeyboardButton("📂 إدارة أقسام المكتبة", callback_data="adm:cats"), InlineKeyboardButton("➕ إضافة مادة/كتاب/PDF", callback_data="adm:add_book")],
        [InlineKeyboardButton("🎨 خدمات التصميم والنصوص", callback_data="adm:designs"), InlineKeyboardButton("📢 إذاعة عامة للجميع", callback_data="adm:broadcast")],
        [InlineKeyboardButton("⚙️ إعدادات الترحيب والاشتراك والصيانة", callback_data="adm:settings")],
        [InlineKeyboardButton("👀 العودة كـ مستخدم عادي", callback_data="nav:home")]
    ])

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("👑 **أهلاً بكِ في لوحة التحكم الإدارية المطلقة لـ Dua Space:**\nلديكِ الصلاحية الكاملة لتعديل كل شيء دون المساس بالأكواد:", reply_markup=admin_home_keyboard(), parse_mode="Markdown")

@admin_only
async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm:home":
        context.user_data.pop("adm_state", None)
        await query.edit_message_text("👑 **لوحة التحكم الإدارية الشاملة:**", reply_markup=admin_home_keyboard(), parse_mode="Markdown")

    elif data == "adm:stats":
        with db_connect() as db:
            u_cnt = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            b_cnt = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
            c_cnt = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            t_cnt = db.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
        text = (
            "📊 **إحصائيات Dua Space المباشرة:**\n\n"
            f"👤 المشتركين المسجلين: `{u_cnt}`\n"
            f"📚 المواد والكتب والمراجع: `{b_cnt}`\n"
            f"📂 عدد الأقسام النشطة: `{c_cnt}`\n"
            f"💬 التذاكر المفتوحة قيد الانتظار: `{t_cnt}`"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")]]), parse_mode="Markdown")

    # --- إدارة الأقسام ---
    elif data == "adm:cats":
        with db_connect() as db:
            cats = db.execute("SELECT * FROM categories ORDER BY position, category_id").fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ حذف: {c['name_ar']}", callback_data=f"adm:delcat:{c['category_id']}")] for c in cats]
        kb.append([InlineKeyboardButton("➕ إنشاء قسم جديد تماماً", callback_data="adm:new_cat")])
        kb.append([InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")])
        await query.edit_message_text("📂 **إدارة أقسام المكتبة:**\nاضغطي على أي قسم لحذفه بالكامل ومسح كتبه، أو اضغطي لإنشاء قسم جديد:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("adm:delcat:"):
        cid = int(data.split(":")[2])
        with db_connect() as db:
            db.execute("DELETE FROM categories WHERE category_id = ?", (cid,))
        await query.answer("تم حذف القسم وكافة مواده بنجاح.")
        await admin_actions(update, context)

    elif data == "adm:new_cat":
        context.user_data["adm_state"] = "waiting_new_cat_name_ar"
        await query.message.reply_text("➕ أرسلي اسم القسم الجديد بالعربي:")

    # --- إضافة مادة / PDF / فيديو للمكتبة ---
    elif data == "adm:add_book":
        with db_connect() as db:
            cats = db.execute("SELECT category_id, name_ar FROM categories").fetchall()
        kb = [[InlineKeyboardButton(c["name_ar"], callback_data=f"adm:selcat:{c['category_id']}")] for c in cats]
        kb.append([InlineKeyboardButton("↩️ إلغاء", callback_data="adm:home")])
        await query.edit_message_text("اختاري القسم الذي تريدين إرفاق المادة أو الكتاب إليه:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("adm:selcat:"):
        cid = int(data.split(":")[2])
        context.user_data["adm_target_cid"] = cid
        context.user_data["adm_state"] = "waiting_book_title_ar"
        await query.message.reply_text("📖 أرسلي عنوان الكتاب أو المادة بالعربي:")

    # --- إدارة خدمات التصميم والنصوص ---
    elif data == "adm:designs":
        with db_connect() as db:
            ds = db.execute("SELECT * FROM designs").fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ حذف: {d['title_ar']}", callback_data=f"adm:deldes:{d['design_id']}")] for d in ds]
        kb.append([InlineKeyboardButton("➕ إضافة خدمة تصميم جديدة", callback_data="adm:new_design")])
        kb.append([InlineKeyboardButton("✏️ تعديل النص التمهيدي لقسم التصميم", callback_data="adm:edit_des_intro")])
        kb.append([InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")])
        await query.edit_message_text("🎨 **إدارة خدمات التصميم (بدون أسعار محددة):**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("adm:deldes:"):
        did = int(data.split(":")[2])
        with db_connect() as db:
            db.execute("DELETE FROM designs WHERE design_id = ?", (did,))
        await query.answer("تم حذف الخدمة.")
        await admin_actions(update, context)

    elif data == "adm:new_design":
        context.user_data["adm_state"] = "waiting_design_title_ar"
        await query.message.reply_text("أرسلي اسم خدمة التصميم الجديدة بالعربي:")

    elif data == "adm:edit_des_intro":
        context.user_data["adm_state"] = "waiting_design_intro_text"
        await query.message.reply_text("أرسلي النص التمهيدي الجديد لقسم التصميم:")

    # --- الإذاعة ---
    elif data == "adm:broadcast":
        context.user_data["adm_state"] = "waiting_broadcast"
        await query.message.reply_text("📢 أرسلي الرسالة التي تريدين إذاعتها لجميع مستخدمي المنصة الآن:")

    # --- الإعدادات الشاملة ---
    elif data == "adm:settings":
        sub = get_setting("force_subscription", "1")
        maint = get_setting("maintenance", "0")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔐 الاشتراك الإجباري: {'مفعّل ✅' if sub == '1' else 'معطّل ❌'}", callback_data="adm:toggle_sub")],
            [InlineKeyboardButton(f"🛠️ وضع الصيانة: {'مفعّل ✅' if maint == '1' else 'معطّل ❌'}", callback_data="adm:toggle_maint")],
            [InlineKeyboardButton("✏️ تعديل رسالة الترحيب بالعربي", callback_data="adm:set_welcome_ar")],
            [InlineKeyboardButton("✏️ تعديل رسالة الترحيب بالإنجليزية", callback_data="adm:set_welcome_en")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")]
        ])
        await query.edit_message_text("⚙️ **إعدادات المنصة والتحكم بالنظام:**", reply_markup=kb, parse_mode="Markdown")

    elif data == "adm:toggle_sub":
        cur = get_setting("force_subscription", "1")
        set_setting("force_subscription", "0" if cur == "1" else "1")
        await query.answer("تم تحديث حالة الاشتراك الإجباري.")
        await admin_actions(update, context)

    elif data == "adm:toggle_maint":
        cur = get_setting("maintenance", "0")
        set_setting("maintenance", "0" if cur == "1" else "1")
        await query.answer("تم تحديث وضع الصيانة.")
        await admin_actions(update, context)

    elif data == "adm:set_welcome_ar":
        context.user_data["adm_state"] = "waiting_welcome_text_ar"
        await query.message.reply_text("أرسلي رسالة الترحيب الجديدة بالعربي:")

    elif data == "adm:set_welcome_en":
        context.user_data["adm_state"] = "waiting_welcome_text_en"
        await query.message.reply_text("Send the new English welcome message:")

# ==================================================
# معالج الرسائل، الملفات، والصور
# ==================================================

async def handle_incoming_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or update.effective_chat.type != ChatType.PRIVATE:
        return

    text = (msg.text or msg.caption or "").strip()
    u_state = context.user_data.get("state")
    a_state = context.user_data.get("adm_state")

    # استلام طلب تصميم من مستخدم
    if u_state == "waiting_design_order":
        context.user_data.pop("state", None)
        await msg.reply_text("✅ استلمنا طلبكِ بنجاح وسنتواصل معكِ فوراً لمناقشة التفاصيل والاتفاق!")
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎨 **طلب تصميم جديد:**\nمن: {user.full_name} (`{user.id}`)\nالطلب بالتفصيل:\n{text}", parse_mode="Markdown")
        return

    # استلام تذكرة دعم
    if u_state == "waiting_support_ticket":
        context.user_data.pop("state", None)
        with db_connect() as db:
            cur = db.execute("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)", (user.id, text, now_text()))
            tid = cur.lastrowid
        await msg.reply_text(f"✅ تم فتح التذكرة رقم `#{tid}` وسنرد عليكِ قريباً عبر البوت.", parse_mode="Markdown")
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"💬 **تذكرة دعم جديدة (#{tid}):**\nمن: {user.full_name} (`{user.id}`)\nالرسالة:\n{text}\n\nللرد: `/reply {tid} نص الرد`", parse_mode="Markdown")
        return

    # إجراءات الأدمن المباشرة
    if is_owner(user.id) and a_state:
        if a_state == "waiting_new_cat_name_ar":
            context.user_data["temp_cat_ar"] = text
            context.user_data["adm_state"] = "waiting_new_cat_name_en"
            await msg.reply_text("أرسلي اسم القسم بالإنجليزية:")
            return

        elif a_state == "waiting_new_cat_name_en":
            cat_ar = context.user_data.pop("temp_cat_ar")
            cat_en = text
            with db_connect() as db:
                db.execute("INSERT INTO categories (name_ar, name_en, description_ar, description_en) VALUES (?, ?, 'قسم جديد', 'New Section')", (cat_ar, cat_en))
            context.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ تم إنشاء القسم: **{cat_ar}** بنجاح ومتاح للجميع الآن!", parse_mode="Markdown")
            return

        elif a_state == "waiting_welcome_text_ar":
            set_setting("welcome_ar", text)
            context.user_data.pop("adm_state", None)
            await msg.reply_text("✅ تم تحديث رسالة الترحيب بالعربية بنجاح!")
            return

        elif a_state == "waiting_welcome_text_en":
            set_setting("welcome_en", text)
            context.user_data.pop("adm_state", None)
            await msg.reply_text("✅ English welcome message updated successfully!")
            return

        elif a_state == "waiting_design_intro_text":
            set_setting("design_intro_ar", text)
            context.user_data.pop("adm_state", None)
            await msg.reply_text("✅ تم تحديث النص التمهيدي لقسم التصميم بنجاح!")
            return

        elif a_state == "waiting_broadcast":
            context.user_data.pop("adm_state", None)
            with db_connect() as db:
                users = db.execute("SELECT user_id FROM users").fetchall()
            sent = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u["user_id"], text=text)
                    sent += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    pass
            await msg.reply_text(f"📢 اكتملت الإذاعة بنجاح! تم الإرسال إلى {sent} مستخدم.")
            return

        # مراحل إضافة مادة أو ملف للمكتبة
        elif a_state == "waiting_book_title_ar":
            context.user_data["temp_b_title_ar"] = text
            context.user_data["adm_state"] = "waiting_book_desc_ar"
            await msg.reply_text("أرسلي وصفاً مختصراً للمادة (أو اكتبي: لا يوجد):")
            return

        elif a_state == "waiting_book_desc_ar":
            context.user_data["temp_b_desc_ar"] = "" if text == "لا يوجد" else text
            context.user_data["adm_state"] = "waiting_book_file"
            await msg.reply_text("📥 الآن أرسلي **ملف الـ PDF**، أو **الفيديو**، أو **الصورة**، أو **رابط المصدر المباشر**:")
            return

        elif a_state == "waiting_book_file":
            cid = context.user_data.get("adm_target_cid", 1)
            t_ar = context.user_data.pop("temp_b_title_ar", "مادة معرفية")
            d_ar = context.user_data.pop("temp_b_desc_ar", "")
            context.user_data.pop("adm_state", None)

            fid, m_type, b_url = "", "text", ""
            if msg.document:
                fid, m_type = msg.document.file_id, "document"
            elif msg.video:
                fid, m_type = msg.video.file_id, "video"
            elif msg.photo:
                fid, m_type = msg.photo[-1].file_id, "photo"
            elif text.startswith("http"):
                b_url = text

            with db_connect() as db:
                db.execute("INSERT INTO books (category_id, title_ar, title_en, description_ar, description_en, url, file_id, media_type, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (cid, t_ar, t_ar, d_ar, d_ar, b_url, fid, m_type, now_text()))
            await msg.reply_text(f"✅ تمت إضافة **{t_ar}** إلى القسم المحدد بنجاح ومتاح للتحميل والتصفح الآن!", parse_mode="Markdown")
            return

        # إضافة خدمة تصميم جديدة
        elif a_state == "waiting_design_title_ar":
            context.user_data["temp_des_ar"] = text
            context.user_data["adm_state"] = "waiting_design_desc_ar"
            await msg.reply_text("أرسلي وصفاً تفصيلياً لخدمة التصميم:")
            return

        elif a_state == "waiting_design_desc_ar":
            t_ar = context.user_data.pop("temp_des_ar")
            d_ar = text
            with db_connect() as db:
                db.execute("INSERT INTO designs (title_ar, title_en, description_ar, description_en) VALUES (?, ?, ?, ?)",
                           (t_ar, t_ar, d_ar, d_ar))
            context.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ تمت إضافة خدمة التصميم: **{t_ar}** بنجاح!", parse_mode="Markdown")
            return

# ==================================================
# أوامر الإشراف في المجموعات (مع كشف المشرف المتخفي)
# ==================================================

async def is_group_admin(chat, user, bot):
    if user.id in [chat.id, 1087968824, 777000] or is_owner(user.id):
        return True
    try:
        m = await chat.get_member(user.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE or not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if msg.reply_to_message:
        try:
            await msg.reply_to_message.delete()
            await msg.delete()
        except Exception:
            pass

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE or not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if msg.reply_to_message:
        t = msg.reply_to_message.from_user
        try:
            await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=t.id)
            await msg.reply_text(f"🚫 تم حظر {t.full_name}.")
        except Exception as e:
            await msg.reply_text(f"تعذر الحظر: {e}")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE or not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if msg.reply_to_message:
        t = msg.reply_to_message.from_user
        try:
            await context.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=t.id, only_if_banned=True)
            await msg.reply_text(f"✅ تم فك حظر {t.full_name}.")
        except Exception as e:
            await msg.reply_text(f"تعذر فك الحظر: {e}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE or not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if msg.reply_to_message:
        t = msg.reply_to_message.from_user
        try:
            await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=t.id, permissions=ChatPermissions(can_send_messages=False))
            await msg.reply_text(f"🔇 تم كتم {t.full_name}.")
        except Exception as e:
            await msg.reply_text(f"تعذر الكتم: {e}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE or not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if msg.reply_to_message:
        t = msg.reply_to_message.from_user
        try:
            p = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True)
            await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=t.id, permissions=p)
            await msg.reply_text(f"🔊 تم فك كتم {t.full_name}.")
        except Exception as e:
            await msg.reply_text(f"تعذر فك الكتم: {e}")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE or not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if msg.reply_to_message:
        t = msg.reply_to_message.from_user
        with db_connect() as db:
            db.execute("INSERT INTO warnings (chat_id, user_id, created_at) VALUES (?, ?, ?)", (update.effective_chat.id, t.id, now_text()))
            cnt = db.execute("SELECT COUNT(*) FROM warnings WHERE chat_id = ? AND user_id = ?", (update.effective_chat.id, t.id)).fetchone()[0]

        if cnt >= 3:
            try:
                await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=t.id)
                await msg.reply_text(f"🚫 تم حظر {t.full_name} لتجاوز 3 تحذيرات.")
            except Exception:
                pass
        else:
            await msg.reply_text(f"⚠️ تحذير ({cnt}/3) للعضو {t.full_name}.")

@admin_only
async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.effective_message.reply_text("الاستخدام: `/reply رقم_التذكرة نص الرد`", parse_mode="Markdown")
        return
    tid = context.args[0]
    txt = " ".join(context.args[1:])
    with db_connect() as db:
        row = db.execute("SELECT user_id FROM tickets WHERE ticket_id = ?", (tid,)).fetchone()
        if row:
            db.execute("UPDATE tickets SET status = 'closed' WHERE ticket_id = ?", (tid,))
    if not row:
        await update.effective_message.reply_text("التذكرة غير موجودة.")
        return
    try:
        await context.bot.send_message(chat_id=row["user_id"], text=f"💬 **رد إدارة Dua Space على تذكرتكِ:**\n\n{txt}", parse_mode="Markdown")
        await update.effective_message.reply_text("✅ تم إرسال الرد وإغلاق التذكرة.")
    except Exception as e:
        await update.effective_message.reply_text(f"تعذر الإرسال: {e}")

# ==================================================
# خادم الويب المدمج لـ Render ونقطة الانطلاق
# ==================================================

async def handle_health(request):
    return web.Response(text="Dua Space Engine: 100% Operational", status=200)

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN مفقود في متغيرات البيئة!")

    init_database()

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
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("reply", cmd_reply))

    application.add_handler(CommandHandler("del", cmd_del))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("mute", cmd_mute))
    application.add_handler(CommandHandler("unmute", cmd_unmute))
    application.add_handler(CommandHandler("warn", cmd_warn))

    application.add_handler(CallbackQueryHandler(handle_navigation, pattern=r"^(nav:|lib:|order:|tasbeeh:|q:|setlang:)"))
    application.add_handler(CallbackQueryHandler(admin_actions, pattern=r"^adm:"))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_incoming_messages))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Dua Space Ultimate Engine started successfully.")
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
