# -*- coding: utf-8 -*-
# Dua Space Bot - Stable, Clean & Fully Managed Edition
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

# تثبيت معرّف الإدارة لضمان الصلاحيات
HARDCODED_ADMIN = 8669779200
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

try:
    ENV_ADMIN = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ENV_ADMIN = 0

ADMIN_ID = ENV_ADMIN if ENV_ADMIN != 0 else HARDCODED_ADMIN
CHANNEL_ID = os.getenv("CHANNEL_ID", "@DuaSpace1").strip()
CHANNEL_URL = "https://t.me/DuaSpace1"
DATABASE_PATH = os.getenv("DATABASE_PATH", "dua_space_v2.db")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("DuaSpace")

# ==========================================
# قاعدة البيانات والتهيئة التلقائية للأقسام
# ==========================================

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
            lang TEXT DEFAULT 'ar',
            joined_at TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            position INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            url TEXT DEFAULT '',
            file_id TEXT DEFAULT '',
            media_type TEXT DEFAULT 'text',
            added_at TEXT NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS designs (
            design_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS adhkar (
            dhikr_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            text TEXT NOT NULL,
            reward TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS quiz (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            opt1 TEXT NOT NULL,
            opt2 TEXT NOT NULL,
            opt3 TEXT NOT NULL,
            opt4 TEXT NOT NULL,
            answer INTEGER NOT NULL,
            explanation TEXT NOT NULL
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
            "welcome_en": "Welcome to Dua Space 🌙\n\nYour digital space for knowledge, books, languages, and custom design services.",
            "design_intro": "🎨 **خدمات التصميم الرقمي من Dua Space:**\nنقدم تصاميم إبداعية مخصصة باحترافية عالية. تحديد المواصفات والأسعار يتم بالاتفاق المباشر وفق متطلباتكِ.",
        }
        for k, v in defaults.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # زرع أقسام المكتبة المعرفية
        default_cats = [
            ("إسلاميات", "المصاحف، التفسير، الحديث الشريف، والفقه الميسر", 1),
            ("الطب والعلوم الصحية", "علم الأحياء، وظائف الأعضاء، والمراجع الطبية العالمية", 2),
            ("تعلّم اللغات (6 لغات)", "العربية، الإنجليزية، التركية، الكورية، اليابانية، والصينية", 3),
            ("الهندسة والتقنية", "البرمجة، هياكل البيانات، ومصادر علوم الحاسوب المفتوحة", 4),
            ("الأدب والروايات وتطوير الذات", "أمهات الكتب الأدبية، الفلسفة، وبناء العادات", 5),
        ]
        for cname, cdesc, pos in default_cats:
            row = db.execute("SELECT category_id FROM categories WHERE name = ?", (cname,)).fetchone()
            if not row:
                db.execute("INSERT INTO categories (name, description, position) VALUES (?, ?, ?)", (cname, cdesc, pos))

        # زرع مراجع مفتوحة ومباشرة لكل قسم
        books_seed = [
            ("إسلاميات", "المصحف الشريف وتفاسيره المعتمدة", "مجمع الملك فهد لطباعة المصحف الشريف الرقمي", "https://qurancomplex.gov.sa/"),
            ("إسلاميات", "جامع كتب الحديث (صحيح البخاري ومسلم)", "محرك البحث المتخصص في متون الحديث والتخريج", "https://sunnah.com/"),
            ("الطب والعلوم الصحية", "المكتبة الوطنية الأمريكية للطب (PubMed)", "أكبر قاعدة مراجع وأبحاث طبية مجانية في العالم", "https://pubmed.ncbi.nlm.nih.gov/"),
            ("الطب والعلوم الصحية", "كتاب تشريح ووظائف الأعضاء (OpenStax)", "كتاب علمي منهجي مفتوح المصدر ومحكّم", "https://openstax.org/details/books/anatomy-and-physiology-2e"),
            ("تعلّم اللغات (6 لغات)", "اللغة العربية: المعاجم ولسان العرب (الباحث)", "معجم عربي متكامل للبحث في المعاجم وقواعد النحو", "https://baheth.net/"),
            ("تعلّم اللغات (6 لغات)", "English: Oxford Learner's Grammar Portal", "دليل أوكسفورد الشامل لقواعد الإنجليزية وبناء المفردات", "https://www.oxfordlearnersdictionaries.com/"),
            ("تعلّم اللغات (6 لغات)", "Türkçe: Yunus Emre Enstitüsü Türkçe Öğrenim", "المنهج التركي الرسمي لتعلم اللغة التركية من الصفر", "https://turkce.yee.org.tr/"),
            ("تعلّم اللغات (6 لغات)", "한국어: المعهد الوطني للغة الكورية (K-Learners)", "المنهج الأساسي الرسمي لتعلم الهانغول الكوري", "https://www.korean.go.kr/"),
            ("تعلّم اللغات (6 لغات)", "日本語: Japan Foundation Learning Resources", "بوابة مؤسسة اليابان الرسمية لتعلم الهيراغانا والكانجي", "https://www.jpf.go.jp/"),
            ("تعلّم اللغات (6 لغات)", "中文: Chinese Grammar Wiki & Hanzi Guide", "المرجع الشامل لقواعد الماندرين وكتابة المقاطع الصينية", "https://resources.allsetlearning.com/chinese/grammar/"),
            ("الهندسة والتقنية", "بايثون الرسمية: دليل المبتدئين وهياكل البيانات", "التوثيق الرسمي الكامل للغة بايثون والمكتبات القياسية", "https://docs.python.org/3/tutorial/"),
            ("الهندسة والتقنية", "MIT OpenCourseWare: علوم الحاسوب والبرمجة", "المناهج والمحاضرات المفتوحة من معهد ماساتشوستس للتقنية", "https://ocw.mit.edu/courses/electrical-engineering-and-computer-science/"),
            ("الأدب والروايات وتطوير الذات", "مكتبة غوتنبرغ العالمية (Project Gutenberg)", "أكثر من 70 ألف كتاب ورواية كلاسيكية مجانية وقانونية", "https://www.gutenberg.org/"),
            ("الأدب والروايات وتطوير الذات", "مؤسسة هنداوي: كتب الأدب وتطوير الشخصية", "مكتبة إلكترونية للروايات العالمية وكتب الفكر المترجمة", "https://www.hindawi.org/books/"),
        ]
        for cname, title, desc, url in books_seed:
            row = db.execute("SELECT category_id FROM categories WHERE name = ?", (cname,)).fetchone()
            if row:
                cid = row["category_id"]
                exists = db.execute("SELECT 1 FROM books WHERE title = ?", (title,)).fetchone()
                if not exists:
                    db.execute("INSERT INTO books (category_id, title, description, url, added_at) VALUES (?, ?, ?, ?, ?)",
                               (cid, title, desc, url, now_text()))

        # زرع خدمات التصميم (بدون أي أسعار مفروضة)
        designs_seed = [
            ("تصميم الهويات البصرية والشعارات الاحترافية", "شعار مخصص، اختيار الألوان والخطوط، وكتيب الهوية الكامل للعلامة."),
            ("تصاميم السوشيال ميديا والإعلانات", "بوستات وقوالب مخصصة لانستغرام وتيليجرام بأعلى جودة وجاذبية."),
            ("تصميم أغلفة الكتب والروايات", "تصميم متكامل للغلافين الأمامي والخلفي معدّ للطباعة والنشر الإلكتروني."),
            ("تصميم العروض التقديمية (PowerPoint & PDF)", "شرائح تفاعلية وأنيقة للمحاضرات، المشاريع الدراسية، وحقائب الأعمال."),
            ("تصميم الكروت والمطبوعات التجارية", "بطاقات شخصية، بروشورات، فلايرات، ولافتات إعلانية احترافية."),
        ]
        for t, d in designs_seed:
            exists = db.execute("SELECT 1 FROM designs WHERE title = ?", (t,)).fetchone()
            if not exists:
                db.execute("INSERT INTO designs (title, description) VALUES (?, ?)", (t, d))

        # أذكار
        adhkar_seed = [
            ("أذكار", "أَصْبَحْنَا وَأَصْبَحَ المُلْكُ لِلَّهِ، وَالحَمْدُ لِلَّهِ لا إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لا شَرِيكَ لَهُ.", "حفظ ونماء وطمأنينة اليوم وبركته"),
            ("أذكار", "اللَّهُمَّ لا سَهْلَ إِلاَّ ما جَعَلْتَهُ سَهْلاً، وأَنْتَ تَجْعَلُ الحَزْنَ إِذَا شِئْتَ سَهْلاً.", "تيسير المذاكرة والحفظ وتسهيل كل أمر عسير"),
            ("أذكار", "أَسْتَغْفِرُ اللَّهَ العَظِيمَ الَّذِي لا إِلَهَ إِلاَّ هُوَ الحَيُّ القَيُّومُ وَأَتُوبُ إِلَيْهِ.", "مغفرة الذنوب وانشراح الصدر والسكينة"),
            ("أذكار", "لا حَوْلَ وَلا قُوَّةَ إِلاَّ بِاللَّهِ العَلِيِّ العَظِيمِ.", "كنز من كنوز الجنة ودفع الهموم"),
        ]
        for c, t, r in adhkar_seed:
            exists = db.execute("SELECT 1 FROM adhkar WHERE text = ?", (t,)).fetchone()
            if not exists:
                db.execute("INSERT INTO adhkar (category, text, reward) VALUES (?, ?, ?)", (c, t, r))

        # أسئلة وتحديات
        quizzes = [
            ("ما هو العضو الذي يضخ الدم لجميع أنحاء الجسم؟", "الرئة", "القلب", "الكبد", "الكلى", 2, "القلب هو المضخة المركزية لجهاز الدوران."),
            ("كم عدد أركان الإسلام الأساسية؟", "4", "5", "6", "7", 2, "بني الإسلام على خمس دعائم أساسية."),
            ("ما هي الوحدة الأساسية لبناء الكائنات الحية؟", "الخلية", "الذرة", "النسيج", "العضو", 1, "الخلية هي أصغر وحدة حية بنائية ووظيفية."),
            ("ما هو أكبر كواكب مجموعتنا الشمسية حجماً؟", "الأرض", "زحل", "المشتري", "المريخ", 3, "المشتري هو الأكبر حجماً بين كافة كواكب المجموعة."),
        ]
        for q, o1, o2, o3, o4, ans, exp in quizzes:
            exists = db.execute("SELECT 1 FROM quiz WHERE question = ?", (q,)).fetchone()
            if not exists:
                db.execute("INSERT INTO quiz (question, opt1, opt2, opt3, opt4, answer, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (q, o1, o2, o3, o4, ans, exp))

def get_setting(key, default=""):
    with db_connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    with db_connect() as db:
        db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))

def get_lang(uid):
    with db_connect() as db:
        row = db.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    return row["lang"] if row and row["lang"] else "ar"

def set_lang(uid, lang):
    with db_connect() as db:
        db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, uid))

# ==========================================
# الصلاحيات والتسجيل
# ==========================================

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
                await update.effective_message.reply_text("⚠️ هذا الأمر مخصص لمالكة المنصة فقط.")
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

# ==========================================
# الواجهة الرئيسية للمستخدم
# ==========================================

def main_menu_keyboard(lang="ar"):
    if lang == "en":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 Dua Space Library", callback_data="nav:library"), InlineKeyboardButton("🎨 Design Services", callback_data="nav:design")],
            [InlineKeyboardButton("📿 Adhkar & Tasbeeh", callback_data="nav:adhkar"), InlineKeyboardButton("🧠 Quiz & Trivia", callback_data="nav:quiz")],
            [InlineKeyboardButton("⏱️ Focus Timer (Pomodoro)", callback_data="nav:pomo"), InlineKeyboardButton("💬 Contact Support", callback_data="nav:support")],
            [InlineKeyboardButton("🌐 Language / اللغة", callback_data="nav:lang")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 مكتبة Dua Space المعرفية", callback_data="nav:library"), InlineKeyboardButton("🎨 خدمات التصميم", callback_data="nav:design")],
        [InlineKeyboardButton("📿 الأذكار والسبحة الرقمية", callback_data="nav:adhkar"), InlineKeyboardButton("🧠 التحديات والمسابقات", callback_data="nav:quiz")],
        [InlineKeyboardButton("⏱️ وقت التركيز (Pomodoro)", callback_data="nav:pomo"), InlineKeyboardButton("💬 تواصل مع الإدارة", callback_data="nav:support")],
        [InlineKeyboardButton("🌐 تغيير اللغة / Language", callback_data="nav:lang")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    register_user(user)
    lang = get_lang(user.id)

    if get_setting("maintenance", "0") == "1" and not is_owner(user.id):
        txt = "🛠️ البوت حالياً في وضع التحديث والصيانة لتحسين التجربة. نعود إليكم بعد قليل!" if lang == "ar" else "🛠️ Dua Space is currently under maintenance. We will be back shortly!"
        await msg.reply_text(txt)
        return

    if not await check_subscription(user.id, context):
        btn_txt = "📢 الانضمام للقناة الرسمية" if lang == "ar" else "📢 Join our Official Channel"
        check_txt = "✅ تم الاشتراك، تفعيل البوت" if lang == "ar" else "✅ Joined, Activate Bot"
        sub_prompt = "أهلاً بكِ في Dua Space 🌙\nيرجى الانضمام لقناتنا الرسمية للاستمتاع بكافة المزايا:" if lang == "ar" else "Welcome to Dua Space 🌙\nPlease join our official channel to use the bot:"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_txt, url=CHANNEL_URL)],
            [InlineKeyboardButton(check_txt, callback_data="nav:check_sub")]
        ])
        await msg.reply_text(sub_prompt, reply_markup=kb)
        return

    welcome = get_setting("welcome_en" if lang == "en" else "welcome_ar")
    await msg.reply_text(welcome, reply_markup=main_menu_keyboard(lang))

# ==========================================
# التصفح والتفاعل للمستخدمين
# ==========================================

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    lang = get_lang(uid)

    if data == "nav:check_sub":
        if await check_subscription(uid, context):
            welcome = get_setting("welcome_en" if lang == "en" else "welcome_ar")
            await query.edit_message_text(welcome, reply_markup=main_menu_keyboard(lang))
        else:
            await query.answer("لم يتم التحقق من اشتراكك في القناة بعد." if lang == "ar" else "Subscription verification failed. Please join the channel.", show_alert=True)

    elif data == "nav:home":
        context.user_data.pop("state", None)
        welcome = get_setting("welcome_en" if lang == "en" else "welcome_ar")
        await query.edit_message_text(welcome, reply_markup=main_menu_keyboard(lang))

    elif data == "nav:lang":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="setlang:ar"), InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en")],
            [InlineKeyboardButton("↩️ Back / رجوع", callback_data="nav:home")]
        ])
        await query.edit_message_text("🌐 **اختر لغة العرض / Choose your display language:**", reply_markup=kb, parse_mode="Markdown")

    elif data.startswith("setlang:"):
        new_lang = data.split(":")[1]
        set_lang(uid, new_lang)
        await query.answer("تم تغيير اللغة بنجاح!" if new_lang == "ar" else "Language changed successfully!")
        welcome = get_setting("welcome_en" if new_lang == "en" else "welcome_ar")
        await query.edit_message_text(welcome, reply_markup=main_menu_keyboard(new_lang))

    # --- تصفح المكتبة ---
    elif data == "nav:library":
        with db_connect() as db:
            cats = db.execute("SELECT category_id, name FROM categories ORDER BY position, category_id").fetchall()
        kb = [[InlineKeyboardButton(f"📂 {c['name']}", callback_data=f"lib:cat:{c['category_id']}")] for c in cats]
        kb.append([InlineKeyboardButton("🏠 Main Menu" if lang == "en" else "🏠 القائمة الرئيسية", callback_data="nav:home")])
        header = "📚 **مكتبة Dua Space المعرفية:**\nاختاري القسم المطلوب لتصفح المراجع والمصادر والكتب المفتوحة:" if lang == "ar" else "📚 **Dua Space Knowledge Library:**\nSelect a section to explore textbooks, digital sources, and open references:"
        await query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("lib:cat:"):
        cid = int(data.split(":")[2])
        with db_connect() as db:
            cat = db.execute("SELECT name, description FROM categories WHERE category_id = ?", (cid,)).fetchone()
            bks = db.execute("SELECT book_id, title FROM books WHERE category_id = ? ORDER BY book_id DESC", (cid,)).fetchall()

        kb = [[InlineKeyboardButton(f"📖 {b['title']}", callback_data=f"lib:view:{b['book_id']}")] for b in bks]
        kb.append([InlineKeyboardButton("⬅️ Back to Categories" if lang == "en" else "⬅️ رجوع للأقسام", callback_data="nav:library")])
        text = f"📂 **قسم: {cat['name']}**\n_{cat['description']}_\n\n"
        text += "المواد والمراجع المتوفرة:" if bks else "لا توجد مواد مضافة في هذا القسم حالياً."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("lib:view:"):
        bid = int(data.split(":")[2])
        with db_connect() as db:
            bk = db.execute("SELECT * FROM books WHERE book_id = ?", (bid,)).fetchone()

        kb = []
        if bk["url"]:
            btn_lbl = "🌐 فتح المرجع / المصدر المعتمد" if lang == "ar" else "🌐 Open Direct Source"
            kb.append([InlineKeyboardButton(btn_lbl, url=bk["url"])])
        kb.append([InlineKeyboardButton("⬅️ Back" if lang == "en" else "⬅️ رجوع للقسم", callback_data=f"lib:cat:{bk['category_id']}")])

        caption_txt = f"📖 **{bk['title']}**\n\n{bk['description'] or ''}"

        # إرسال الملف المباشر (PDF / فيديو / صورة) إن وجد
        if bk["file_id"]:
            try:
                if bk["media_type"] == "document":
                    await context.bot.send_document(chat_id=uid, document=bk["file_id"], caption=caption_txt, parse_mode="Markdown")
                elif bk["media_type"] == "video":
                    await context.bot.send_video(chat_id=uid, video=bk["file_id"], caption=caption_txt, parse_mode="Markdown")
                elif bk["media_type"] == "photo":
                    await context.bot.send_photo(chat_id=uid, photo=bk["file_id"], caption=caption_txt, parse_mode="Markdown")
            except Exception as e:
                logger.error("Failed sending file: %s", e)
        else:
            await query.edit_message_text(caption_txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    # --- خدمات التصميم بدون أسعار مفروضة ---
    elif data == "nav:design":
        with db_connect() as db:
            items = db.execute("SELECT * FROM designs").fetchall()
        text = get_setting("design_intro") + "\n\n"
        for itm in items:
            text += f"▫️ **{itm['title']}**\n_{itm['description']}_\n\n"

        text += "📩 لطلب أي خدمة وتحديد المواصفات المطلوبة، اضغطي على زر طلب تصميم للاتفاق المباشر:"
        kb = [
            [InlineKeyboardButton("✍️ طلب خدمة تصميم الآن", callback_data="order:design")],
            [InlineKeyboardButton("🏠 Main Menu" if lang == "en" else "🏠 القائمة الرئيسية", callback_data="nav:home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "order:design":
        context.user_data["state"] = "waiting_design_order"
        prompt = "🎨 أرسلي مواصفات التصميم الذي ترغبين به في رسالة واحدة وسنتواصل معكِ فوراً:" if lang == "ar" else "🎨 Please describe your design project, and we will get back to you directly:"
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

    # --- مؤقت بومودورو للتركيز ---
    elif data == "nav:pomo":
        txt = "⏱️ بدأ مؤقت التركيز لمدة 25 دقيقة! استثمري وقتكِ في الدراسة والإنجاز 🎯" if lang == "ar" else "⏱️ Focus session started for 25 minutes! Stay focused and productive 🎯"
        await query.message.reply_text(txt)
        asyncio.create_task(pomo_timer(query.message.chat_id, context, lang))

    # --- التحديات والمسابقات ---
    elif data == "nav:quiz":
        with db_connect() as db:
            q = db.execute("SELECT * FROM quiz ORDER BY RANDOM() LIMIT 1").fetchone()
        context.user_data["current_q"] = dict(q)
        kb = [
            [InlineKeyboardButton(q["opt1"], callback_data="q:ans:1")],
            [InlineKeyboardButton(q["opt2"], callback_data="q:ans:2")],
            [InlineKeyboardButton(q["opt3"], callback_data="q:ans:3")],
            [InlineKeyboardButton(q["opt4"], callback_data="q:ans:4")],
            [InlineKeyboardButton("🏠 Main Menu" if lang == "en" else "🏠 الرئيسية", callback_data="nav:home")]
        ]
        text = f"🧠 **سؤال التحدي والمعرفة:**\n\n{q['question']}\n\nاختاري الإجابة الصحيحة:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("q:ans:"):
        choice = int(data.split(":")[2])
        q = context.user_data.get("current_q")
        if not q:
            await query.edit_message_text("انتهت الجلسة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 سؤال جديد", callback_data="nav:quiz")]]))
            return
        correct = (choice == q["answer"])
        res = "🎉 إجابة صحيحة وممتازة!" if correct else "❌ إجابة غير صحيحة، حظاً أوفر في السؤال القادم."
        text = f"{res}\n\n💡 **الشرح والتوضيح:**\n{q['explanation']}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 سؤال آخر", callback_data="nav:quiz")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="nav:home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "nav:support":
        context.user_data["state"] = "waiting_support_ticket"
        await query.message.reply_text("💬 اكتبي رسالتكِ أو استفساركِ بالتفصيل وسيصل مباشرة إلى الإدارة للرد عليكِ:")

async def pomo_timer(chat_id, context, lang="ar"):
    await asyncio.sleep(25 * 60)
    try:
        txt = "🔔 **انتهت جلسة الـ 25 دقيقة!** أحسنتِ، خذي استراحة 5 دقائق لتجديد النشاط ✨" if lang == "ar" else "🔔 **25-minute focus session completed!** Take a 5-minute break ✨"
        await context.bot.send_message(chat_id=chat_id, text=txt, parse_mode="Markdown")
    except Exception:
        pass

# ==========================================
# لوحة القيادة الإدارية الشاملة (/admin)
# ==========================================

def admin_home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات المنصة الحية", callback_data="adm:stats")],
        [InlineKeyboardButton("📂 إدارة أقسام المكتبة", callback_data="adm:cats"), InlineKeyboardButton("➕ إضافة مادة / PDF / رابط", callback_data="adm:add_book")],
        [InlineKeyboardButton("🎨 خدمات التصميم والنصوص", callback_data="adm:designs"), InlineKeyboardButton("📢 إذاعة عامة للجميع", callback_data="adm:broadcast")],
        [InlineKeyboardButton("⚙️ إعدادات الترحيب والاشتراك والصيانة", callback_data="adm:settings")],
        [InlineKeyboardButton("👀 العودة لواجهة المستخدم", callback_data="nav:home")]
    ])

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("👑 **لوحة التحكم الشاملة لمالكة المنصة:**\nكل الصلاحيات متاحة لكِ هنا مباشرة وبسهولة:", reply_markup=admin_home_keyboard(), parse_mode="Markdown")

@admin_only
async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm:home":
        context.user_data.pop("adm_state", None)
        await query.edit_message_text("👑 **لوحة التحكم الشاملة لمالكة المنصة:**", reply_markup=admin_home_keyboard(), parse_mode="Markdown")

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
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ رجوع للوحة الإدارة", callback_data="adm:home")]]), parse_mode="Markdown")

    # --- إدارة الأقسام ---
    elif data == "adm:cats":
        with db_connect() as db:
            cats = db.execute("SELECT * FROM categories ORDER BY position, category_id").fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ حذف: {c['name']}", callback_data=f"adm:delcat:{c['category_id']}")] for c in cats]
        kb.append([InlineKeyboardButton("➕ إنشاء قسم جديد تماماً", callback_data="adm:new_cat")])
        kb.append([InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")])
        await query.edit_message_text("📂 **إدارة أقسام المكتبة:**\nاضغطي على أي قسم لحذفه بالكامل ومسح محتوياته، أو أضيفي قسماً جديداً:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("adm:delcat:"):
        cid = int(data.split(":")[2])
        with db_connect() as db:
            db.execute("DELETE FROM categories WHERE category_id = ?", (cid,))
        await query.answer("تم حذف القسم بنجاح.")
        await admin_actions(update, context)

    elif data == "adm:new_cat":
        context.user_data["adm_state"] = "waiting_new_cat_name"
        await query.message.reply_text("➕ أرسلي اسم القسم الجديد الآن:")

    # --- إضافة كتاب أو PDF أو فيديو ---
    elif data == "adm:add_book":
        with db_connect() as db:
            cats = db.execute("SELECT category_id, name FROM categories").fetchall()
        kb = [[InlineKeyboardButton(c["name"], callback_data=f"adm:selcat:{c['category_id']}")] for c in cats]
        kb.append([InlineKeyboardButton("↩️ إلغاء", callback_data="adm:home")])
        await query.edit_message_text("اختاري القسم الذي تريدين إضافة المادة إليه:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("adm:selcat:"):
        cid = int(data.split(":")[2])
        context.user_data["adm_target_cid"] = cid
        context.user_data["adm_state"] = "waiting_book_title"
        await query.message.reply_text("📖 أرسلي عنوان الكتاب أو المادة أو المحاضرة:")

    # --- إدارة خدمات التصميم والنصوص ---
    elif data == "adm:designs":
        with db_connect() as db:
            ds = db.execute("SELECT * FROM designs").fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ حذف: {d['title']}", callback_data=f"adm:deldes:{d['design_id']}")] for d in ds]
        kb.append([InlineKeyboardButton("➕ إضافة خدمة تصميم جديدة", callback_data="adm:new_design")])
        kb.append([InlineKeyboardButton("✏️ تعديل النص التمهيدي للقسم", callback_data="adm:edit_des_intro")])
        kb.append([InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")])
        await query.edit_message_text("🎨 **إدارة خدمات التصميم (بدون أسعار محددة):**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("adm:deldes:"):
        did = int(data.split(":")[2])
        with db_connect() as db:
            db.execute("DELETE FROM designs WHERE design_id = ?", (did,))
        await query.answer("تم حذف الخدمة.")
        await admin_actions(update, context)

    elif data == "adm:new_design":
        context.user_data["adm_state"] = "waiting_design_title"
        await query.message.reply_text("أرسلي اسم خدمة التصميم الجديدة:")

    elif data == "adm:edit_des_intro":
        context.user_data["adm_state"] = "waiting_design_intro_text"
        await query.message.reply_text("أرسلي النص التمهيدي الجديد لقسم التصميم:")

    # --- الإذاعة ---
    elif data == "adm:broadcast":
        context.user_data["adm_state"] = "waiting_broadcast"
        await query.message.reply_text("📢 أرسلي الرسالة التي تريدين إذاعتها لجميع مستخدمي المنصة الآن:")

    # --- الإعدادات الشاملة والنظام ---
    elif data == "adm:settings":
        sub = get_setting("force_subscription", "1")
        maint = get_setting("maintenance", "0")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔐 الاشتراك الإجباري: {'مفعّل ✅' if sub == '1' else 'معطّل ❌'}", callback_data="adm:toggle_sub")],
            [InlineKeyboardButton(f"🛠️ وضع الصيانة: {'مفعّل ✅' if maint == '1' else 'معطّل ❌'}", callback_data="adm:toggle_maint")],
            [InlineKeyboardButton("✏️ تعديل رسالة الترحيب بالعربي", callback_data="adm:set_welcome_ar")],
            [InlineKeyboardButton("✏️ تعديل رسالة الترحيب بالإنجليزي", callback_data="adm:set_welcome_en")],
            [InlineKeyboardButton("↩️ رجوع للوحة الإدارة", callback_data="adm:home")]
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

# ==========================================
# استلام الرسائل والملفات
# ==========================================

async def handle_incoming_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or update.effective_chat.type != ChatType.PRIVATE:
        return

    text = (msg.text or msg.caption or "").strip()
    u_state = context.user_data.get("state")
    a_state = context.user_data.get("adm_state")

    # استلام طلب تصميم من المستخدم
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

    # عمليات المالك والإدارة
    if is_owner(user.id) and a_state:
        if a_state == "waiting_new_cat_name":
            with db_connect() as db:
                db.execute("INSERT INTO categories (name, description) VALUES (?, 'قسم معرفي متجدد')", (text,))
            context.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ تم إنشاء القسم: **{text}** بنجاح ومتاح للجميع الآن!", parse_mode="Markdown")
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
            set_setting("design_intro", text)
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

        elif a_state == "waiting_book_title":
            context.user_data["temp_b_title"] = text
            context.user_data["adm_state"] = "waiting_book_desc"
            await msg.reply_text("أرسلي وصفاً مختصراً للمادة (أو اكتبي: لا يوجد):")
            return

        elif a_state == "waiting_book_desc":
            context.user_data["temp_b_desc"] = "" if text == "لا يوجد" else text
            context.user_data["adm_state"] = "waiting_book_file"
            await msg.reply_text("📥 الآن أرسلي **ملف PDF**، أو **فيديو**، أو **صورة**، أو **رابط مباشر**:")
            return

        elif a_state == "waiting_book_file":
            cid = context.user_data.get("adm_target_cid", 1)
            t = context.user_data.pop("temp_b_title", "مادة معرفية")
            d = context.user_data.pop("temp_b_desc", "")
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
                db.execute("INSERT INTO books (category_id, title, description, url, file_id, media_type, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (cid, t, d, b_url, fid, m_type, now_text()))
            await msg.reply_text(f"✅ تمت إضافة **{t}** بنجاح ومتاح للتحميل والتصفح داخل القسم الآن!", parse_mode="Markdown")
            return

        elif a_state == "waiting_design_title":
            context.user_data["temp_des_title"] = text
            context.user_data["adm_state"] = "waiting_design_desc"
            await msg.reply_text("أرسلي وصفاً تفصيلياً لخدمة التصميم:")
            return

        elif a_state == "waiting_design_desc":
            t = context.user_data.pop("temp_des_title")
            d = text
            with db_connect() as db:
                db.execute("INSERT INTO designs (title, description) VALUES (?, ?)", (t, d))
            context.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ تمت إضافة خدمة التصميم: **{t}** بنجاح!", parse_mode="Markdown")
            return

# ==========================================
# أوامر الإشراف في المجموعات
# ==========================================

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

# ==========================================
# تشغيل خادم الويب والتطبيق
# ==========================================

async def handle_health(request):
    return web.Response(text="Dua Space Engine: 100% Active", status=200)

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
        logger.info("Dua Space Engine is completely ready and running.")
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
