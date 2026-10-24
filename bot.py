# -*- coding: utf-8 -*-
import asyncio
import html
import logging
import os
import sqlite3
import time
from datetime import timedelta
from pathlib import Path

import aiohttp
from aiohttp import web
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ChatPermissions,
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

# -------------------- الإعدادات --------------------

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("dua-space")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
PRIMARY_ADMIN_ID = 8669779200
ADMIN_IDS = {PRIMARY_ADMIN_ID}
if ADMIN_ID:
    ADMIN_IDS.add(ADMIN_ID)

CHANNEL_ID = os.getenv("CHANNEL_ID", "@DuaSpace1").strip()
DB_PATH = Path(os.getenv("DATABASE_PATH", "dua_space.db"))
PORT = int(os.getenv("PORT", "10000"))
PAGE_SIZE = 8
QURAN_API = "https://api.alquran.cloud/v1"

# -------------------- البيانات المبدئية --------------------

SURAHS = [
    ("الفاتحة", "Al-Fatihah"), ("البقرة", "Al-Baqarah"),
    ("آل عمران", "Ali 'Imran"), ("النساء", "An-Nisa"),
    ("المائدة", "Al-Ma'idah"), ("الأنعام", "Al-An'am"),
    ("الأعراف", "Al-A'raf"), ("الأنفال", "Al-Anfal"),
    ("التوبة", "At-Tawbah"), ("يونس", "Yunus"),
    ("هود", "Hud"), ("يوسف", "Yusuf"),
    ("الرعد", "Ar-Ra'd"), ("إبراهيم", "Ibrahim"),
    ("الحجر", "Al-Hijr"), ("النحل", "An-Nahl"),
    ("الإسراء", "Al-Isra"), ("الكهف", "Al-Kahf"),
    ("مريم", "Maryam"), ("طه", "Ta-Ha"),
    ("الأنبياء", "Al-Anbya"), ("الحج", "Al-Hajj"),
    ("المؤمنون", "Al-Mu'minun"), ("النور", "An-Nur"),
    ("الفرقان", "Al-Furqan"), ("الشعراء", "Ash-Shu'ara"),
    ("النمل", "An-Naml"), ("القصص", "Al-Qasas"),
    ("العنكبوت", "Al-'Ankabut"), ("الروم", "Ar-Rum"),
    ("لقمان", "Luqman"), ("السجدة", "As-Sajdah"),
    ("الأحزاب", "Al-Ahzab"), ("سبأ", "Saba"),
    ("فاطر", "Fatir"), ("يس", "Ya-Sin"),
    ("الصافات", "As-Saffat"), ("ص", "Sad"),
    ("الزمر", "Az-Zumar"), ("غافر", "Ghafir"),
    ("فصلت", "Fussilat"), ("الشورى", "Ash-Shuraa"),
    ("الزخرف", "Az-Zukhruf"), ("الدخان", "Ad-Dukhan"),
    ("الجاثية", "Al-Jathiyah"), ("الأحقاف", "Al-Ahqaf"),
    ("محمد", "Muhammad"), ("الفتح", "Al-Fath"),
    ("الحجرات", "Al-Hujurat"), ("ق", "Qaf"),
    ("الذاريات", "Adh-Dhariyat"), ("الطور", "At-Tur"),
    ("النجم", "An-Najm"), ("القمر", "Al-Qamar"),
    ("الرحمن", "Ar-Rahman"), ("الواقعة", "Al-Waqi'ah"),
    ("الحديد", "Al-Hadid"), ("المجادلة", "Al-Mujadila"),
    ("الحشر", "Al-Hashr"), ("الممتحنة", "Al-Mumtahanah"),
    ("الصف", "As-Saff"), ("الجمعة", "Al-Jumu'ah"),
    ("المنافقون", "Al-Munafiqun"), ("التغابن", "At-Taghabun"),
    ("الطلاق", "At-Talaq"), ("التحريم", "At-Tahrim"),
    ("الملك", "Al-Mulk"), ("القلم", "Al-Qalam"),
    ("الحاقة", "Al-Haqqah"), ("المعارج", "Al-Ma'arij"),
    ("نوح", "Nuh"), ("الجن", "Al-Jinn"),
    ("المزمل", "Al-Muzzammil"), ("المدثر", "Al-Muddaththir"),
    ("القيامة", "Al-Qiyamah"), ("الإنسان", "Al-Insan"),
    ("المرسلات", "Al-Mursalat"), ("النبأ", "An-Naba"),
    ("النازعات", "An-Nazi'at"), ("عبس", "'Abasa"),
    ("التكوير", "At-Takwir"), ("الانفطار", "Al-Infitar"),
    ("المطففين", "Al-Mutaffifin"), ("الانشقاق", "Al-Inshiqaq"),
    ("البروج", "Al-Buruj"), ("الطارق", "At-Tariq"),
    ("الأعلى", "Al-A'la"), ("الغاشية", "Al-Ghashiyah"),
    ("الفجر", "Al-Fajr"), ("البلد", "Al-Balad"),
    ("الشمس", "Ash-Shams"), ("الليل", "Al-Layl"),
    ("الضحى", "Ad-Duha"), ("الشرح", "Ash-Sharh"),
    ("التين", "At-Tin"), ("العلق", "Al-'Alaq"),
    ("القدر", "Al-Qadr"), ("البينة", "Al-Bayyinah"),
    ("الزلزلة", "Az-Zalzalah"), ("العاديات", "Al-'Adiyat"),
    ("القارعة", "Al-Qari'ah"), ("التكاثر", "At-Takathur"),
    ("العصر", "Al-'Asr"), ("الهمزة", "Al-Humazah"),
    ("الفيل", "Al-Fil"), ("قريش", "Quraysh"),
    ("الماعون", "Al-Ma'un"), ("الكوثر", "Al-Kawthar"),
    ("الكافرون", "Al-Kafirun"), ("النصر", "An-Nasr"),
    ("المسد", "Al-Masad"), ("الإخلاص", "Al-Ikhlas"),
    ("الفلق", "Al-Falaq"), ("الناس", "An-Nas"),
]

SEED_MATERIALS = [
    ("languages", "تعلم العربية", "دروس ومراجع لتعلم العربية.", "https://www.arabacademy.com/"),
    ("languages", "British Council — English", "مواد مفتوحة لتعلم الإنجليزية.", "https://learnenglish.britishcouncil.org/"),
    ("languages", "Turkish — Yunus Emre", "مصدر لتعلم اللغة التركية.", "https://www.yee.org.tr/en"),
    ("languages", "King Sejong Institute", "مصدر رسمي لتعلم الكورية.", "https://www.iksi.or.kr/"),
    ("languages", "NHK Easy Japanese", "دروس ومصادر لتعلم اليابانية.", "https://www.nhk.or.jp/lesson/"),
    ("languages", "Chinese — HelloChinese", "مصدر تعليمي للغة الصينية.", "https://www.hellochinese.cc/"),
    ("library", "Python Documentation", "التوثيق الرسمي للغة Python.", "https://docs.python.org/3/"),
    ("library", "MIT OpenCourseWare", "مواد تعليمية مفتوحة من MIT.", "https://ocw.mit.edu/"),
    ("library", "OpenStax Biology", "كتاب أحياء تعليمي مفتوح.", "https://openstax.org/subjects/science"),
    ("library", "MedlinePlus", "معلومات صحية تثقيفية من المكتبة الوطنية الأمريكية للطب.", "https://medlineplus.gov/"),
    ("library", "Project Gutenberg", "كتب أدبية متاحة ضمن مشروع Gutenberg.", "https://www.gutenberg.org/"),
    ("seerah", "السيرة النبوية — مرجع للقراءة", "أضف هنا مادتك الموثقة أو ملفًا عبر لوحة الإدارة.", "https://sunnah.com/"),
]

SEED_AZKAR = [
    ("الصباح", "أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير."),
    ("الصباح", "اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور."),
    ("المساء", "أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير."),
    ("المساء", "اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير."),
    ("النوم", "باسمك اللهم أموت وأحيا."),
    ("دعاء", "ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار."),
]

QUIZ = [
    ("كم عدد سور القرآن الكريم؟", ["112", "113", "114", "115"], 2, "عدد سور القرآن الكريم 114 سورة."),
    ("ما السورة التي تُسمى أم الكتاب؟", ["البقرة", "الفاتحة", "الإخلاص", "الناس"], 1, "سورة الفاتحة تُسمى أم الكتاب."),
    ("ما أول شهر في السنة الهجرية؟", ["رمضان", "محرم", "صفر", "رجب"], 1, "أول شهور السنة الهجرية هو محرم."),
]

# -------------------- قاعدة البيانات --------------------

def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            lang TEXT DEFAULT 'ar', joined_at INTEGER, last_seen INTEGER
        );
        CREATE TABLE IF NOT EXISTS materials(
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT DEFAULT '', url TEXT DEFAULT '',
            file_id TEXT DEFAULT '', file_type TEXT DEFAULT '', created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS favorites(
            user_id INTEGER, item_type TEXT, item_id TEXT,
            PRIMARY KEY(user_id, item_type, item_id)
        );
        CREATE TABLE IF NOT EXISTS azkar(
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, text TEXT
        );
        CREATE TABLE IF NOT EXISTS tasbeeh(
            user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            message TEXT, status TEXT DEFAULT 'open', created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS visits(
            category TEXT PRIMARY KEY, count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS warnings(
            chat_id INTEGER, user_id INTEGER, count INTEGER DEFAULT 0,
            PRIMARY KEY(chat_id, user_id)
        );
        """)

        if con.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0:
            now = int(time.time())
            con.executemany(
                "INSERT INTO materials(category,title,body,url,created_at) VALUES(?,?,?,?,?)",
                [(c, t, b, u, now) for c, t, b, u in SEED_MATERIALS],
            )
        if con.execute("SELECT COUNT(*) FROM azkar").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO azkar(category,text) VALUES(?,?)", SEED_AZKAR
            )
        defaults = {
            "maintenance": "0",
            "force_sub": "0",
            "welcome_ar": "أهلًا بك في Dua Space 🌙",
            "welcome_en": "Welcome to Dua Space 🌙",
        }
        for key, value in defaults.items():
            con.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                (key, value),
            )


def setting(key, default=""):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with db() as con:
        con.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


def is_admin(user_id):
    return user_id in ADMIN_IDS


def tr(lang, ar, en):
    return ar if lang != "en" else en


def user_lang(user_id):
    with db() as con:
        row = con.execute("SELECT lang FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["lang"] if row else "ar"


def register_user(user):
    now = int(time.time())
    with db() as con:
        con.execute(
            """INSERT INTO users(user_id,username,first_name,joined_at,last_seen)
               VALUES(?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
               username=excluded.username, first_name=excluded.first_name,
               last_seen=excluded.last_seen""",
            (user.id, user.username or "", user.first_name or "", now, now),
        )


def hit(category):
    with db() as con:
        con.execute(
            "INSERT INTO visits(category,count) VALUES(?,1) "
            "ON CONFLICT(category) DO UPDATE SET count=count+1",
            (category,),
        )


def main_menu(lang):
    labels = [
        (tr(lang, "📖 القرآن الكريم", "📖 Quran"), "q:0"),
        (tr(lang, "🤲 الأذكار والسبحة", "🤲 Azkar & Tasbeeh"), "azkar"),
        (tr(lang, "📚 المكتبة واللغات", "📚 Library & Languages"), "cats"),
        (tr(lang, "⭐ المفضلة", "⭐ Favorites"), "favorites"),
        (tr(lang, "🔎 البحث", "🔎 Search"), "search"),
        (tr(lang, "🎨 خدمات التصميم", "🎨 Design services"), "design"),
        (tr(lang, "🧠 المسابقة", "🧠 Quiz"), "quiz"),
        (tr(lang, "🌐 اللغة / Language", "🌐 Language / اللغة"), "language"),
        (tr(lang, "⏱️ مؤقت التركيز", "⏱️ Focus timer"), "pomodoro"),
        (tr(lang, "✉️ الدعم", "✉️ Support"), "support"),
    ]
    rows = [[InlineKeyboardButton(a, callback_data=b) for a, b in labels[i:i+2]]
            for i in range(0, len(labels), 2)]
    return InlineKeyboardMarkup(rows)


async def send_home(update, context, edit=False):
    user = update.effective_user
    lang = user_lang(user.id)
    text = setting("welcome_en" if lang == "en" else "welcome_ar")
    if setting("maintenance") == "1" and not is_admin(user.id):
        text = tr(lang, "🛠 البوت في وضع الصيانة. حاول لاحقًا.", "🛠 The bot is under maintenance. Please try again later.")
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu(lang))
    else:
        await update.effective_message.reply_text(text, reply_markup=main_menu(lang))


async def check_subscription(user_id, context):
    if setting("force_sub") != "1" or is_admin(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
    except Exception:
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    if not await check_subscription(update.effective_user.id, context):
        await update.message.reply_text(
            f"يرجى الاشتراك في {html.escape(CHANNEL_ID)} ثم أرسل /start مجددًا."
        )
        return
    await send_home(update, context)


# -------------------- أدوات الواجهة --------------------

def page_keyboard(prefix, page, total):
    last = max(0, (total - 1) // PAGE_SIZE)
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}:{page-1}"))
    buttons.append(InlineKeyboardButton(f"{page+1}/{last+1}", callback_data="noop"))
    if page < last:
        buttons.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}:{page+1}"))
    return [buttons, [InlineKeyboardButton("🏠 القائمة", callback_data="home")]]


async def show_quran(query, page):
    total = len(SURAHS)
    start_i = page * PAGE_SIZE
    rows = []
    for i in range(start_i, min(start_i + PAGE_SIZE, total)):
        ar, en = SURAHS[i]
        rows.append([
            InlineKeyboardButton(f"{i+1:03d}. {ar}", callback_data=f"qr:{i+1}"),
            InlineKeyboardButton("⭐", callback_data=f"favadd:s:{i+1}"),
        ])
    rows.extend(page_keyboard("q", page, total))
    await query.edit_message_text(
        "📖 <b>فهرس سور القرآن الكريم</b>\nاختر سورة للقراءة أو أضفها إلى المفضلة.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_materials(query, category, page):
    with db() as con:
        items = con.execute(
            "SELECT * FROM materials WHERE category=? ORDER BY id DESC",
            (category,),
        ).fetchall()
    title = {"languages": "اللغات الست", "library": "المكتبة والمراجع", "seerah": "السيرة النبوية"}
    rows = []
    slice_items = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    for item in slice_items:
        rows.append([
            InlineKeyboardButton(item["title"][:50], callback_data=f"mat:{item['id']}"),
            InlineKeyboardButton("⭐", callback_data=f"favadd:m:{item['id']}"),
        ])
    rows.extend(page_keyboard(f"m:{category}", page, len(items)))
    await query.edit_message_text(
        f"📚 <b>{html.escape(title.get(category, category))}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_categories(query):
    rows = [
        [InlineKeyboardButton("🌍 اللغات الست", callback_data="m:languages:0")],
        [InlineKeyboardButton("📚 مراجع عامة", callback_data="m:library:0")],
        [InlineKeyboardButton("🕌 السيرة النبوية", callback_data="m:seerah:0")],
        [InlineKeyboardButton("🏠 القائمة", callback_data="home")],
    ]
    await query.edit_message_text("اختر قسمًا:", reply_markup=InlineKeyboardMarkup(rows))


async def read_surah(query, number, context):
    ar_name = SURAHS[number - 1][0]
    await query.answer("يتم جلب السورة…")
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{QURAN_API}/surah/{number}/quran-uthmani") as response:
                response.raise_for_status()
                data = await response.json()
        surah = data["data"]
        text = f"📖 <b>سورة {html.escape(ar_name)}</b>\n\n"
        for ayah in surah["ayahs"]:
            text += f"{html.escape(ayah['text'])} <b>﴿{ayah['numberInSurah']}﴾</b>\n"
        chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
        for chunk in chunks:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=chunk,
                parse_mode="HTML",
            )
        audio = f"https://cdn.islamic.network/quran/audio-surah/128/ar.alafasy/{number}.mp3"
        await context.bot.send_audio(
            chat_id=query.message.chat_id,
            audio=audio,
            title=f"سورة {ar_name}",
            caption="🎧 تلاوة السورة",
        )
    except Exception:
        log.exception("Quran API request failed")
        await query.message.reply_text("تعذر جلب السورة الآن. حاول مرة أخرى لاحقًا.")


# -------------------- الأذكار، السبحة، البحث، التذاكر --------------------

async def show_azkar(query):
    rows = [
        [InlineKeyboardButton("🌅 أذكار الصباح", callback_data="az:الصباح")],
        [InlineKeyboardButton("🌆 أذكار المساء", callback_data="az:المساء")],
        [InlineKeyboardButton("🌙 أذكار النوم", callback_data="az:النوم")],
        [InlineKeyboardButton("🤲 أدعية متنوعة", callback_data="az:دعاء")],
        [InlineKeyboardButton("📿 السبحة الرقمية", callback_data="tasbeeh")],
        [InlineKeyboardButton("🏠 القائمة", callback_data="home")],
    ]
    await query.edit_message_text("🤲 <b>الأذكار والسبحة</b>", parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(rows))


async def show_azkar_category(query, category):
    with db() as con:
        rows = con.execute("SELECT text FROM azkar WHERE category=?", (category,)).fetchall()
    body = "\n\n".join(f"• {html.escape(r['text'])}" for r in rows) or "لا توجد أذكار في هذا القسم بعد."
    await query.edit_message_text(
        f"🤲 <b>أذكار {html.escape(category)}</b>\n\n{body}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ رجوع", callback_data="azkar")]]),
    )


async def show_tasbeeh(query, user_id):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO tasbeeh(user_id,count) VALUES(?,0)", (user_id,))
        count = con.execute("SELECT count FROM tasbeeh WHERE user_id=?", (user_id,)).fetchone()["count"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📿 تسبيح +1", callback_data="tas:+"),
         InlineKeyboardButton("🔄 تصفير", callback_data="tas:0")],
        [InlineKeyboardButton("↩️ رجوع", callback_data="azkar")],
    ])
    await query.edit_message_text(f"📿 <b>عداد التسبيح</b>\n\nالعدد الحالي: <b>{count}</b>",
                                  parse_mode="HTML", reply_markup=kb)


async def save_ticket(update, text):
    with db() as con:
        cur = con.execute(
            "INSERT INTO tickets(user_id,message,created_at) VALUES(?,?,?)",
            (update.effective_user.id, text, int(time.time())),
        )
        ticket_id = cur.lastrowid
    for admin_id in ADMIN_IDS:
        try:
            await update.get_bot().send_message(
                admin_id,
                f"✉️ تذكرة دعم #{ticket_id}\nمن: {update.effective_user.id}\n\n{html.escape(text)}\n\n"
                f"للرد: /reply {ticket_id} نص الرد",
                parse_mode="HTML",
            )
        except Exception:
            pass
    return ticket_id


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    state = context.user_data.get("state")

    if state == "search":
        context.user_data.pop("state", None)
        query = text[:100]
        with db() as con:
            materials = con.execute(
                "SELECT id,title,category FROM materials WHERE title LIKE ? OR body LIKE ? LIMIT 10",
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
        found = [f"• {html.escape(x['title'])} — /material_{x['id']}" for x in materials]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{QURAN_API}/search/{aiohttp.helpers.quote(query)}/all/ar"
                ) as response:
                    data = await response.json()
            quran_hits = data.get("data", {}).get("matches", [])[:5]
            for item in quran_hits:
                found.append(
                    f"• القرآن: سورة {html.escape(item['surah']['name'])}، آية {item['numberInSurah']}"
                )
        except Exception:
            pass
        await update.message.reply_text(
            "🔎 نتائج البحث:\n\n" + ("\n".join(found) if found else "لم أعثر على نتائج."),
            parse_mode="HTML",
        )
        return

    if state in ("design", "support"):
        context.user_data.pop("state", None)
        if state == "support":
            ticket_id = await save_ticket(update, text)
            await update.message.reply_text(f"وصلت رسالتك إلى فريق الدعم. رقم التذكرة: #{ticket_id}")
        else:
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"🎨 طلب تصميم جديد من {user_id} (@{update.effective_user.username or 'بدون اسم مستخدم'}):\n\n"
                        f"{html.escape(text)}",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            await update.message.reply_text("تم إرسال مواصفات التصميم إلى الإدارة للتواصل معك.")
        return

    if state == "admin_upload" and is_admin(user_id):
        parts = context.user_data.get("upload_meta", ("library", "مادة جديدة"))
        with db() as con:
            con.execute(
                "INSERT INTO materials(category,title,body,url,created_at) VALUES(?,?,?,?,?)",
                (parts[0], parts[1], text, text if text.startswith(("http://", "https://")) else "", int(time.time())),
            )
        context.user_data.pop("state", None)
        context.user_data.pop("upload_meta", None)
        await update.message.reply_text("تم حفظ المادة.")
        return

    await update.message.reply_text("استخدم الأزرار أو أرسل /start لعرض القائمة.")


async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) or context.user_data.get("state") != "admin_upload":
        return
    category, title = context.user_data.get("upload_meta", ("library", "ملف مرفوع"))
    message = update.message
    file_id, file_type = "", ""
    if message.document:
        file_id, file_type = message.document.file_id, "document"
    elif message.audio:
        file_id, file_type = message.audio.file_id, "audio"
    elif message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.video:
        file_id, file_type = message.video.file_id, "video"
    if not file_id:
        await message.reply_text("نوع الملف غير مدعوم.")
        return
    with db() as con:
        con.execute(
            "INSERT INTO materials(category,title,body,file_id,file_type,created_at) VALUES(?,?,?,?,?,?)",
            (category, title, message.caption or "", file_id, file_type, int(time.time())),
        )
    context.user_data.pop("state", None)
    context.user_data.pop("upload_meta", None)
    await message.reply_text("تم حفظ الملف وإتاحته في القسم.")


# -------------------- الإدارة --------------------

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats"),
         InlineKeyboardButton("🛠 الصيانة", callback_data="admin:maintenance")],
        [InlineKeyboardButton("🔒 الاشتراك الإجباري", callback_data="admin:subscription"),
         InlineKeyboardButton("📢 إذاعة", callback_data="admin:broadcast")],
        [InlineKeyboardButton("🏠 القائمة", callback_data="home")],
    ])


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🛡 <b>لوحة إدارة Dua Space</b>\n\n"
        "أوامر الإدارة:\n"
        "/addmaterial category|title — ثم أرسل نصًا أو ملفًا\n"
        "/delmaterial ID\n"
        "/addzekr category|النص\n"
        "/delzekr ID\n"
        "/broadcast نص الرسالة\n"
        "/reply رقم_التذكرة نص الرد\n"
        "/backup",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


async def add_material(update, context):
    if not is_admin(update.effective_user.id):
        return
    raw = " ".join(context.args).strip()
    if "|" not in raw:
        await update.message.reply_text("الصيغة: /addmaterial library|عنوان المادة")
        return
    category, title = [x.strip() for x in raw.split("|", 1)]
    if category not in {"library", "languages", "seerah"}:
        await update.message.reply_text("الأقسام المتاحة: library أو languages أو seerah")
        return
    context.user_data["state"] = "admin_upload"
    context.user_data["upload_meta"] = (category, title)
    await update.message.reply_text("أرسل الآن نص المادة أو رابطًا أو ملفًا/صورة/صوتًا/فيديو.")


async def delete_material(update, context):
    if not is_admin(update.effective_user.id) or not context.args:
        return
    try:
        with db() as con:
            con.execute("DELETE FROM materials WHERE id=?", (int(context.args[0]),))
        await update.message.reply_text("تم حذف المادة إن كان رقمها صحيحًا.")
    except ValueError:
        await update.message.reply_text("استخدم: /delmaterial ID")


async def add_zekr(update, context):
    if not is_admin(update.effective_user.id):
        return
    raw = " ".join(context.args)
    if "|" not in raw:
        await update.message.reply_text("الصيغة: /addzekr الصباح|نص الذكر")
        return
    category, text = raw.split("|", 1)
    with db() as con:
        con.execute("INSERT INTO azkar(category,text) VALUES(?,?)", (category.strip(), text.strip()))
    await update.message.reply_text("تمت إضافة الذكر.")


async def delete_zekr(update, context):
    if not is_admin(update.effective_user.id) or not context.args:
        return
    try:
        with db() as con:
            con.execute("DELETE FROM azkar WHERE id=?", (int(context.args[0]),))
        await update.message.reply_text("تم حذف الذكر إن كان رقمه صحيحًا.")
    except ValueError:
        await update.message.reply_text("استخدم: /delzekr ID")


async def broadcast(update, context):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("استخدم: /broadcast نص الرسالة")
        return
    with db() as con:
        users = con.execute("SELECT user_id FROM users").fetchall()
    sent = 0
    for row in users:
        try:
            await context.bot.send_message(row["user_id"], text)
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
    await update.message.reply_text(f"اكتملت الإذاعة. وصل الإرسال إلى {sent} مستخدمًا.")


async def reply_ticket(update, context):
    if not is_admin(update.effective_user.id) or len(context.args) < 2:
        return
    try:
        ticket_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("الصيغة: /reply رقم_التذكرة نص الرد")
        return
    answer = " ".join(context.args[1:])
    with db() as con:
        row = con.execute("SELECT user_id FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if row:
            con.execute("UPDATE tickets SET status='answered' WHERE id=?", (ticket_id,))
    if not row:
        await update.message.reply_text("لم يتم العثور على التذكرة.")
        return
    await context.bot.send_message(row["user_id"], f"💬 رد الإدارة على تذكرتك #{ticket_id}:\n\n{answer}")
    await update.message.reply_text("تم إرسال الرد.")


async def backup(update, context):
    if not is_admin(update.effective_user.id):
        return
    if not DB_PATH.exists():
        await update.message.reply_text("ملف قاعدة البيانات غير موجود.")
        return
    with DB_PATH.open("rb") as file:
        await update.message.reply_document(document=file, filename=DB_PATH.name,
                                            caption="🗄 نسخة احتياطية من قاعدة البيانات")
    if ADMIN_ID and ADMIN_ID != update.effective_user.id:
        with DB_PATH.open("rb") as file:
            await context.bot.send_document(ADMIN_ID, document=file, filename=DB_PATH.name)


# -------------------- المجموعات والإشراف --------------------

async def group_admin(update, context):
    if update.effective_chat.type == "private":
        return True
    user_id = update.effective_user.id
    if is_admin(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def moderate(update, context, action):
    message = update.effective_message
    if not await group_admin(update, context):
        return
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        await message.reply_text("استخدم الأمر بالرد على رسالة العضو.")
        return
    chat_id = update.effective_chat.id
    try:
        if action == "del":
            await message.reply_to_message.delete()
            await message.delete()
        elif action == "ban":
            await context.bot.ban_chat_member(chat_id, target.id)
        elif action == "unban":
            await context.bot.unban_chat_member(chat_id, target.id)
        elif action == "mute":
            await context.bot.restrict_chat_member(
                chat_id, target.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=timedelta(hours=1),
            )
        elif action == "unmute":
            await context.bot.restrict_chat_member(
                chat_id, target.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_other_messages=True,
                ),
            )
        elif action == "warn":
            with db() as con:
                con.execute(
                    "INSERT INTO warnings(chat_id,user_id,count) VALUES(?,?,1) "
                    "ON CONFLICT(chat_id,user_id) DO UPDATE SET count=count+1",
                    (chat_id, target.id),
                )
                count = con.execute(
                    "SELECT count FROM warnings WHERE chat_id=? AND user_id=?",
                    (chat_id, target.id),
                ).fetchone()["count"]
            await message.reply_text(f"⚠️ تحذير {count}/3 لـ {target.mention_html()}", parse_mode="HTML")
            if count >= 3:
                await context.bot.ban_chat_member(chat_id, target.id)
    except Exception as exc:
        await message.reply_text(f"تعذر تنفيذ الإجراء: {html.escape(str(exc))}")


# -------------------- التفاعلات --------------------

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = user_lang(user_id)

    if data == "noop":
        return
    if data == "home":
        await send_home(update, context, edit=True)
    elif data.startswith("q:"):
        await show_quran(query, int(data.split(":")[1]))
    elif data.startswith("qr:"):
        await read_surah(query, int(data.split(":")[1]), context)
    elif data == "cats":
        hit("library")
        await show_categories(query)
    elif data.startswith("m:"):
        parts = data.split(":")
        await show_materials(query, parts[1], int(parts[2]))
    elif data.startswith("mat:"):
        item_id = int(data.split(":")[1])
        with db() as con:
            item = con.execute("SELECT * FROM materials WHERE id=?", (item_id,)).fetchone()
        if not item:
            await query.message.reply_text("المادة غير موجودة.")
            return
        text = f"📚 <b>{html.escape(item['title'])}</b>\n\n{html.escape(item['body'] or '')}"
        if item["url"]:
            text += f"\n\n🔗 {html.escape(item['url'])}"
        if item["file_id"]:
            method = {
                "document": context.bot.send_document,
                "audio": context.bot.send_audio,
                "photo": context.bot.send_photo,
                "video": context.bot.send_video,
            }.get(item["file_type"])
            if method:
                await method(query.message.chat_id, item["file_id"], caption=item["title"])
        await query.message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ حفظ للمفضلة", callback_data=f"favadd:m:{item_id}")],
                [InlineKeyboardButton("↩️ رجوع", callback_data=f"m:{item['category']}:0")],
            ]),
            disable_web_page_preview=True,
        )
    elif data == "azkar":
        hit("azkar")
        await show_azkar(query)
    elif data.startswith("az:"):
        await show_azkar_category(query, data.split(":", 1)[1])
    elif data == "tasbeeh":
        await show_tasbeeh(query, user_id)
    elif data == "tas:+" or data == "tas:0":
        with db() as con:
            con.execute("INSERT OR IGNORE INTO tasbeeh(user_id,count) VALUES(?,0)", (user_id,))
            if data == "tas:+":
                con.execute("UPDATE tasbeeh SET count=count+1 WHERE user_id=?", (user_id,))
            else:
                con.execute("UPDATE tasbeeh SET count=0 WHERE user_id=?", (user_id,))
        await show_tasbeeh(query, user_id)
    elif data.startswith("favadd:"):
        _, item_type, item_id = data.split(":")
        with db() as con:
            con.execute(
                "INSERT OR IGNORE INTO favorites(user_id,item_type,item_id) VALUES(?,?,?)",
                (user_id, item_type, item_id),
            )
        await query.answer("أضيفت إلى المفضلة ⭐", show_alert=True)
    elif data == "favorites":
        with db() as con:
            items = con.execute(
                "SELECT item_type,item_id FROM favorites WHERE user_id=? ORDER BY rowid DESC LIMIT 30",
                (user_id,),
            ).fetchall()
        rows = []
        for item in items:
            if item["item_type"] == "s":
                n = int(item["item_id"])
                rows.append([InlineKeyboardButton(f"📖 سورة {SURAHS[n-1][0]}", callback_data=f"qr:{n}")])
            else:
                rows.append([InlineKeyboardButton(f"📚 مادة #{item['item_id']}", callback_data=f"mat:{item['item_id']}")])
        rows.append([InlineKeyboardButton("🏠 القائمة", callback_data="home")])
        await query.edit_message_text("⭐ <b>المفضلة</b>", parse_mode="HTML",
                                      reply_markup=InlineKeyboardMarkup(rows))
    elif data == "language":
        await query.edit_message_text(
            "اختر لغة الواجهة / Choose interface language",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("العربية", callback_data="lang:ar"),
                 InlineKeyboardButton("English", callback_data="lang:en")],
                [InlineKeyboardButton("🏠 القائمة", callback_data="home")],
            ]),
        )
    elif data.startswith("lang:"):
        new_lang = data.split(":")[1]
        with db() as con:
            con.execute("UPDATE users SET lang=? WHERE user_id=?", (new_lang, user_id))
        await send_home(update, context, edit=True)
    elif data == "search":
        context.user_data["state"] = "search"
        await query.message.reply_text("أرسل كلمة البحث في المكتبة أو القرآن.")
    elif data == "design":
        context.user_data["state"] = "design"
        await query.message.reply_text("أرسل مواصفات التصميم المطلوبة ووسيلة التواصل المناسبة.")
    elif data == "support":
        context.user_data["state"] = "support"
        await query.message.reply_text("اكتب رسالتك لفريق الدعم.")
    elif data == "quiz":
        q, options, answer, explanation = QUIZ[int(time.time()) % len(QUIZ)]
        context.user_data["quiz_answer"] = (answer, explanation)
        buttons = [[InlineKeyboardButton(opt, callback_data=f"quiz:{i}") for i, opt in enumerate(options)]]
        await query.message.reply_text(f"🧠 {q}", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("quiz:"):
        expected, explanation = context.user_data.get("quiz_answer", (-1, ""))
        chosen = int(data.split(":")[1])
        result = "✅ إجابة صحيحة!" if chosen == expected else "❌ ليست الإجابة الصحيحة."
        await query.message.reply_text(f"{result}\n{explanation}")
    elif data == "pomodoro":
        await query.edit_message_text(
            "⏱️ اختر مدة التركيز:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("25 دقيقة", callback_data="pom:25"),
                 InlineKeyboardButton("45 دقيقة", callback_data="pom:45")],
                [InlineKeyboardButton("60 دقيقة", callback_data="pom:60")],
                [InlineKeyboardButton("🏠 القائمة", callback_data="home")],
            ]),
        )
    elif data.startswith("pom:"):
        minutes = int(data.split(":")[1])
        if context.job_queue:
            context.job_queue.run_once(
                pomodoro_done, when=minutes * 60, chat_id=query.message.chat_id,
                user_id=user_id, name=f"pomodoro_{user_id}",
            )
            await query.message.reply_text(f"بدأ مؤقت التركيز لمدة {minutes} دقيقة. بالتوفيق! 🌿")
        else:
            await query.message.reply_text(f"⏱️ تم ضبط المؤقت لمدة {minutes} دقيقة.")
    elif data.startswith("admin:") and is_admin(user_id):
        action = data.split(":")[1]
        if action == "stats":
            with db() as con:
                users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                materials = con.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                tickets = con.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
                popular = con.execute("SELECT category,count FROM visits ORDER BY count DESC LIMIT 1").fetchone()
            await query.message.reply_text(
                f"📊 المستخدمون: {users}\n📚 المواد: {materials}\n✉️ التذاكر المفتوحة: {tickets}\n"
                f"🔥 الأكثر زيارة: {popular['category'] if popular else 'لا يوجد سجل'}"
            )
        elif action == "maintenance":
            value = "0" if setting("maintenance") == "1" else "1"
            set_setting("maintenance", value)
            await query.message.reply_text(f"وضع الصيانة: {'مفعّل' if value == '1' else 'معطّل'}")
        elif action == "subscription":
            value = "0" if setting("force_sub") == "1" else "1"
            set_setting("force_sub", value)
            await query.message.reply_text(f"الاشتراك الإجباري: {'مفعّل' if value == '1' else 'معطّل'}")
        elif action == "broadcast":
            context.user_data["state"] = "admin_broadcast"
            await query.message.reply_text("أرسل نص الإذاعة الآن.")
    else:
        await query.message.reply_text("استخدم /start لفتح القائمة.")


async def pomodoro_done(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    try:
        await context.bot.send_message(job.chat_id, "⏰ انتهى وقت التركيز! خذ استراحة قصيرة 🌿")
    except Exception:
        log.exception("Could not send Pomodoro notification")


async def broadcast_text_state(update, context):
    if context.user_data.get("state") == "admin_broadcast" and is_admin(update.effective_user.id):
        context.user_data.pop("state", None)
        context.args = update.message.text.split()
        await broadcast(update, context)
    else:
        await on_text(update, context)


# -------------------- خادم Render وتشغيل التطبيق --------------------

async def health(_request):
    try:
        with db() as con:
            con.execute("SELECT 1").fetchone()
        return web.json_response({"status": "ok", "service": "Dua Space"})
    except Exception:
        return web.json_response({"status": "error"}, status=503)


async def root(_request):
    return web.Response(text="Dua Space bot is running.", content_type="text/plain")


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("HTTP health server listening on port %s", PORT)
    return runner


async def run():
    if not BOT_TOKEN:
        raise RuntimeError("يجب ضبط BOT_TOKEN في متغيرات البيئة.")
    init_db()

    web_runner = await run_web_server()
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("addmaterial", add_material))
    application.add_handler(CommandHandler("delmaterial", delete_material))
    application.add_handler(CommandHandler("addzekr", add_zekr))
    application.add_handler(CommandHandler("delzekr", delete_zekr))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("reply", reply_ticket))
    application.add_handler(CommandHandler("backup", backup))

    for command, action in [
        ("del", "del"), ("ban", "ban"), ("unban", "unban"),
        ("mute", "mute"), ("unmute", "unmute"), ("warn", "warn"),
    ]:
        async def handler(update, context, _action=action):
            await moderate(update, context, _action)
        application.add_handler(CommandHandler(command, handler))

    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, on_media))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_text_state))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        log.info("Dua Space bot started.")
        await asyncio.Event().wait()
    finally:
        if application.updater and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
        await web_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run())
