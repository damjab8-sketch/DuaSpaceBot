# -*- coding: utf-8 -*-
# Dua Space Bot - Production Ready Engine
# Python 3.11+ | PTB 21.10 | Render Compatible

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
# 1. الإعدادات الأساسية
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

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
# 2. قاعدة البيانات المهيكلة
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
            media_type TEXT DEFAULT 'text',
            added_at TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY(category_id) REFERENCES categories(category_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scheduled_posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            sent INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quiz_scores (
            score_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """)

        defaults = {
            "maintenance": "0",
            "force_subscription": "1",
            "welcome_text": (
                "أهلًا بك في Dua Space 🌙\n\n"
                "مساحتك للمعرفة، القراءة، والتعلّم."
            ),
            "auto_posts_enabled": "0",
        }

        for key, value in defaults.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

        default_categories = [
            ("إسلاميات", "القرآن والتفسير والسيرة والحديث والأذكار"),
            ("قصص وروايات", "قصص وروايات عربية وعالمية ومترجمة"),
            ("تعلّم اللغات", "الإنجليزية والفرنسية وغيرها"),
            ("الطب والصحة", "كتب ومراجع في الطب والعلوم الصحية"),
            ("الهندسة والتقنية", "الهندسة والبرمجة والتكنولوجيا"),
            ("علم النفس", "علم النفس وتطوير الذات"),
        ]

        for position, (name, description) in enumerate(default_categories):
            db.execute("""
                INSERT INTO categories (name, description, position)
                SELECT ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = ?)
            """, (name, description, position, name))

def get_setting(key, default=""):
    with db_connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    with db_connect() as db:
        db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))

# ==================================================
# 3. الصلاحيات وتسجيل المستخدمين
# ==================================================

def is_owner(user_id):
    return ADMIN_ID != 0 and user_id == ADMIN_ID

def is_admin(user_id):
    return is_owner(user_id)

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not is_admin(user.id):
            if update.callback_query:
                await update.callback_query.answer("هذا القسم للإدارة فقط.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text("عذرًا، هذا الأمر متاح للإدارة فقط.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def register_user(user):
    current_time = now_text()
    with db_connect() as db:
        existing = db.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,)).fetchone()
        if existing:
            db.execute("UPDATE users SET username = ?, full_name = ?, last_seen = ? WHERE user_id = ?",
                       (user.username or "", user.full_name or "", current_time, user.id))
            return False
        db.execute("INSERT INTO users (user_id, username, full_name, joined_at, last_seen) VALUES (?, ?, ?, ?, ?)",
                   (user.id, user.username or "", user.full_name or "", current_time, current_time))
        return True

def get_statistics():
    with db_connect() as db:
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        today = datetime.now(timezone.utc).date().isoformat()
        new_today = db.execute("SELECT COUNT(*) FROM users WHERE substr(joined_at, 1, 10) = ?", (today,)).fetchone()[0]
        total_books = db.execute("SELECT COUNT(*) FROM books WHERE enabled = 1").fetchone()[0]
        total_categories = db.execute("SELECT COUNT(*) FROM categories WHERE enabled = 1").fetchone()[0]
        open_tickets = db.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]
    return {
        "users": total_users,
        "new_today": new_today,
        "books": total_books,
        "categories": total_categories,
        "open_tickets": open_tickets,
    }

# ==================================================
# 4. الاشتراك الإجباري والقوائم
# ==================================================

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if get_setting("force_subscription", "1") != "1" or is_owner(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except TelegramError:
        return True

def subscription_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 الاشتراك في القناة", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ تحقّق من الاشتراك", callback_data="check_subscription")],
    ])

def inline_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 المكتبة والمعرفة", callback_data="menu:library")],
        [InlineKeyboardButton("📿 التسبيح الإلكتروني", callback_data="menu:tasbeeh"), InlineKeyboardButton("🧠 بنك الاختبارات", callback_data="menu:quiz")],
        [InlineKeyboardButton("⏱️ مؤقت التركيز (Pomodoro)", callback_data="menu:pomo")],
        [InlineKeyboardButton("💬 الدعم والاستفسارات", callback_data="menu:support")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    register_user(user)

    if get_setting("maintenance", "0") == "1" and not is_admin(user.id):
        await message.reply_text("🛠️ البوت تحت الصيانة حاليًا.")
        return

    if not await check_subscription(user.id, context):
        await message.reply_text(
            "أهلًا بك في Dua Space 🌙\n\nللاستفادة من خدمات البوت، يرجى الاشتراك في القناة أولًا ثم الضغط على تحقق:",
            reply_markup=subscription_keyboard(),
        )
        return

    welcome = get_setting("welcome_text", "أهلًا بك في Dua Space 🌙")
    await message.reply_text(welcome, reply_markup=inline_main_menu())

# ==================================================
# 5. تصفح المكتبة والأقسام
# ==================================================

async def show_categories(query, context: ContextTypes.DEFAULT_TYPE):
    with db_connect() as db:
        rows = db.execute("SELECT category_id, name FROM categories WHERE enabled = 1 ORDER BY position, name").fetchall()

    buttons = [[InlineKeyboardButton(row["name"], callback_data=f"category:{row['category_id']}")] for row in rows]
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="menu:home")])

    await query.edit_message_text("📚 **مكتبة Dua Space الشاملة**\n\nاختاري القسم المطلوب:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def show_books(query, category_id: int, context: ContextTypes.DEFAULT_TYPE):
    with db_connect() as db:
        category = db.execute("SELECT name FROM categories WHERE category_id = ?", (category_id,)).fetchone()
        books = db.execute("SELECT book_id, title FROM books WHERE category_id = ? AND enabled = 1 ORDER BY book_id DESC", (category_id,)).fetchall()

    if not category:
        await query.edit_message_text("القسم غير متوفر حالياً.")
        return

    buttons = [[InlineKeyboardButton(f"📖 {b['title']}", callback_data=f"book:{b['book_id']}")] for b in books]
    buttons.append([InlineKeyboardButton("⬅️ العودة للأقسام", callback_data="menu:library")])

    text = f"📚 قسم: **{category['name']}**\n\n"
    text += "اختر الكتاب أو المرجع المراد عرضه:" if books else "لا توجد مواد مضافة في هذا القسم حتى الآن."
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def show_book_details(query, book_id: int, context: ContextTypes.DEFAULT_TYPE):
    with db_connect() as db:
        book = db.execute("SELECT * FROM books WHERE book_id = ? AND enabled = 1", (book_id,)).fetchone()

    if not book:
        await query.edit_message_text("الكتاب غير موجود.")
        return

    text = f"📖 **{book['title']}**\n\n{book['description'] or ''}"
    buttons = []
    if book["url"]:
        buttons.append([InlineKeyboardButton("📥 قراءة أو فتح الرابط", url=book["url"])])
    buttons.append([InlineKeyboardButton("⬅️ رجوع للأقسام", callback_data="menu:library")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    if book["file_id"]:
        try:
            m_type = book["media_type"]
            cid = query.from_user.id
            if m_type == "video":
                await context.bot.send_video(chat_id=cid, video=book["file_id"], caption=book["title"])
            elif m_type == "photo":
                await context.bot.send_photo(chat_id=cid, photo=book["file_id"], caption=book["title"])
            else:
                await context.bot.send_document(chat_id=cid, document=book["file_id"], caption=book["title"])
        except TelegramError:
            pass

# ==================================================
# 6. التسبيح ومؤقت التركيز
# ==================================================

def tasbeeh_keyboard(count=0):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📿 سبحان الله وبحمده ({count})", callback_data="tasbeeh:count")],
        [InlineKeyboardButton("🔄 تصفير العداد", callback_data="tasbeeh:reset")],
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="menu:home")],
    ])

async def open_tasbeeh(query, context: ContextTypes.DEFAULT_TYPE):
    count = context.user_data.get("tasbeeh_count", 0)
    await query.edit_message_text("📿 **السبحة الرقمية التفاعلية**\n\nسبحان الله، والحمد لله، ولا إله إلا الله، والله أكبر.", reply_markup=tasbeeh_keyboard(count), parse_mode="Markdown")

async def run_pomodoro(chat_id, context):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.send_message(chat_id=chat_id, text="🔔 **انتهت جلسة الـ 25 دقيقة!**\nعمل رائع، خذ استراحة 5 دقائق لتجديد طاقتك ✨", parse_mode="Markdown")
    except Exception:
        pass

# ==================================================
# 7. بنك الاختبارات والتحديات
# ==================================================

QUIZ_QUESTIONS = [
    {"question": "كم عدد أركان الإسلام؟", "options": ["أربعة", "خمسة", "ستة", "سبعة"], "answer": 1, "explanation": "أركان الإسلام خمسة."},
    {"question": "ما أكبر كوكب في المجموعة الشمسية؟", "options": ["الأرض", "المريخ", "المشتري", "زحل"], "answer": 2, "explanation": "المشتري هو أكبر كواكب مجموعتنا."},
    {"question": "ما ناتج 12 × 8؟", "options": ["86", "96", "108", "88"], "answer": 1, "explanation": "12 × 8 = 96."},
    {"question": "ما العضو المسؤول عن ضخ الدم في جسم الإنسان؟", "options": ["الرئة", "الكبد", "القلب", "الكلى"], "answer": 2, "explanation": "القلب يضخ الدم لجميع أنحاء الجسم."},
]

async def send_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(QUIZ_QUESTIONS)
    context.user_data["current_quiz"] = q
    buttons = [[InlineKeyboardButton(opt, callback_data=f"quiz:answer:{idx}")] for idx, opt in enumerate(q["options"])]
    buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="menu:home")])
    text = f"🧠 **تحدّي Dua Space:**\n\n{q['question']}\n\nاختاري الإجابة الصحيحة:"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

# ==================================================
# 8. معالجات الأزرار العامة
# ==================================================

async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "check_subscription":
        if await check_subscription(user_id, context):
            await query.edit_message_text("✅ تم التحقق من اشتراكك بنجاح!")
            welcome = get_setting("welcome_text", "أهلًا بك في Dua Space 🌙")
            await query.message.reply_text(welcome, reply_markup=inline_main_menu())
        else:
            await query.answer("لم يتم التأكد من الاشتراك بعد.", show_alert=True)
        return

    if data == "menu:home":
        context.user_data.pop("flow", None)
        welcome = get_setting("welcome_text", "أهلًا بك في Dua Space 🌙")
        await query.edit_message_text(welcome, reply_markup=inline_main_menu())

    elif data == "menu:library":
        await show_categories(query, context)

    elif data == "menu:tasbeeh":
        await open_tasbeeh(query, context)

    elif data == "tasbeeh:count":
        c = context.user_data.get("tasbeeh_count", 0) + 1
        context.user_data["tasbeeh_count"] = c
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(c))

    elif data == "tasbeeh:reset":
        context.user_data["tasbeeh_count"] = 0
        await query.edit_message_reply_markup(reply_markup=tasbeeh_keyboard(0))

    elif data == "menu:pomo":
        await query.message.reply_text("🚀 بدأت الـ 25 دقيقة تركيز! سننبهك فور انتهائها ✨")
        asyncio.create_task(run_pomodoro(query.message.chat_id, context))

    elif data.startswith("category:"):
        cid = int(data.split(":")[1])
        await show_books(query, cid, context)

    elif data.startswith("book:"):
        bid = int(data.split(":")[1])
        await show_book_details(query, bid, context)

    elif data == "menu:quiz":
        await send_quiz(update, context)

    elif data == "menu:support":
        context.user_data["flow"] = {"kind": "support_msg"}
        await query.message.reply_text("💬 اكتبي رسالتك أو استفسارك هنا مباشرة وسنرد عليك عبر البوت:")

    elif data.startswith("quiz:answer:"):
        q = context.user_data.get("current_quiz")
        if not q:
            await query.edit_message_text("انتهى السؤال السابق.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 سؤال آخر", callback_data="menu:quiz")]]))
            return
        ans = int(data.split(":")[2])
        corr = ans == q["answer"]
        if corr:
            with db_connect() as db:
                db.execute("INSERT INTO quiz_scores (user_id, score, created_at) VALUES (?, 1, ?)", (user_id, now_text()))
            res = "🎉 **إجابة صحيحة وذكية!**"
        else:
            res = f"❌ **إجابة خاطئة!** الصواب: {q['options'][q['answer']]}"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 سؤال آخر", callback_data="menu:quiz")],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="menu:home")]
        ])
        await query.edit_message_text(f"{res}\n\n💡 {q['explanation']}", reply_markup=kb, parse_mode="Markdown")

# ==================================================
# 9. لوحة تحكم الإدارة (Admin Panel)
# ==================================================

def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات الحقيقية", callback_data="admin:stats")],
        [InlineKeyboardButton("📚 إدارة الأقسام والمكتبة", callback_data="admin:library")],
        [InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="admin:add_cat")],
        [InlineKeyboardButton("📢 إذاعة للمستخدمين", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⚙️ إعدادات البوت والترحيب", callback_data="admin:settings")],
        [InlineKeyboardButton("👀 معاينة واجهة المستخدم", callback_data="menu:home")]
    ])

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("🛠️ **لوحة قيادة Dua Space الإدارية:**", reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

@admin_only
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin:home":
        await query.edit_message_text("🛠️ **لوحة التحكم:**", reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

    elif data == "admin:stats":
        s = get_statistics()
        text = (
            "📊 **إحصائيات منصة Dua Space الفعلية:**\n\n"
            f"👥 إجمالي المستخدمين: `{s['users']}`\n"
            f"🆕 المسجلين اليوم: `{s['new_today']}`\n"
            f"📚 إجمالي الكتب والمراجع: `{s['books']}`\n"
            f"📂 إجمالي الأقسام: `{s['categories']}`\n"
            f"💬 التذاكر المفتوحة: `{s['open_tickets']}`"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ رجوع", callback_data="admin:home")]]), parse_mode="Markdown")

    elif data == "admin:library":
        with db_connect() as db:
            rows = db.execute("SELECT category_id, name FROM categories ORDER BY name").fetchall()
        buttons = [[InlineKeyboardButton(f"📂 {r['name']}", callback_data=f"admin:cat:{r['category_id']}")] for r in rows]
        buttons.append([InlineKeyboardButton("➕ إضافة قسم", callback_data="admin:add_cat")])
        buttons.append([InlineKeyboardButton("↩️ رجوع", callback_data="admin:home")])
        await query.edit_message_text("📚 اختاري القسم لإدارته:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("admin:cat:"):
        cid = int(data.split(":")[2])
        context.user_data["admin_cid"] = cid
        with db_connect() as db:
            cat = db.execute("SELECT name FROM categories WHERE category_id = ?", (cid,)).fetchone()
            bks = db.execute("SELECT book_id, title FROM books WHERE category_id = ?", (cid,)).fetchall()

        buttons = [[InlineKeyboardButton(f"📖 {b['title']}", callback_data=f"admin:book:{b['book_id']}")] for b in bks]
        buttons.extend([
            [InlineKeyboardButton("➕ إضافة مادة/كتاب هنا", callback_data="admin:add_book")],
            [InlineKeyboardButton("🗑️ حذف هذا القسم كاملاً", callback_data="admin:del_cat")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="admin:library")]
        ])
        await query.edit_message_text(f"📂 قسم: **{cat['name']}** (المواد: {len(bks)})", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data == "admin:add_cat":
        context.user_data["admin_action"] = "add_cat_name"
        await query.message.reply_text("➕ أرسلي اسم القسم الجديد الآن:")

    elif data == "admin:del_cat":
        cid = context.user_data.get("admin_cid")
        with db_connect() as db:
            db.execute("DELETE FROM books WHERE category_id = ?", (cid,))
            db.execute("DELETE FROM categories WHERE category_id = ?", (cid,))
        await query.message.reply_text("🗑️ تم حذف القسم وجميع موارده بنجاح.")

    elif data == "admin:add_book":
        context.user_data["admin_action"] = "add_book_title"
        await query.message.reply_text("أرسلي عنوان الكتاب أو المورد:")

    elif data == "admin:broadcast":
        context.user_data["admin_action"] = "broadcast"
        await query.message.reply_text("📢 أرسلي الرسالة التي تريدين بثها لجميع المستخدمين:")

    elif data == "admin:settings":
        sub = get_setting("force_subscription", "1")
        maint = get_setting("maintenance", "0")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔐 الاشتراك الإجباري: {'مفعّل' if sub == '1' else 'معطّل'}", callback_data="admin:toggle_sub")],
            [InlineKeyboardButton(f"🛠️ وضع الصيانة: {'مفعّل' if maint == '1' else 'معطّل'}", callback_data="admin:toggle_maint")],
            [InlineKeyboardButton("✏️ تعديل رسالة الترحيب", callback_data="admin:set_welcome")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="admin:home")]
        ])
        await query.edit_message_text("⚙️ **إعدادات المنصة:**", reply_markup=kb, parse_mode="Markdown")

    elif data == "admin:toggle_sub":
        cur = get_setting("force_subscription", "1")
        set_setting("force_subscription", "0" if cur == "1" else "1")
        await query.message.reply_text("✅ تم تحديث إعداد الاشتراك.")

    elif data == "admin:toggle_maint":
        cur = get_setting("maintenance", "0")
        set_setting("maintenance", "0" if cur == "1" else "1")
        await query.message.reply_text("✅ تم تحديث وضع الصيانة.")

    elif data == "admin:set_welcome":
        context.user_data["admin_action"] = "set_welcome"
        await query.message.reply_text("أرسلي نص رسالة الترحيب الجديد الآن:")

# ==================================================
# 10. أوامر إشراف المجموعات (تدعم المشرف المتخفي تلقائياً)
# ==================================================

async def is_group_admin(chat, user, bot):
    # التعرف التلقائي على حسابات المجموعة المجهولة والقنوات المشرفة
    if user.id in [chat.id, 1087968824, 777000]:
        return True
    if is_owner(user.id):
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
        await msg.reply_text("❌ مخصص لمشرفي القروب فقط.")
        return
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ ردي على الرسالة بالأمر `/del`")
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
        await msg.reply_text(f"❌ تعذر الحظر: {e}")

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
        await msg.reply_text(f"✅ تم فك الحظر عن {t.full_name}.")
    except Exception as e:
        await msg.reply_text(f"❌ تعذر فك الحظر: {e}")

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
        await msg.reply_text(f"🔇 تم كتم {t.full_name}.")
    except Exception as e:
        await msg.reply_text(f"❌ تعذر الكتم: {e}")

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
        await msg.reply_text(f"🔊 تم إلغاء كتم {t.full_name}.")
    except Exception as e:
        await msg.reply_text(f"❌ تعذر فك الكتم: {e}")

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
        db.execute("INSERT INTO warnings (chat_id, user_id, reason, created_at) VALUES (?, ?, 'مخالفة', ?)", (update.effective_chat.id, t.id, now_text()))
        cnt = db.execute("SELECT COUNT(*) FROM warnings WHERE chat_id = ? AND user_id = ?", (update.effective_chat.id, t.id)).fetchone()[0]

    if cnt >= 3:
        try:
            await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=t.id)
            await msg.reply_text(f"🚫 تم حظر {t.full_name} لتجاوز 3 تحذيرات.")
        except Exception:
            pass
    else:
        await msg.reply_text(f"⚠️ تحذير ({cnt}/3) للعضو {t.full_name}.")

# ==================================================
# 11. موجه الرسائل والوسائط والدعم
# ==================================================

async def text_and_media_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or update.effective_chat.type != ChatType.PRIVATE:
        return

    val = (msg.text or msg.caption or "").strip()
    flow = context.user_data.get("flow")
    admin_act = context.user_data.get("admin_action")

    # دعم التذاكر من المستخدم
    if flow and flow.get("kind") == "support_msg":
        context.user_data.pop("flow", None)
        with db_connect() as db:
            cur = db.execute("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)", (user.id, val, now_text()))
            tid = cur.lastrowid
        await msg.reply_text(f"✅ تم فتح تذكرتك رقم `#{tid}` وسنرد عليك قريباً 🪐", parse_mode="Markdown")
        if ADMIN_ID:
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"📩 **تذكرة دعم جديدة (#{tid})**\nمن: {user.full_name} (`{user.id}`)\nالرسالة:\n{val}", parse_mode="Markdown")
            except Exception:
                pass
        return

    # إجراءات الأدمن وإدخال البيانات
    if is_admin(user.id) and admin_act:
        if admin_act == "add_cat_name":
            with db_connect() as db:
                db.execute("INSERT INTO categories (name) VALUES (?)", (val,))
            context.user_data.pop("admin_action", None)
            await msg.reply_text(f"✅ تمت إضافة قسم: {val}")
            return

        elif admin_act == "set_welcome":
            set_setting("welcome_text", val)
            context.user_data.pop("admin_action", None)
            await msg.reply_text("✅ تم تحديث رسالة الترحيب بنجاح!")
            return

        elif admin_act == "broadcast":
            context.user_data.pop("admin_action", None)
            with db_connect() as db:
                users = db.execute("SELECT user_id FROM users").fetchall()
            sent = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u["user_id"], text=val)
                    sent += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    pass
            await msg.reply_text(f"📢 تمت الإذاعة بنجاح إلى {sent} مستخدم.")
            return

        elif admin_act == "add_book_title":
            context.user_data["new_b_title"] = val
            context.user_data["admin_action"] = "add_book_desc"
            await msg.reply_text("أرسلي وصفاً مختصراً (أو اكتبي: بدون):")
            return

        elif admin_act == "add_book_desc":
            context.user_data["new_b_desc"] = "" if val == "بدون" else val
            context.user_data["admin_action"] = "add_book_media"
            await msg.reply_text("أرسلي الآن ملف الـ PDF أو الفيديو أو رابط خارجي (أو اكتبي: بدون):")
            return

        elif admin_act == "add_book_media":
            cid = context.user_data.get("admin_cid", 1)
            title = context.user_data.pop("new_b_title", "بدون عنوان")
            desc = context.user_data.pop("new_b_desc", "")
            context.user_data.pop("admin_action", None)

            fid, m_type, b_url = "", "text", ""
            if msg.document:
                fid, m_type = msg.document.file_id, "document"
            elif msg.video:
                fid, m_type = msg.video.file_id, "video"
            elif msg.photo:
                fid, m_type = msg.photo[-1].file_id, "photo"
            elif val.startswith("http"):
                b_url = val

            with db_connect() as db:
                db.execute("INSERT INTO books (category_id, title, description, url, file_id, media_type, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (cid, title, desc, b_url, fid, m_type, now_text()))
            await msg.reply_text(f"✅ تمت إضافة المادة بنجاح للمكتبة: {title}")
            return

# ==================================================
# 12. نقطة التشغيل وخادم الويب المدمج لـ Render
# ==================================================

async def handle_health(request):
    return web.Response(text="Dua Space Live Engine 🪐", status=200)

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN مفقود في إعدادات البيئة!")

    init_database()

    # خادم ويب لحماية البوت من الإغلاق في Render
    app_web = web.Application()
    app_web.router.add_get("/", handle_health)
    app_web.router.add_get("/health", handle_health)

    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    application = Application.builder().token(BOT_TOKEN).build()

    # أوامر عامة
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))

    # أوامر القروبات
    application.add_handler(CommandHandler("del", cmd_del))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("mute", cmd_mute))
    application.add_handler(CommandHandler("unmute", cmd_unmute))
    application.add_handler(CommandHandler("warn", cmd_warn))

    # الأزرار
    application.add_handler(CallbackQueryHandler(menu_callbacks, pattern=r"^(check_subscription|menu:|category:|book:|tasbeeh:|quiz:)"))
    application.add_handler(CallbackQueryHandler(admin_callbacks, pattern=r"^admin:"))

    # موجه النصوص والوسائط
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, text_and_media_router))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Dua Space Engine is completely running.")
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
