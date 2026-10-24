# -*- coding: utf-8 -*-
# Dua Space Bot - Complete Production Engine
# Python 3.11+ | PTB 21.10 | Render Free Compatible

import os
import json
import time
import sqlite3
import logging
import random
import asyncio
from datetime import datetime, timezone
from functools import wraps

from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ChatPermissions,
)
from telegram.constants import ChatMemberStatus, ChatType
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
# الإعدادات الأساسية
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

CHANNEL_ID = os.getenv("CHANNEL_ID", "@DuaSpace1").strip()
CHANNEL_URL = "https://t.me/DuaSpace1"
DATABASE_PATH = os.getenv("DATABASE_PATH", "dua_space.db")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("DuaSpace")

# ==================================================
# إدارة قاعدة البيانات والزرع التلقائي للبيانات
# ==================================================

def db_connect():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def now_text():
    return datetime.now(timezone.utc).isoformat()

def init_database():
    with db_connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
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
            price TEXT NOT NULL,
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
            "welcome_text": "أهلًا بكِ في Dua Space 🌙\n\nمساحتك المتكاملة للمعرفة، القراءة، التعلّم، وخدمات التصميم.",
        }
        for k, v in defaults.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # زرع أقسام المكتبة التأسيسية
        default_cats = [
            ("إسلاميات", "كتب الفقه والقرآن والأدعية والحديث الشريف"),
            ("الطب والعلوم الصحية", "مراجع علم الأحياء، الطب، والتغذية"),
            ("تعلّم اللغات", "قواعد، محادثات، ومصادر تعلم اللغات"),
            ("الهندسة والتقنية", "البرمجة، علوم الحاسوب، والتقنية الحديثة"),
            ("قصص وروايات", "روائع الأدب العالمي والعربي وتطوير الذات"),
        ]
        for idx, (cname, cdesc) in enumerate(default_cats):
            db.execute("INSERT OR IGNORE INTO categories (name, description, position) VALUES (?, ?, ?)", (cname, cdesc, idx))

        # زرع كتب ومراجع افتراضية
        books_seed = [
            ("إسلاميات", "الأذكار والتحصينات النبوية", "كتيب شامل لأذكار اليوم والليلة", "https://t.me/DuaSpace1"),
            ("إسلاميات", "رياض الصالحين", "مختصر جامع في الحديث الشريف", "https://t.me/DuaSpace1"),
            ("الطب والعلوم الصحية", "دليل وظائف الأعضاء المبسط", "شرح أساسيات الجهاز العصبي والدورة الدموية", "https://t.me/DuaSpace1"),
            ("تعلّم اللغات", "دليل المفردات الإنجليزية الأكثر استخداماً", "أهم 3000 كلمة في اللغة الإنجليزية للمبتدئين", "https://t.me/DuaSpace1"),
            ("الهندسة والتقنية", "مدخل إلى عالم البرمجة وبايثون", "أساسيات التفكير المنطقي وهياكل البيانات", "https://t.me/DuaSpace1"),
            ("قصص وروايات", "قواعد تطوير الشخصية والتركيز", "دليل بناء العادات الدراسية والإنجاز اليومي", "https://t.me/DuaSpace1"),
        ]
        for cat_name, title, desc, url in books_seed:
            row = db.execute("SELECT category_id FROM categories WHERE name = ?", (cat_name,)).fetchone()
            if row:
                cid = row["category_id"]
                exists = db.execute("SELECT 1 FROM books WHERE title = ?", (title,)).fetchone()
                if not exists:
                    db.execute("INSERT INTO books (category_id, title, description, url, added_at) VALUES (?, ?, ?, ?, ?)",
                               (cid, title, desc, url, now_text()))

        # زرع خدمات التصميم
        design_seed = [
            ("تصميم هوية بصرية كاملة", "35$", "شعار احترافي، ألوان، خطوط، وتطبيقات الهوية"),
            ("تصميم بوستات سوشيال ميديا (حزمة 5)", "15$", "تصاميم مخصصة لانستغرام وتيليجرام بأعلى جودة"),
            ("تصميم أغلفة كتب وروايات", "10$", "تصميم واجهة وخلفية للطباعة والنشر الإلكتروني"),
            ("تصميم عروض تقديمية (PowerPoint)", "12$", "تصميم شرائح احترافية وجذابة للمحاضرات والمشاريع"),
        ]
        for title, price, desc in design_seed:
            exists = db.execute("SELECT 1 FROM designs WHERE title = ?", (title,)).fetchone()
            if not exists:
                db.execute("INSERT INTO designs (title, price, description) VALUES (?, ?, ?)", (title, price, desc))

        # زرع باقة الأذكار
        adhkar_seed = [
            ("الصباح والمساء", "أَصْبَحْنَا وَأَصْبَحَ المُلْكُ لِلَّهِ، وَالحَمْدُ لِلَّهِ لا إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لا شَرِيكَ لَهُ.", "حفظ ونماء وطمأنينة اليوم"),
            ("الصباح والمساء", "اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ وَإِلَيْكَ النُّشُورُ.", "استشعار معية الله"),
            ("أدعية الاستذكار", "اللهم لا سهل إلا ما جعلته سهلاً وأنت تجعل الحزن إذا شئت سهلاً.", "لتسهيل الحفظ والدراسة"),
            ("الاستغفار", "أستغفر الله العظيم الذي لا إله إلا هو الحي القيوم وأتوب إليه.", "مغفرة الذنوب وزيادة الرزق"),
        ]
        for cat, txt, rew in adhkar_seed:
            exists = db.execute("SELECT 1 FROM adhkar WHERE text = ?", (txt,)).fetchone()
            if not exists:
                db.execute("INSERT INTO adhkar (category, text, reward) VALUES (?, ?, ?)", (cat, txt, rew))

        # زرع بنك الأسئلة
        quiz_seed = [
            ("كم عدد أركان الإسلام؟", "4", "5", "6", "7", 2, "أركان الإسلام خمسة بني عليها الدين."),
            ("ما هو العضو الذي يضخ الدم لجميع أنحاء الجسم؟", "الرئة", "القلب", "الكبد", "الكلى", 2, "القلب هو المضخة المركزية لجهاز الدوران."),
            ("ما هي الوحدة الأساسية لبناء الكائنات الحية؟", "الخلية", "الذرة", "النسيج", "العضو", 1, "الخلية هي أصغر وحدة حية بنائية ووظيفية."),
            ("ما هو أكبر كواكب مجموعتنا الشمسية حجماً؟", "الأرض", "زحل", "المشتري", "المريخ", 3, "المشتري هو الأكبر حجماً بين كل كواكب المجموعة."),
        ]
        for q, o1, o2, o3, o4, ans, exp in quiz_seed:
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

# ==================================================
# التحقق والمشرفين
# ==================================================

def is_owner(user_id):
    return ADMIN_ID != 0 and user_id == ADMIN_ID

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not is_owner(user.id):
            if update.callback_query:
                await update.callback_query.answer("هذه اللوحة خاصة بإدارة المنصة فقط.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text("عذراً، هذا الإجراء مخصص لمالك المنصة فقط.")
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
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return True

# ==================================================
# القوائم والواجهات التفاعلية
# ==================================================

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 مكتبة Dua Space", callback_data="nav:library"), InlineKeyboardButton("🎨 خدمات التصميم", callback_data="nav:design")],
        [InlineKeyboardButton("📿 الأذكار والسبحة", callback_data="nav:adhkar"), InlineKeyboardButton("🧠 التحديات والمسابقات", callback_data="nav:quiz")],
        [InlineKeyboardButton("⏱️ مؤقت التركيز (Pomodoro)", callback_data="nav:pomo"), InlineKeyboardButton("💬 تواصل مع الدعم", callback_data="nav:support")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    register_user(user)

    if get_setting("maintenance", "0") == "1" and not is_owner(user.id):
        await msg.reply_text("🛠️ البوت قيد الصيانة المؤقتة لتطوير المحتوى. نعود بعد قليل!")
        return

    if not await check_subscription(user.id, context):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 اشتركي في القناة أولاً", url=CHANNEL_URL)],
            [InlineKeyboardButton("✅ تم الاشتراك، تفعيل البوت", callback_data="nav:check_sub")]
        ])
        await msg.reply_text("أهلاً بكِ في منصة Dua Space 🌙\nيرجى الانضمام لقناتنا الرسمية للاستمتاع بجميع المزايا:", reply_markup=kb)
        return

    welcome = get_setting("welcome_text")
    await msg.reply_text(welcome, reply_markup=main_menu_keyboard())

# ==================================================
# تصفح الأقسام والمحتوى
# ==================================================

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:check_sub":
        if await check_subscription(query.from_user.id, context):
            await query.edit_message_text(get_setting("welcome_text"), reply_markup=main_menu_keyboard())
        else:
            await query.answer("لم يتم التحقق من اشتراكك في القناة بعد.", show_alert=True)

    elif data == "nav:home":
        context.user_data.pop("state", None)
        await query.edit_message_text(get_setting("welcome_text"), reply_markup=main_menu_keyboard())

    # --- قسم المكتبة ---
    elif data == "nav:library":
        with db_connect() as db:
            cats = db.execute("SELECT category_id, name FROM categories ORDER BY position, category_id").fetchall()
        kb = [[InlineKeyboardButton(f"📂 {c['name']}", callback_data=f"lib:cat:{c['category_id']}")] for c in cats]
        kb.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="nav:home")])
        await query.edit_message_text("📚 **أقسام مكتبة Dua Space المعرفية:**\nاختاري القسم لتصفح الكتب والمراجع والمحاضرات:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("lib:cat:"):
        cid = int(data.split(":")[2])
        with db_connect() as db:
            cat = db.execute("SELECT name, description FROM categories WHERE category_id = ?", (cid,)).fetchone()
            bks = db.execute("SELECT book_id, title FROM books WHERE category_id = ? ORDER BY book_id DESC", (cid,)).fetchall()

        kb = [[InlineKeyboardButton(f"📖 {b['title']}", callback_data=f"lib:view:{b['book_id']}")] for b in bks]
        kb.append([InlineKeyboardButton("⬅️ رجوع للأقسام", callback_data="nav:library")])
        text = f"📂 **قسم: {cat['name']}**\n_{cat['description']}_\n\n"
        text += "المواد المتوفرة في هذا القسم:" if bks else "لا توجد مواد مضافة في هذا القسم حالياً."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("lib:view:"):
        bid = int(data.split(":")[2])
        with db_connect() as db:
            bk = db.execute("SELECT * FROM books WHERE book_id = ?", (bid,)).fetchone()

        kb = []
        if bk["url"]:
            kb.append([InlineKeyboardButton("🔗 فتح الرابط أو المرجع", url=bk["url"])])
        kb.append([InlineKeyboardButton("⬅️ رجوع للقسم", callback_data=f"lib:cat:{bk['category_id']}")])

        msg_text = f"📖 **{bk['title']}**\n\n{bk['description'] or ''}"
        await query.edit_message_text(msg_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

        # إرسال الملف المرفق إن وجد
        if bk["file_id"]:
            cid = query.from_user.id
            try:
                if bk["media_type"] == "document":
                    await context.bot.send_document(chat_id=cid, document=bk["file_id"], caption=bk["title"])
                elif bk["media_type"] == "video":
                    await context.bot.send_video(chat_id=cid, video=bk["file_id"], caption=bk["title"])
                elif bk["media_type"] == "photo":
                    await context.bot.send_photo(chat_id=cid, photo=bk["file_id"], caption=bk["title"])
            except Exception as e:
                logger.error("Failed to send book media: %s", e)

    # --- قسم خدمات التصميم ---
    elif data == "nav:design":
        with db_connect() as db:
            items = db.execute("SELECT * FROM designs").fetchall()
        text = "🎨 **خدمات التصميم الرقمي من Dua Space:**\n\n"
        for itm in items:
            text += f"▫️ **{itm['title']}** — السعر: `{itm['price']}`\n_{itm['description']}_\n\n"
        text += "📩 لطلب أي تصميم مخصص، اضغطي على زر طلب تصميم للتواصل المباشر معنا:"
        kb = [
            [InlineKeyboardButton("✍️ طلب خدمة تصميم الآن", callback_data="order:design")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="nav:home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "order:design":
        context.user_data["state"] = "waiting_design_order"
        await query.message.reply_text("🎨 أرسلي تفاصيل التصميم المطلوب في رسالة واحدة وسنقوم بالرد عليكِ فوراً:")

    # --- قسم الأذكار والسبحة ---
    elif data == "nav:adhkar":
        with db_connect() as db:
            adh = db.execute("SELECT * FROM adhkar ORDER BY RANDOM() LIMIT 1").fetchone()
        count = context.user_data.get("tasbeeh_count", 0)
        text = (
            "📿 **واحة الذكر والتسبيح الإلكتروني**\n\n"
            f"🌿 *ذكر مختار:*\n« {adh['text']} »\n\n"
            f"💡 *الفضل:* {adh['reward']}\n\n"
            f"🔢 **عداد التسبيح الحالي:** `{count}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📿 سبّح (+1)", callback_data="tasbeeh:inc")],
            [InlineKeyboardButton("🔄 تصفير العداد", callback_data="tasbeeh:zero"), InlineKeyboardButton("🌿 ذكر آخر", callback_data="nav:adhkar")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="nav:home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "tasbeeh:inc":
        c = context.user_data.get("tasbeeh_count", 0) + 1
        context.user_data["tasbeeh_count"] = c
        await query.answer(f"سبحان الله وبحمده ({c})")
        # تحديث النص مع العداد
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
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="nav:home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "tasbeeh:zero":
        context.user_data["tasbeeh_count"] = 0
        await query.answer("تم تصفير العداد.")
        await handle_navigation(update, context)

    # --- مؤقت بومودورو ---
    elif data == "nav:pomo":
        await query.message.reply_text("⏱️ **بدأ مؤقت التركيز (25 دقيقة)!**\nاستثمري الوقت في الدراسة والإنجاز، وسأقوم بتنبيهكِ فور انتهاء الوقت 🎯")
        asyncio.create_task(pomo_timer(query.message.chat_id, context))

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
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="nav:home")]
        ]
        text = f"🧠 **تحدّي الذكاء والمعرفة:**\n\n{q['question']}\n\nاختاري الإجابة الصحيحة:"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("q:ans:"):
        choice = int(data.split(":")[2])
        q = context.user_data.get("current_q")
        if not q:
            await query.edit_message_text("انتهى وقت هذا التحدي.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 سؤال جديد", callback_data="nav:quiz")]]))
            return
        correct = (choice == q["answer"])
        res_header = "🎉 **إجابة صحيحة، ممتازة جداً!**" if correct else "❌ **إجابة خاطئة، حظاً أوفر في المرة القادمة.**"
        text = f"{res_header}\n\n💡 **الشرح والتوضيح:**\n{q['explanation']}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 سؤال آخر", callback_data="nav:quiz")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="nav:home")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # --- الدعم الفني ---
    elif data == "nav:support":
        context.user_data["state"] = "waiting_support_ticket"
        await query.message.reply_text("💬 اكتبي رسالتكِ أو استفساركِ بالتفصيل وسيتم إرسالها إلى الإدارة فوراً:")

async def pomo_timer(chat_id, context):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.send_message(chat_id=chat_id, text="🔔 **انتهت جلسة الـ 25 دقيقة!**\nعمل رائع، خذي استراحة 5 دقائق لتجديد النشاط ✨")
    except Exception:
        pass

# ==================================================
# لوحة القيادة الإدارية الشاملة (/admin)
# ==================================================

def admin_home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات المنصة الحية", callback_data="adm:stats")],
        [InlineKeyboardButton("📂 إدارة أقسام المكتبة", callback_data="adm:cats"), InlineKeyboardButton("➕ إضافة مادة للمكتبة", callback_data="adm:add_book")],
        [InlineKeyboardButton("🎨 خدمات التصميم والأسعار", callback_data="adm:designs")],
        [InlineKeyboardButton("📢 إذاعة رسالة لكل المشتركين", callback_data="adm:broadcast")],
        [InlineKeyboardButton("⚙️ إعدادات البوت والترحيب", callback_data="adm:settings")],
        [InlineKeyboardButton("👀 العودة لواجهة المستخدم", callback_data="nav:home")]
    ])

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🛠️ **لوحة التحكم الشاملة لمالك المنصة:**\nيمكنكِ التحكم في كافة الأقسام والمواد وإرسال الإذاعات من هنا مباشرة:", reply_markup=admin_home_keyboard(), parse_mode="Markdown")

@admin_only
async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm:home":
        context.user_data.pop("adm_state", None)
        await query.edit_message_text("🛠️ **لوحة التحكم الشاملة:**", reply_markup=admin_home_keyboard(), parse_mode="Markdown")

    elif data == "adm:stats":
        with db_connect() as db:
            u_cnt = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            b_cnt = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
            c_cnt = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            t_cnt = db.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
        text = (
            "📊 **إحصائيات Dua Space المباشرة:**\n\n"
            f"👤 عدد المستخدمين المسجلين: `{u_cnt}`\n"
            f"📚 إجمالي المواد والكتب: `{b_cnt}`\n"
            f"📂 عدد الأقسام النشطة: `{c_cnt}`\n"
            f"💬 التذاكر المفتوحة قيد الانتظار: `{t_cnt}`"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")]]), parse_mode="Markdown")

    elif data == "adm:cats":
        with db_connect() as db:
            cats = db.execute("SELECT * FROM categories ORDER BY position").fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ حذف: {c['name']}", callback_data=f"adm:delcat:{c['category_id']}")] for c in cats]
        kb.append([InlineKeyboardButton("➕ إنشاء قسم جديد", callback_data="adm:new_cat")])
        kb.append([InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")])
        await query.edit_message_text("📂 **إدارة الأقسام:**\nاضغطي على أي قسم لحذفه ومسح محتوياته، أو أضيفي قسماً جديداً:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("adm:delcat:"):
        cid = int(data.split(":")[2])
        with db_connect() as db:
            db.execute("DELETE FROM categories WHERE category_id = ?", (cid,))
        await query.answer("تم حذف القسم بنجاح.")
        await admin_actions(update, context)

    elif data == "adm:new_cat":
        context.user_data["adm_state"] = "waiting_new_cat_name"
        await query.message.reply_text("➕ أرسلي اسم القسم الجديد الآن:")

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
        await query.message.reply_text("📖 أرسلي عنوان الكتاب أو المرجع أو المحاضرة:")

    elif data == "adm:designs":
        with db_connect() as db:
            ds = db.execute("SELECT * FROM designs").fetchall()
        kb = [[InlineKeyboardButton(f"🗑️ حذف: {d['title']}", callback_data=f"adm:deldes:{d['design_id']}")] for d in ds]
        kb.append([InlineKeyboardButton("➕ إضافة خدمة تصميم جديدة", callback_data="adm:new_design")])
        kb.append([InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")])
        await query.edit_message_text("🎨 **خدمات التصميم الحالية:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("adm:deldes:"):
        did = int(data.split(":")[2])
        with db_connect() as db:
            db.execute("DELETE FROM designs WHERE design_id = ?", (did,))
        await query.answer("تم حذف الخدمة.")
        await admin_actions(update, context)

    elif data == "adm:new_design":
        context.user_data["adm_state"] = "waiting_design_title"
        await query.message.reply_text("أرسلي اسم خدمة التصميم الجديدة:")

    elif data == "adm:broadcast":
        context.user_data["adm_state"] = "waiting_broadcast"
        await query.message.reply_text("📢 أرسلي الرسالة التي تريدين إذاعتها لجميع مستخدمي البوت:")

    elif data == "adm:settings":
        sub = get_setting("force_subscription", "1")
        maint = get_setting("maintenance", "0")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔐 الاشتراك الإجباري: {'مفعّل' if sub == '1' else 'معطّل'}", callback_data="adm:toggle_sub")],
            [InlineKeyboardButton(f"🛠️ وضع الصيانة: {'مفعّل' if maint == '1' else 'معطّل'}", callback_data="adm:toggle_maint")],
            [InlineKeyboardButton("✏️ تعديل رسالة الترحيب", callback_data="adm:set_welcome")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="adm:home")]
        ])
        await query.edit_message_text("⚙️ **إعدادات المنصة:**", reply_markup=kb, parse_mode="Markdown")

    elif data == "adm:toggle_sub":
        cur = get_setting("force_subscription", "1")
        set_setting("force_subscription", "0" if cur == "1" else "1")
        await query.answer("تم تغيير حالة الاشتراك الإجباري.")
        await admin_actions(update, context)

    elif data == "adm:toggle_maint":
        cur = get_setting("maintenance", "0")
        set_setting("maintenance", "0" if cur == "1" else "1")
        await query.answer("تم تغيير وضع الصيانة.")
        await admin_actions(update, context)

    elif data == "adm:set_welcome":
        context.user_data["adm_state"] = "waiting_welcome_text"
        await query.message.reply_text("أرسلي رسالة الترحيب الجديدة الآن:")

# ==================================================
# معالج الرسائل النصية، الملفات، والوسائط
# ==================================================

async def handle_incoming_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return

    # معالجة الخاص فقط
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    text = (msg.text or msg.caption or "").strip()
    u_state = context.user_data.get("state")
    a_state = context.user_data.get("adm_state")

    # استلام طلب تصميم من مستخدم
    if u_state == "waiting_design_order":
        context.user_data.pop("state", None)
        await msg.reply_text("✅ استلمنا طلبكِ وسنقوم بمراجعته والرد عليكِ في أقرب وقت!")
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎨 **طلب تصميم جديد:**\nمن: {user.full_name} (`{user.id}`)\nالطلب:\n{text}", parse_mode="Markdown")
        return

    # استلام تذكرة دعم
    if u_state == "waiting_support_ticket":
        context.user_data.pop("state", None)
        with db_connect() as db:
            cur = db.execute("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)", (user.id, text, now_text()))
            tid = cur.lastrowid
        await msg.reply_text(f"✅ تم فتح تذكرتكِ رقم `#{tid}` وسنرد عليكِ قريباً عبر البوت.", parse_mode="Markdown")
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"💬 **تذكرة دعم جديدة (#{tid}):**\nمن: {user.full_name} (`{user.id}`)\nالرسالة:\n{text}\n\nللرد: `/reply {tid} نص الرد`", parse_mode="Markdown")
        return

    # وظائف المالك والإدارة
    if is_owner(user.id) and a_state:
        if a_state == "waiting_new_cat_name":
            with db_connect() as db:
                db.execute("INSERT INTO categories (name, description) VALUES (?, 'قسم مضاف حديثاً')", (text,))
            context.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ تم إنشاء القسم: **{text}** بنجاح!", parse_mode="Markdown")
            return

        elif a_state == "waiting_welcome_text":
            set_setting("welcome_text", text)
            context.user_data.pop("adm_state", None)
            await msg.reply_text("✅ تم تحديث رسالة الترحيب بنجاح!")
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

        # خطوات إضافة كتاب/ملف
        elif a_state == "waiting_book_title":
            context.user_data["temp_b_title"] = text
            context.user_data["adm_state"] = "waiting_book_desc"
            await msg.reply_text("أرسلي وصفاً مختصراً للمادة (أو اكتبي: لا يوجد):")
            return

        elif a_state == "waiting_book_desc":
            context.user_data["temp_b_desc"] = "" if text == "لا يوجد" else text
            context.user_data["adm_state"] = "waiting_book_file"
            await msg.reply_text("📥 الآن أرسلي **ملف الـ PDF**، أو **الفيديو**، أو **الصورة**، أو **رابط خارجي** (أو اكتبي: بدون):")
            return

        elif a_state == "waiting_book_file":
            cid = context.user_data.get("adm_target_cid", 1)
            title = context.user_data.pop("temp_b_title", "مادة معرفية")
            desc = context.user_data.pop("temp_b_desc", "")
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
                           (cid, title, desc, b_url, fid, m_type, now_text()))
            await msg.reply_text(f"✅ تمت إضافة **{title}** إلى القسم المحدد بنجاح ومتاح للجميع الآن!", parse_mode="Markdown")
            return

        # خطوات إضافة خدمة تصميم
        elif a_state == "waiting_design_title":
            context.user_data["temp_d_title"] = text
            context.user_data["adm_state"] = "waiting_design_price"
            await msg.reply_text("أرسلي سعر الخدمة (مثال: 15$ أو 1000 جنيه):")
            return

        elif a_state == "waiting_design_price":
            title = context.user_data.pop("temp_d_title")
            price = text
            with db_connect() as db:
                db.execute("INSERT INTO designs (title, price, description) VALUES (?, ?, 'خدمة مخصصة وفق طلب العميل')", (title, price))
            context.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ تم إضافة خدمة **{title}** بسعر `{price}` بنجاح!", parse_mode="Markdown")
            return

# ==================================================
# أوامر الإشراف في المجموعات (تدعم المشرف المتخفي تلقائياً)
# ==================================================

async def is_group_admin(chat, user, bot):
    # التعرف على المشرف المتخفي وقنوات التيليجرام
    if user.id in [chat.id, 1087968824, 777000] or is_owner(user.id):
        return True
    try:
        m = await chat.get_member(user.id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE:
        return
    if not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        await msg.reply_text("الرجاء الرد على الرسالة لحذفها.")
        return
    try:
        await msg.reply_to_message.delete()
        await msg.delete()
    except Exception:
        pass

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE:
        return
    if not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    t = msg.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=t.id)
        await msg.reply_text(f"🚫 تم حظر العضو {t.full_name}.")
    except Exception as e:
        await msg.reply_text(f"تعذر الحظر: {e}")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE:
        return
    if not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    t = msg.reply_to_message.from_user
    try:
        await context.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=t.id, only_if_banned=True)
        await msg.reply_text(f"✅ تم إلغاء حظر العضو {t.full_name}.")
    except Exception as e:
        await msg.reply_text(f"تعذر فك الحظر: {e}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE:
        return
    if not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    t = msg.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=t.id, permissions=ChatPermissions(can_send_messages=False))
        await msg.reply_text(f"🔇 تم كتم العضو {t.full_name}.")
    except Exception as e:
        await msg.reply_text(f"تعذر الكتم: {e}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE:
        return
    if not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    t = msg.reply_to_message.from_user
    try:
        p = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True)
        await context.bot.restrict_chat_member(chat_id=update.effective_chat.id, user_id=t.id, permissions=p)
        await msg.reply_text(f"🔊 تم فك كتم العضو {t.full_name}.")
    except Exception as e:
        await msg.reply_text(f"تعذر فك الكتم: {e}")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if update.effective_chat.type == ChatType.PRIVATE:
        return
    if not await is_group_admin(update.effective_chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    t = msg.reply_to_message.from_user
    with db_connect() as db:
        db.execute("INSERT INTO warnings (chat_id, user_id, created_at) VALUES (?, ?, ?)", (update.effective_chat.id, t.id, now_text()))
        cnt = db.execute("SELECT COUNT(*) FROM warnings WHERE chat_id = ? AND user_id = ?", (update.effective_chat.id, t.id)).fetchone()[0]

    if cnt >= 3:
        try:
            await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=t.id)
            await msg.reply_text(f"🚫 تم حظر العضو {t.full_name} لتجاوز 3 تحذيرات.")
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
        await update.effective_message.reply_text("✅ تم إرسال الرد للمستخدم وإغلاق التذكرة.")
    except Exception as e:
        await update.effective_message.reply_text(f"تعذر الإرسال: {e}")

# ==================================================
# خادم الويب المدمج لـ Render ونقطة البداية
# ==================================================

async def handle_health(request):
    return web.Response(text="Dua Space Engine: 100% Active", status=200)

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN مفقود في متغيرات البيئة!")

    init_database()

    # تشغيل خادم ويب مدمج لفحص الاتصال بـ Render
    app_web = web.Application()
    app_web.router.add_get("/", handle_health)
    app_web.router.add_get("/health", handle_health)

    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    application = Application.builder().token(BOT_TOKEN).build()

    # أوامر البوت
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("reply", cmd_reply))

    # أوامر الإشراف في المجموعات
    application.add_handler(CommandHandler("del", cmd_del))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("mute", cmd_mute))
    application.add_handler(CommandHandler("unmute", cmd_unmute))
    application.add_handler(CommandHandler("warn", cmd_warn))

    # معالجات الأزرار
    application.add_handler(CallbackQueryHandler(handle_navigation, pattern=r"^(nav:|lib:|order:|tasbeeh:|q:)"))
    application.add_handler(CallbackQueryHandler(admin_actions, pattern=r"^adm:"))

    # معالج الرسائل والملفات
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_incoming_messages))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Dua Space Engine successfully running.")
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
