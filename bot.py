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
logger = logging.getLogger("DuaSpaceGodModeCore")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@DuaSpace1").strip()

try:
    ADMIN_ID = int(os.environ.get("ADMIN_ID", "0").strip())
except ValueError:
    ADMIN_ID = 0

DB_PATH = os.environ.get("DATABASE_PATH", "duaspace.db")
CHANNEL_URL = "https://t.me/DuaSpace1"
BOT_USERNAME = os.environ.get("BOT_USERNAME", "DuaSpaceHelperBot").strip().lstrip("@")

# -------------------- قاعدة البيانات الشاملة --------------------

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

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                quiz_score INTEGER DEFAULT 0,
                referral_count INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                warns INTEGER DEFAULT 0,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                media_type TEXT DEFAULT 'text',
                file_id TEXT DEFAULT NULL,
                btn_url TEXT DEFAULT NULL,
                position INTEGER DEFAULT 50
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
                ticket_id TEXT UNIQUE,
                user_id INTEGER NOT NULL,
                username TEXT,
                service_id INTEGER,
                service_title TEXT NOT NULL,
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'قيد الانتظار',
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

            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_code TEXT UNIQUE,
                user_id INTEGER NOT NULL,
                admin_msg_id INTEGER UNIQUE,
                user_msg_id INTEGER,
                status TEXT DEFAULT 'مفتوحة',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        con.commit()

        # ضبط رسالة الترحيب
        welcome_default = (
            "أهلًا بكم في منصة Dua Space الشاملة! 🪐\n"
            "مساحتكم الأولى للإبداع، المعرفة الأكاديمية، والارتقاء.\n"
            "يرجى اختيار القسم المطلوب عبر الأزرار أدناه:"
        )
        if not con.execute("SELECT key FROM settings WHERE key = 'welcome_msg'").fetchone():
            con.execute("INSERT INTO settings(key, value) VALUES('welcome_msg', ?)", (welcome_default,))

        # الأقسام الافتراضية
        default_sections = [
            ("services", "🛍️ خدمات واستوديو Dua Space", "🛍️ **خدمات واستوديو Dua Space للتصميم والحلول الرقمية:**\nاختر الخدمة المطلوبة لمعرفة التفاصيل والبدء في الطلب مباشرة:", "text", None, None, 1),
            ("engineering", "📐 الصرح الهندسي والتقني", "📐 **الصرح الهندسي والتقني الشامل 🪐**\nبوابتكم لأقوى مراجع الهندسة الطبية الحيوية، البرمجيات، والذكاء الاصطناعي.", "text", None, None, 2),
            ("quiz", "🧠 بنك تحديات الذكاء والمخ", "🧠 **تحديات واختبارات الذكاء وتدريب المخ:**\nحل الأسئلة ونافس في لوحة الصدارة العامة!", "text", None, None, 3),
            ("scholarships", "🎓 دليل المنح والفرص الشامل", "🎓 **دليل المنح الدولية الشاملة:**\n• المنحة التركية\n• منحة الحكومة المجرية\n• منحة روسيا\n• منح جامعات قطر", "text", None, None, 4),
            ("anime", "🎌 عالم الأنمي والمانجا", "🎌 **عالم الأنمي والمانجا والروايات المترجمة:**\nمساحتكم الترفيهية لمتابعة فصول المانجا وروايات اللايت نوفل.", "text", None, None, 5),
            ("pomodoro", "⏱️ رفيق التركيز (Pomodoro)", "⏱️ **مؤقت التركيز (Pomodoro):**\nجلسات تركيز 25 دقيقة لإنجاز مهامك بكفاءة دون مشتتات.", "text", None, None, 6),
            ("tasbeeh", "📿 السبحة الإلكترونية", "📿 **السبحة الرقمية التفاعلية:**", "text", None, None, 7),
            ("leaderboard", "🏆 لوحة صدارة المتفوقين", "🏆 **لوحة صدارة أعضاء مجتمع Dua Space:**\nقائمة بأنشط الأعضاء في حل التحديات ونشر المنصة.", "text", None, None, 8),
            ("referral", "👥 رابط دعوتي وهديتي", "👥 **نظام المكافآت والإحالات:**\nشارك رابطك الخاص واكسب نقاطاً إضافية في المنصة!", "text", None, None, 9),
        ]
        for code, title, content, m_type, fid, b_url, pos in default_sections:
            if not con.execute("SELECT id FROM sections WHERE code = ?", (code,)).fetchone():
                con.execute(
                    "INSERT INTO sections(code, title, content, media_type, file_id, btn_url, position) VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (code, title, content, m_type, fid, b_url, pos)
                )

        # خدمات التصميم
        default_services = [
            ("🎨 تصميم الهويات البصرية والشعارات", "تصميم هويات متكاملة وشعارات مبتكرة للمشاريع.", "حسب الطلب"),
            ("🖼️ بوسترات وبنرات إعلانية", "تصاميم سوشيال ميديا احترافية بجودة عالية.", "حسب الطلب"),
            ("💌 بطاقات دعوة وتهنئة رقمية", "تصاميم مبتكرة وخاصة بالمناسبات والفعاليات.", "حسب الطلب"),
            ("📦 طلب تصميم مخصص", "أرسل تفاصيل مشروعك لنحدد التكلفة والمدة المناسبة.", "يحدد لاحقاً"),
        ]
        for t, d, p in default_services:
            if not con.execute("SELECT id FROM services WHERE title = ?", (t,)).fetchone():
                con.execute("INSERT INTO services(title, description, price, active) VALUES(?, ?, ?, 1)", (t, d, p))

        # أسئلة كويز تأسيسية
        if con.execute("SELECT COUNT(*) as n FROM questions").fetchone()["n"] == 0:
            con.execute(
                "INSERT INTO questions(question, options_json, answer_index, explanation) VALUES(?, ?, ?, ?)",
                ("🧠 ذكاء منطقي: ما هو الشيء الذي يملك عيناً واحدة ولا يرى بها؟", json.dumps(["الإبرة", "الإعصار", "المرآة", "الساعة"], ensure_ascii=False), 0, "الإبرة لها عين (ثقب الخيط) ولكنها لا ترى بها!")
            )
            con.execute(
                "INSERT INTO questions(question, options_json, answer_index, explanation) VALUES(?, ?, ?, ?)",
                ("🧩 شيء يزداد كلما أخذت منه؟", json.dumps(["الحفرة", "العمر", "المعرفة", "المال"], ensure_ascii=False), 0, "الحفرة! كلما أخذت منها تراباً زاد حجمها.")
            )

        con.commit()
    finally:
        con.close()

def save_user(user, referrer_id=None):
    if not user:
        return
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    con = db_connect()
    try:
        existing = con.execute("SELECT user_id, referred_by FROM users WHERE user_id = ?", (user.id,)).fetchone()
        if not existing:
            con.execute(
                "INSERT INTO users(user_id, username, first_name, referred_by, first_seen, last_seen) VALUES(?, ?, ?, ?, ?, ?)",
                (user.id, user.username or "", user.first_name or "", referrer_id, now, now)
            )
            if referrer_id and referrer_id != user.id:
                con.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referrer_id,))
        else:
            con.execute(
                "UPDATE users SET username = ?, first_name = ?, last_seen = ? WHERE user_id = ?",
                (user.username or "", user.first_name or "", now, user.id)
            )
        con.commit()
    finally:
        con.close()

def is_admin_user(user_id):
    return bool(ADMIN_ID and user_id == ADMIN_ID)

async def is_chat_admin(chat, user, bot):
    if user.id in [chat.id, 1087968824, 777000]:
        return True
    if is_admin_user(user.id):
        return True
    try:
        member = await chat.get_member(user.id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

# -------------------- فحص الاشتراك الإجباري --------------------

async def is_user_subscribed(bot, user_id):
    if is_admin_user(user_id):
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as exc:
        logger.warning(f"Subscription error: {exc}")
        return True

def force_sub_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 انضم لقناة Dua Space أولاً", url=CHANNEL_URL)],
            [InlineKeyboardButton("✅ تحقّق من الاشتراك", callback_data="check_subscription")],
        ]
    )

# -------------------- القوائم المنسقة للمستخدم --------------------

def main_menu_keyboard():
    rows = db_all("SELECT * FROM sections ORDER BY position ASC, id ASC")
    buttons = []
    current_row = []

    for s in rows:
        btn_text = s["title"]
        if s["btn_url"]:
            btn = InlineKeyboardButton(btn_text, url=s["btn_url"])
        else:
            code = s["code"] or f"custom_{s['id']}"
            btn = InlineKeyboardButton(btn_text, callback_data=f"sec_click:{code}")

        if len(btn_text) > 22 or s["code"] in ["services", "leaderboard"]:
            if current_row:
                buttons.append(current_row)
                current_row = []
            buttons.append([btn])
        else:
            current_row.append(btn)
            if len(current_row) == 2:
                buttons.append(current_row)
                current_row = []

    if current_row:
        buttons.append(current_row)

    buttons.append([InlineKeyboardButton("💬 الدعم والتواصل المباشر مع الإدارة", callback_data="start_support_ticket")])
    return InlineKeyboardMarkup(buttons)

def services_menu_keyboard():
    rows = db_all("SELECT id, title FROM services WHERE active = 1 ORDER BY id ASC")
    buttons = [[InlineKeyboardButton(f"✨ {r['title']}", callback_data=f"show_service:{r['id']}")] for r in rows]
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])
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
                InlineKeyboardButton("🔄 تصفير العداد", callback_data=f"treset:{phrase}"),
                InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home"),
            ],
        ]
    )

# -------------------- لوحة تحكم المالك المطلقة (God Mode CMS) --------------------

def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 إحصائيات المنصة الحقيقية", callback_data="adm_stats")],
            [
                InlineKeyboardButton("📂 التحكم بالأقسام والمحتوى", callback_data="adm_sections_hub"),
                InlineKeyboardButton("📝 تعديل رسالة الترحيب", callback_data="adm_edit_welcome"),
            ],
            [
                InlineKeyboardButton("🧠 بنك الكويز والتحديات", callback_data="adm_quiz_hub"),
                InlineKeyboardButton("📥 تذاكر وطلبات الأعضاء", callback_data="adm_tickets_hub"),
            ],
            [
                InlineKeyboardButton("📢 إذاعة عامة (Broadcast)", callback_data="adm_broadcast"),
                InlineKeyboardButton("💾 تحميل نسخة قاعدة البيانات", callback_data="adm_backup"),
            ],
            [
                InlineKeyboardButton("👀 معاينة واجهة المستخدم", callback_data="home"),
            ],
        ]
    )

# -------------------- أوامر حماية القروبات وإلغاء العقوبات --------------------

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return
    if not await is_chat_admin(chat, update.effective_user, context.bot):
        await msg.reply_text("❌ مخصص لمشرفي المجموعة فقط.")
        return
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ يرجى الرد على الرسالة المراد حذفها بالأمر `/del`")
        return
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=msg.reply_to_message.message_id)
        await context.bot.delete_message(chat_id=chat.id, message_id=msg.message_id)
    except Exception:
        pass

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return
    if not await is_chat_admin(chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    target = msg.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target.id)
        await msg.reply_text(f"🚫 تم حظر العضو {target.first_name} بنجاح.")
    except Exception as exc:
        await msg.reply_text(f"❌ تعذر الحظر: {exc}")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return
    if not await is_chat_admin(chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    target = msg.reply_to_message.from_user
    try:
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target.id, only_if_banned=True)
        await msg.reply_text(f"✅ تم إلغاء حظر {target.first_name}.")
    except Exception as exc:
        await msg.reply_text(f"❌ خطأ: {exc}")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return
    if not await is_chat_admin(chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    target = msg.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target.id, permissions=ChatPermissions(can_send_messages=False))
        await msg.reply_text(f"🔇 تم كتم {target.first_name}.")
    except Exception as exc:
        await msg.reply_text(f"❌ خطأ: {exc}")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return
    if not await is_chat_admin(chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    target = msg.reply_to_message.from_user
    try:
        p = ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target.id, permissions=p)
        await msg.reply_text(f"🔊 تم إلغاء كتم {target.first_name}.")
    except Exception as exc:
        await msg.reply_text(f"❌ خطأ: {exc}")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type in [ChatType.PRIVATE, ChatType.CHANNEL]:
        return
    if not await is_chat_admin(chat, update.effective_user, context.bot):
        return
    if not msg.reply_to_message:
        return
    target = msg.reply_to_message.from_user
    row = db_one("SELECT warns FROM users WHERE user_id = ?", (target.id,))
    warns = (row["warns"] if row else 0) + 1
    db_execute("UPDATE users SET warns = ? WHERE user_id = ?", (warns, target.id))

    if warns >= 3:
        try:
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=target.id)
            db_execute("UPDATE users SET warns = 0 WHERE user_id = ?", (target.id,))
            await msg.reply_text(f"🚫 تم حظر {target.first_name} لتجاوزه الحد الأقصى من التحذيرات (3/3).")
        except Exception:
            pass
    else:
        await msg.reply_text(f"⚠️ إنذار ({warns}/3) للعضو {target.first_name}.")

# -------------------- بدء التشغيل --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # معالجة رابط الدعوة والإحالات
    referrer_id = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0].split("_")[1])
        except Exception:
            referrer_id = None

    save_user(user, referrer_id)

    if chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text("🪐 مرحباً! أنا بوت Dua Space لحماية المجموعة وتقديم المراجع والخدمات.")
        return

    context.user_data.pop("flow", None)

    if not await is_user_subscribed(context.bot, user.id):
        await update.effective_message.reply_text(
            "⚠️ **تنبيه:** يرجى الانضمام لقناة Dua Space الرسمية أولاً لتتمكن من استخدام المنصة.",
            reply_markup=force_sub_keyboard(),
            parse_mode="Markdown",
        )
        return

    if is_admin_user(user.id):
        await update.effective_message.reply_text(
            "🪐 مرحباً بكِ دعاء في لوحة القيادة المطلقة (Dua Space Hub):\n"
            "التحكم الكامل بجميع الأزرار، الوسائط، النصوص، التذاكر، والمستخدمين بيدك:",
            reply_markup=admin_keyboard(),
        )
    else:
        welcome_text = get_setting("welcome_msg")
        await update.effective_message.reply_text(welcome_text, reply_markup=main_menu_keyboard())

# -------------------- معالجة نقرات الأزرار --------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    user_id = query.from_user.id

    if data == "check_subscription":
        if await is_user_subscribed(context.bot, user_id):
            await query.message.reply_text("🎉 تم التحقق من اشتراكك بنجاح!")
            welcome_text = get_setting("welcome_msg")
            await query.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text("❌ لم يتم التحقق بعد، انضم للقناة ثم حاول مجدداً.", reply_markup=force_sub_keyboard())
        return

    if not is_admin_user(user_id) and not await is_user_subscribed(context.bot, user_id):
        await query.message.reply_text("⚠️ يرجى الانضمام إلى القناة أولاً:", reply_markup=force_sub_keyboard())
        return

    if data == "home":
        context.user_data.pop("flow", None)
        welcome_text = get_setting("welcome_msg")
        await query.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())
        return

    # فتح تذكرة دعم
    if data == "start_support_ticket":
        context.user_data["flow"] = {"kind": "support_msg"}
        await query.message.reply_text(
            "💬 **مكتب الدعم والاستفسارات المباشر:**\n\n"
            "اكتب رسالتك أو استفسارك هنا مباشرة في رسالة واحدة، وسيتم فتح تذكرة رسمية وإيصالها للإدارة والرد عليك عبر البوت.\n"
            "للإلغاء أرسل /cancel."
        )
        return

    # لوحة الصدارة
    if data == "sec_click:leaderboard":
        top_quiz = db_all("SELECT first_name, quiz_score FROM users ORDER BY quiz_score DESC LIMIT 5")
        top_refs = db_all("SELECT first_name, referral_count FROM users ORDER BY referral_count DESC LIMIT 5")
        text = "🏆 **لوحة صدارة مجتمع Dua Space:**\n\n🧠 **أبطال التحديات والذكاء:**\n"
        for i, u in enumerate(top_quiz, 1):
            text += f"{i}. {u['first_name']} — {u['quiz_score']} نقطة\n"
        text += "\n👥 **أبطال نشر المنصة والدعوات:**\n"
        for i, u in enumerate(top_refs, 1):
            text += f"{i}. {u['first_name']} — {u['referral_count']} دعوة\n"
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]), parse_mode="Markdown")
        return

    # رابط الدعوة الخاص
    if data == "sec_click:referral":
        user_row = db_one("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
        refs = user_row["referral_count"] if user_row else 0
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        text = (
            f"👥 **نظام المكافآت والإحالات الخاص بك:**\n\n"
            f"🔗 **رابط دعوتك الشخصي:**\n`{ref_link}`\n\n"
            f"📊 عدد الأشخاص الذين انضموا عبرك: **{refs}** شخص\n\n"
            "انشر الرابط بين أصدقائك لجمع النقاط وتصدر لوحة الشرف 🪐"
        )
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]), parse_mode="Markdown")
        return

    # عرض الأقسام المتغيرة مع الوسائط (فيديو، PDF، صورة، صوت)
    if data.startswith("sec_click:"):
        code = data.split(":", 1)[1]
        sec = db_one("SELECT * FROM sections WHERE code = ?", (code,))
        if not sec and code.startswith("custom_"):
            sec = db_one("SELECT * FROM sections WHERE id = ?", (code.split("_")[1],))

        if not sec:
            await query.message.reply_text("القسم قيد التحديث 🪐", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]))
            return

        if code == "services":
            await query.message.reply_text(sec["content"], reply_markup=services_menu_keyboard(), parse_mode="Markdown")
            return
        elif code == "tasbeeh":
            await query.message.reply_text(sec["content"], reply_markup=tasbeeh_keyboard(0, "سبحان الله"), parse_mode="Markdown")
            return
        elif code == "pomodoro":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏳ بدء جلسة مذاكرة (25 دقيقة)", callback_data="pomo_run:25")], [InlineKeyboardButton("⬅️ عودة", callback_data="home")]])
            await query.message.reply_text(sec["content"], reply_markup=kb, parse_mode="Markdown")
            return
        elif code == "quiz":
            questions = db_all("SELECT * FROM questions")
            if not questions:
                await query.message.reply_text("يجري تحديث بنك الأسئلة قريباً 🪐", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]]))
                return
            q = random.choice(questions)
            opts = json.loads(q["options_json"])
            kb = [[InlineKeyboardButton(f"• {opt}", callback_data=f"quiz_ans:{q['id']}:{idx}")] for idx, opt in enumerate(opts)]
            kb.append([InlineKeyboardButton("🔄 سؤال آخر", callback_data="sec_click:quiz")])
            kb.append([InlineKeyboardButton("⬅️ عودة", callback_data="home")])
            await query.message.reply_text(f"🧠 **تحدي الذكاء والمخ:**\n\n{q['question']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            return

        # إرسال القسم بحسب نوع الوسائط المرفوعة له
        kb_back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ عودة", callback_data="home")]])
        m_type = sec["media_type"]
        fid = sec["file_id"]
        caption = sec["content"]

        if m_type == "video" and fid:
            await context.bot.send_video(chat_id=query.message.chat_id, video=fid, caption=caption, reply_markup=kb_back)
        elif m_type == "document" and fid:
            await context.bot.send_document(chat_id=query.message.chat_id, document=fid, caption=caption, reply_markup=kb_back)
        elif m_type == "photo" and fid:
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=fid, caption=caption, reply_markup=kb_back)
        elif m_type == "audio" and fid:
            await context.bot.send_audio(chat_id=query.message.chat_id, audio=fid, caption=caption, reply_markup=kb_back)
        else:
            await query.message.reply_text(caption, reply_markup=kb_back, parse_mode="Markdown")
        return

    # تفاعل الكويز
    if data.startswith("quiz_ans:"):
        _, q_id, opt_idx = data.split(":")
        q = db_one("SELECT * FROM questions WHERE id = ?", (int(q_id),))
        if q:
            opts = json.loads(q["options_json"])
            if int(opt_idx) == q["answer_index"]:
                db_execute("UPDATE users SET quiz_score = quiz_score + 1 WHERE user_id = ?", (user_id,))
                res = f"🎉 **إجابة عبقرية وصحيحة!**\n\n💡 {q['explanation']}"
            else:
                res = f"❌ **إجابة خاطئة!**\nالصواب: **{opts[q['answer_index']]}**\n\n💡 {q['explanation']}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 التحدي التالي", callback_data="sec_click:quiz")], [InlineKeyboardButton("⬅️ عودة", callback_data="home")]])
            await query.message.reply_text(res, reply_markup=kb, parse_mode="Markdown")
        return

    # بومودورو والسبحة
    if data.startswith("pomo_run:"):
        await query.message.reply_text("🚀 بدأت الـ 25 دقيقة تركيز! سننبهك فور انتهائها ✨")
        asyncio.create_task(run_pomodoro(query.message.chat_id, context))
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

    # تفاصيل الخدمة والطلب
    if data.startswith("show_service:"):
        s_id = int(data.split(":")[1])
        s = db_one("SELECT * FROM services WHERE id = ?", (s_id,))
        if s:
            text = f"✨ **{s['title']}**\n\nالوصف:\n{s['description']}\n\nالسعر: {s['price']}"
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📩 طلب هذه الخدمة الآن", callback_data=f"order_service:{s_id}")],
                    [InlineKeyboardButton("⬅️ عودة لقائمة الخدمات", callback_data="sec_click:services")],
                ]
            )
            await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if data.startswith("order_service:"):
        s_id = int(data.split(":")[1])
        context.user_data["flow"] = {"kind": "order_desc", "service_id": s_id}
        await query.message.reply_text("📝 اكتبي تفاصيل طلبك في رسالة واحدة (المقاسات، الألوان، والمطلوب):")
        return

    # -------------------- لوحة تحكم الإدارة المطلقة (God Mode) --------------------
    if not is_admin_user(user_id):
        return

    if data == "adm_home":
        await query.message.reply_text("🎛️ لوحة القيادة المركزية:", reply_markup=admin_keyboard())

    # إحصائيات حقيقية
    elif data == "adm_stats":
        u_count = db_one("SELECT COUNT(*) as n FROM users")["n"]
        s_count = db_one("SELECT COUNT(*) as n FROM sections")["n"]
        t_count = db_one("SELECT COUNT(*) as n FROM support_tickets")["n"]
        o_count = db_one("SELECT COUNT(*) as n FROM orders")["n"]
        q_count = db_one("SELECT COUNT(*) as n FROM questions")["n"]

        text = (
            "📊 **إحصائيات منصة Dua Space الشاملة والحقيقية:**\n\n"
            f"👥 **إجمالي المستخدمين المسجلين بالبوت:** `{u_count}` مستخدم\n"
            f"📂 **إجمالي الأقسام النشطة:** `{s_count}` قسم\n"
            f"🧠 **إجمالي أسئلة الكويز:** `{q_count}` سؤال\n"
            f"📥 **إجمالي التذاكر والاستفسارات:** `{t_count}` تذكرة\n"
            f"🛍️ **إجمالي طلبات التصميم:** `{o_count}` طلب\n\n"
            "⚡ البيانات مستخرجة فورياً ومباشرة من قاعدة البيانات."
        )
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="adm_home")]]), parse_mode="Markdown")

    # تعديل الترحيب
    elif data == "adm_edit_welcome":
        context.user_data["flow"] = {"kind": "set_welcome"}
        w = get_setting("welcome_msg")
        await query.message.reply_text(f"📝 **الرسالة الترحيبية الحالية:**\n\n{w}\n\n—\nأرسلي الآن النص الجديد الذي تريدين اعتماده:")

    # بوابة الأقسام والتحكم بها
    elif data == "adm_sections_hub":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("➕ إضافة قسم جديد (نص، فيديو، PDF، صورة)", callback_data="adm_sec_add")],
                [InlineKeyboardButton("✏️ تعديل اسم أو محتوى قسم حالي", callback_data="adm_sec_edit_list")],
                [InlineKeyboardButton("🗑️ حذف قسم نهائياً من القائمة", callback_data="adm_sec_del_list")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="adm_home")],
            ]
        )
        await query.message.reply_text("📂 **إدارة الأقسام والوسائط:**", reply_markup=kb)

    elif data == "adm_sec_add":
        context.user_data["pending_new_sec"] = {}
        context.user_data["flow"] = {"kind": "new_sec_title"}
        await query.message.reply_text("➕ أرسلي اسم الزر/القسم الجديد:")

    elif data == "adm_sec_edit_list":
        secs = db_all("SELECT id, title FROM sections ORDER BY position ASC, id ASC")
        kb = [[InlineKeyboardButton(f"✏️ {s['title']}", callback_data=f"edit_sec_item:{s['id']}")] for s in secs]
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_sections_hub")])
        await query.message.reply_text("اختاري القسم المراد تعديله:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("edit_sec_item:"):
        sec_id = int(data.split(":")[1])
        sec = db_one("SELECT * FROM sections WHERE id = ?", (sec_id,))
        if sec:
            context.user_data["edit_sec_id"] = sec_id
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✏️ تعديل اسم الزر فقط", callback_data="esec_name")],
                    [InlineKeyboardButton("📝 تعديل الشرح/النص فقط", callback_data="esec_text")],
                    [InlineKeyboardButton("📎 تحديث الملف/الفيديو للقسم", callback_data="esec_file")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="adm_sec_edit_list")],
                ]
            )
            await query.message.reply_text(f"⚙️ **تعديل قسم:** {sec['title']}\nنوع الوسائط الحالي: {sec['media_type']}", reply_markup=kb)

    elif data == "esec_name":
        context.user_data["flow"] = {"kind": "update_sec_name", "sec_id": context.user_data["edit_sec_id"]}
        await query.message.reply_text("أرسلي الاسم الجديد للزر:")

    elif data == "esec_text":
        context.user_data["flow"] = {"kind": "update_sec_text", "sec_id": context.user_data["edit_sec_id"]}
        await query.message.reply_text("أرسلي النص الكامل الجديد الذي سيظهر للمستخدم:")

    elif data == "esec_file":
        context.user_data["flow"] = {"kind": "update_sec_file", "sec_id": context.user_data["edit_sec_id"]}
        await query.message.reply_text("أرسلي الآن الفيديو أو ملف الـ PDF أو الصورة مباشرة:")

    elif data == "adm_sec_del_list":
        secs = db_all("SELECT id, title FROM sections ORDER BY position ASC, id ASC")
        kb = [[InlineKeyboardButton(f"❌ {s['title']}", callback_data=f"del_sec_now:{s['id']}")] for s in secs]
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_sections_hub")])
        await query.message.reply_text("🗑️ اختاري القسم المراد حذفه نهائياً من القائمة:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_sec_now:"):
        sec_id = int(data.split(":")[1])
        db_execute("DELETE FROM sections WHERE id = ?", (sec_id,))
        await query.message.reply_text("✅ تم حذف القسم فوراً من القائمة الرئيسية!", reply_markup=admin_keyboard())

    # بوابة الكويز
    elif data == "adm_quiz_hub":
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("➕ إضافة سؤال كويز جديد", callback_data="adm_add_q")],
                [InlineKeyboardButton("🗑️ حذف سؤال من الكويز", callback_data="adm_del_q_list")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="adm_home")],
            ]
        )
        await query.message.reply_text("🧠 **إدارة بنك الأسئلة والتحديات:**", reply_markup=kb)

    elif data == "adm_add_q":
        context.user_data["pending_question"] = {}
        context.user_data["flow"] = {"kind": "q_text"}
        await query.message.reply_text("أرسلي نص السؤال الجديد:")

    elif data == "adm_del_q_list":
        qs = db_all("SELECT id, question FROM questions ORDER BY id DESC LIMIT 15")
        if not qs:
            await query.message.reply_text("لا توجد أسئلة مسجلة حالياً.", reply_markup=admin_keyboard())
            return
        kb = [[InlineKeyboardButton(f"❌ {q['question'][:30]}...", callback_data=f"del_q_item:{q['id']}")] for q in qs]
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_quiz_hub")])
        await query.message.reply_text("اختاري السؤال المراد حذفه نهائياً:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_q_item:"):
        qid = int(data.split(":")[1])
        db_execute("DELETE FROM questions WHERE id = ?", (qid,))
        await query.message.reply_text("✅ تم حذف السؤال بنجاح من بنك الكويز!", reply_markup=admin_keyboard())

    # بوابة التذاكر والطلبات
    elif data == "adm_tickets_hub":
        orders = db_all("SELECT ticket_id, service_title, status FROM orders ORDER BY id DESC LIMIT 5")
        tickets = db_all("SELECT ticket_code, status FROM support_tickets ORDER BY id DESC LIMIT 5")
        text = "📥 **صندوق الطلبات والتذاكر الواردة:**\n\n🛍️ **أحدث طلبات التصميم:**\n"
        for o in orders:
            text += f"• `{o['ticket_id']}` ({o['status']}) - {o['service_title']}\n"
        text += "\n💬 **أحدث تذاكر الاستفسارات:**\n"
        for t in tickets:
            text += f"• تذكرة `{t['ticket_code']}` ({t['status']})\n"
        text += "\n💡 **للرد على أي استفسار:** اضغطي (Reply) على رسالة الإشعار واكتبي ردك مباشرة."
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="adm_home")]]), parse_mode="Markdown")

    elif data == "adm_broadcast":
        context.user_data["flow"] = {"kind": "broadcast"}
        await query.message.reply_text("📢 أرسلي الرسالة المراد بثها فوراً لجميع مستخدمي البوت:")

    elif data == "adm_backup":
        if os.path.exists(DB_PATH):
            await context.bot.send_document(chat_id=user_id, document=open(DB_PATH, "rb"), caption=f"💾 نسخة قاعدة البيانات الكاملة: {datetime.utcnow().strftime('%Y-%m-%d')}")
        else:
            await query.message.reply_text("ملف قاعدة البيانات غير متوفر.")

# -------------------- دالة مؤقت بومودورو --------------------

async def run_pomodoro(chat_id, context):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.send_message(chat_id=chat_id, text="🔔 **انتهت الـ 25 دقيقة!**\nعمل رائع، خذ استراحة 5 دقائق لتجديد طاقتك ✨", parse_mode="Markdown")
    except Exception:
        pass

# -------------------- معالجة النصوص والمدخلات والوسائط --------------------

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not msg.text:
        return

    save_user(user)

    if chat.type != ChatType.PRIVATE:
        return

    # الرد على التذاكر عبر الريبلاي
    if is_admin_user(user.id) and msg.reply_to_message:
        ticket = db_one("SELECT user_id, ticket_code FROM support_tickets WHERE admin_msg_id = ?", (msg.reply_to_message.message_id,))
        if ticket:
            try:
                header = f"🪐 **رد رسمي من إدارة Dua Space بخصوص التذكرة (`{ticket['ticket_code']}`):**\n\n"
                await context.bot.send_message(chat_id=ticket["user_id"], text=f"{header}{msg.text}", parse_mode="Markdown")
                await msg.reply_text("✅ تم إرسال ردكِ للعضو بنجاح وبخصوصية مطلقة.")
                return
            except Exception as e:
                await msg.reply_text(f"❌ تعذر إرسال الرد: {e}")
                return

    flow = context.user_data.get("flow")

    # إرسال رسالة دعم وفتح تذكرة
    if flow and flow.get("kind") == "support_msg":
        content = msg.text.strip()
        t_code = f"TKT-{random.randint(1000, 9999)}"
        context.user_data.pop("flow", None)
        await msg.reply_text(f"✅ تم فتح تذكرتك برقم: `{t_code}`\nسترد عليكِ الإدارة هنا عبر البوت قريباً 🪐", reply_markup=main_menu_keyboard(), parse_mode="Markdown")

        admin_text = (
            f"📩 **تذكرة استفسار جديدة (#{t_code})**\n\n"
            f"من: {user.first_name} (@{user.username or 'بدون'})\n"
            f"ID: `{user.id}`\n\n"
            f"الرسالة:\n{content}\n\n"
            f"—\n💡 **للرد عليه:** اضغطي رد (Reply) على هذه الرسالة مباشرة."
        )
        try:
            sent = await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
            db_execute("INSERT INTO support_tickets(ticket_code, user_id, admin_msg_id, user_msg_id) VALUES(?, ?, ?, ?)", (t_code, user.id, sent.message_id, msg.message_id))
        except Exception:
            pass
        return

    # طلب خدمة تصميم
    if flow and flow.get("kind") == "order_desc":
        s_id = flow["service_id"]
        service = db_one("SELECT * FROM services WHERE id = ?", (s_id,))
        t_id = f"ORD-{random.randint(1000, 9999)}"
        details = msg.text.strip()
        context.user_data.pop("flow", None)

        db_execute(
            "INSERT INTO orders(ticket_id, user_id, username, service_id, service_title, details, status) VALUES(?, ?, ?, ?, ?, ?, 'قيد الانتظار')",
            (t_id, user.id, user.username or "", s_id, service["title"] if service else "خدمة", details)
        )
        await msg.reply_text(f"✅ تم استلام طلبك برقم: `{t_id}`\nسنراجعه ونتواصل معك بأسرع وقت 🪐", reply_markup=main_menu_keyboard(), parse_mode="Markdown")

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🛍️ **طلب تصميم جديد (#{t_id})**\nالخدمة: {service['title']}\nمن: @{user.username}\nID: `{user.id}`\n\nالتفاصيل:\n{details}"
            )
        except Exception:
            pass
        return

    # إدارة النظام من الأدمن
    if is_admin_user(user.id) and flow:
        kind = flow.get("kind")
        val = msg.text.strip()

        if kind == "set_welcome":
            set_setting("welcome_msg", val)
            context.user_data.pop("flow", None)
            await msg.reply_text("✅ تم تحديث رسالة الترحيب بنجاح!", reply_markup=admin_keyboard())
            return

        elif kind == "new_sec_title":
            context.user_data["pending_new_sec"]["title"] = val
            context.user_data["flow"] = {"kind": "new_sec_text"}
            await msg.reply_text("أرسلي النص والشرح الذي سيظهر في هذا القسم:")
            return

        elif kind == "new_sec_text":
            context.user_data["pending_new_sec"]["content"] = val
            context.user_data["flow"] = {"kind": "new_sec_media"}
            await msg.reply_text("هل ترغبين بإرفاق (فيديو، PDF، أو صورة) لهذا القسم؟ أرسلي الملف الآن، أو اكتبي: بدون")
            return

        elif kind == "new_sec_media" and val == "بدون":
            p = context.user_data.pop("pending_new_sec", {})
            context.user_data.pop("flow", None)
            db_execute("INSERT INTO sections(code, title, content, media_type, file_id) VALUES(NULL, ?, ?, 'text', NULL)", (p["title"], p["content"]))
            await msg.reply_text("✅ تمت إضافة القسم بنجاح وظهر في القائمة الرئيسية!", reply_markup=admin_keyboard())
            return

        elif kind == "update_sec_name":
            db_execute("UPDATE sections SET title = ? WHERE id = ?", (val, flow["sec_id"]))
            context.user_data.pop("flow", None)
            await msg.reply_text("✅ تم تعديل اسم الزر بنجاح!", reply_markup=admin_keyboard())
            return

        elif kind == "update_sec_text":
            db_execute("UPDATE sections SET content = ? WHERE id = ?", (val, flow["sec_id"]))
            context.user_data.pop("flow", None)
            await msg.reply_text("✅ تم تعديل محتوى القسم بنجاح!", reply_markup=admin_keyboard())
            return

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
                await msg.reply_text("❌ يرجى إرسال خيارين على الأقل:")
                return
            context.user_data["pending_question"]["opts"] = opts
            context.user_data["flow"] = {"kind": "q_ans"}
            await msg.reply_text(f"ما هو رقم الإجابة الصحيحة؟ (من 1 إلى {len(opts)}):")
            return

        elif kind == "q_ans":
            try:
                ans_idx = int(val) - 1
            except ValueError:
                await msg.reply_text("❌ أرسلي رقماً فقط:")
                return
            context.user_data["pending_question"]["ans"] = ans_idx
            context.user_data["flow"] = {"kind": "q_exp"}
            await msg.reply_text("اكتبي شرح الإجابة وتوضيحها:")
            return

        elif kind == "q_exp":
            pq = context.user_data.pop("pending_question", {})
            context.user_data.pop("flow", None)
            db_execute(
                "INSERT INTO questions(question, options_json, answer_index, explanation) VALUES(?, ?, ?, ?)",
                (pq["q"], json.dumps(pq["opts"], ensure_ascii=False), pq["ans"], val)
            )
            await msg.reply_text("✅ تمت إضافة السؤال بنجاح إلى بنك التحديات!", reply_markup=admin_keyboard())
            return

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
            await msg.reply_text(f"📢 تمت الإذاعة بنجاح إلى {sent} مستخدم.", reply_markup=admin_keyboard())
            return

    if is_admin_user(user.id):
        await msg.reply_text("أهلاً بكِ دعاء 🪐\nأرسلي /admin لفتح لوحة القيادة، أو /cancel للإلغاء.")

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update.effective_user.id):
        return

    flow = context.user_data.get("flow")
    msg = update.effective_message

    file_id = None
    media_type = "text"

    if msg.video:
        file_id = msg.video.file_id
        media_type = "video"
    elif msg.document:
        file_id = msg.document.file_id
        media_type = "document"
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        media_type = "photo"
    elif msg.audio:
        file_id = msg.audio.file_id
        media_type = "audio"

    if not file_id:
        return

    # حفظ الوسائط لقسم جديد
    if flow and flow.get("kind") == "new_sec_media":
        p = context.user_data.pop("pending_new_sec", {})
        context.user_data.pop("flow", None)
        db_execute("INSERT INTO sections(code, title, content, media_type, file_id) VALUES(NULL, ?, ?, ?, ?)", (p["title"], p["content"], media_type, file_id))
        await msg.reply_text("✅ تم حفظ الملف وربطه بالقسم الجديد بنجاح!", reply_markup=admin_keyboard())
        return

    # تحديث الوسائط لقسم موجود
    if flow and flow.get("kind") == "update_sec_file":
        sec_id = flow["sec_id"]
        context.user_data.pop("flow", None)
        db_execute("UPDATE sections SET media_type = ?, file_id = ? WHERE id = ?", (media_type, file_id, sec_id))
        await msg.reply_text("✅ تم تحديث ملف ووسائط القسم بنجاح!", reply_markup=admin_keyboard())
        return

# -------------------- نقطة التشغيل وخادم الويب --------------------

async def handle_health(request):
    return web.Response(text="Dua Space God Mode Online 🪐", status=200)

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
    application.add_handler(CommandHandler("admin", lambda u, c: u.effective_message.reply_text("🎛️ لوحة القيادة المركزية:", reply_markup=admin_keyboard()) if is_admin_user(u.effective_user.id) else None))
    application.add_handler(CommandHandler("cancel", lambda u, c: u.effective_message.reply_text("تم الإلغاء.") if c.user_data.pop("flow", None) is not None else None))

    # أوامر حماية القروبات
    application.add_handler(CommandHandler("del", cmd_del))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("mute", cmd_mute))
    application.add_handler(CommandHandler("unmute", cmd_unmute))
    application.add_handler(CommandHandler("warn", cmd_warn))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    application.add_handler(MessageHandler(filters.ATTACHMENT, media_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.ALL, lambda u, c: c.bot.delete_message(chat_id=u.effective_chat.id, message_id=u.effective_message.message_id) if u.effective_chat.type != ChatType.PRIVATE else None))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Dua Space Core Engine is running.")
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
