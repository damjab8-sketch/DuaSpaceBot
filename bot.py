# -*- coding: utf-8 -*-
import asyncio
import html
import logging
import os
import random
import sqlite3
import time
from datetime import timedelta
from pathlib import Path

import aiohttp
from aiohttp import web
from telegram import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
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

# -------------------- فهرس سور القرآن الـ 114 --------------------

SURAHS = [
    ("الفاتحة", 7), ("البقرة", 286), ("آل عمران", 200), ("النساء", 176),
    ("المائدة", 120), ("الأنعام", 165), ("الأعراف", 206), ("الأنفال", 75),
    ("التوبة", 129), ("يونس", 109), ("هود", 123), ("يوسف", 111),
    ("الرعد", 43), ("إبراهيم", 52), ("الحجر", 99), ("النحل", 128),
    ("الإسراء", 111), ("الكهف", 110), ("مريم", 98), ("طه", 135),
    ("الأنبياء", 112), ("الحج", 78), ("المؤمنون", 118), ("النور", 64),
    ("الفرقان", 77), ("الشعراء", 227), ("النمل", 93), ("القصص", 88),
    ("العنكبوت", 69), ("الروم", 60), ("لقمان", 34), ("السجدة", 30),
    ("الأحزاب", 73), ("سبأ", 54), ("فاطر", 45), ("يس", 83),
    ("الصافات", 182), ("ص", 88), ("الزمر", 75), ("غافر", 85),
    ("فصلت", 54), ("الشورى", 53), ("الزخرف", 89), ("الدخان", 59),
    ("الجاثية", 37), ("الأحقاف", 35), ("محمد", 38), ("الفتح", 29),
    ("الحجرات", 18), ("ق", 45), ("الذاريات", 60), ("الطور", 49),
    ("النجم", 62), ("القمر", 55), ("الرحمن", 78), ("الواقعة", 96),
    ("الحديد", 29), ("المجادلة", 22), ("الحشر", 24), ("الممتحنة", 13),
    ("الصف", 14), ("الجمعة", 11), ("المنافقون", 11), ("التغابن", 18),
    ("الطلاق", 12), ("التحريم", 12), ("الملك", 30), ("القلم", 52),
    ("الحاقة", 52), ("المعارج", 44), ("نوح", 28), ("الجن", 28),
    ("المزمل", 20), ("المدثر", 56), ("القيامة", 40), ("الإنسان", 31),
    ("المرسلات", 50), ("النبأ", 40), ("النازعات", 46), ("عبس", 42),
    ("التكوير", 29), ("الانفطار", 19), ("المطففين", 36), ("الانشقاق", 25),
    ("البروج", 22), ("الطارق", 17), ("الأعلى", 19), ("الغاشية", 26),
    ("الفجر", 30), ("البلد", 20), ("الشمس", 15), ("الليل", 21),
    ("الضحى", 11), ("الشرح", 8), ("التين", 8), ("العلق", 19),
    ("القدر", 5), ("البينة", 8), ("الزلزلة", 8), ("العاديات", 11),
    ("القارعة", 11), ("التكاثر", 8), ("العصر", 3), ("الهمزة", 9),
    ("الفيل", 5), ("قريش", 4), ("الماعون", 7), ("الكوثر", 3),
    ("الكافرون", 6), ("النصر", 3), ("المسد", 5), ("الإخلاص", 4),
    ("الفلق", 5), ("الناس", 6),
]

# -------------------- المراجع والبيانات المبدئية --------------------

SEED_MATERIALS = [
    # اللغات الست المعتمدة
    ("languages", "العربية — مجمع الملك سلمان العالمي", "منصة معتمدة لعلوم اللغة العربية والمعاجم الفصحى.", "https://ksaa.gov.sa/"),
    ("languages", "العربية — معجم الدوحة التاريخي", "بوابة شاملة لتاريخ وتطور الألفاظ والمعاني في لغة الضاد.", "https://www.dohadictionary.org/"),
    ("languages", "الإنجليزية — British Council", "دروس تفاعلية ومصادر قواعد واختبارات لجميع المستويات.", "https://learnenglish.britishcouncil.org/"),
    ("languages", "الإنجليزية — BBC Learning English", "دورات صوتية ومقاطع فيديو لتطوير الاستماع والمفردات.", "https://www.bbc.co.uk/learningenglish/"),
    ("languages", "التركية — Yunus Emre Enstitüsü", "البوابة الرسمية المعتمدة لتعليم اللغة التركية لغير الناطقين بها.", "https://turkce.yee.org.tr/"),
    ("languages", "التركية — TurkishClass101", "دروس صوتية ومفردات وتراكيب يومية مبسطة.", "https://www.turkishclass101.com/"),
    ("languages", "الكورية — King Sejong Institute", "مؤسسة الملك سيجونغ الرسمية لتعليم الكورية والثقافة الكورية.", "https://www.iksi.or.kr/"),
    ("languages", "الكورية — Talk To Me In Korean", "أشهر منهاج تعليمي تفاعلي لإتقان اللغة الكورية المعاصرة.", "https://talktomeinkorean.com/"),
    ("languages", "اليابانية — NHK World Japan", "دروس يومية ميسرة باللغة العربية لتعلم أساسيات اليابانية والكانجي.", "https://www.nhk.or.jp/lesson/arabic/"),
    ("languages", "اليابانية — Marugoto Online", "منهاج ياباني معتمد قائم على المحادثة والمواقف الواقعية.", "https://www.marugoto.org/"),
    ("languages", "الصينية — Confucius Institute", "بوابة معهد كونفوشيوس العالمي لتعليم لغة الماندرين وقواعدها.", "https://www.chinesecio.com/"),
    ("languages", "الصينية — HelloChinese", "منهاج متكامل لتأسيس النطق والكتابة بنظام الرموز الصينية.", "https://www.hellochinese.cc/"),
    # العلوم والطب والبرمجة
    ("library", "البرمجة — التوثيق الرسمي لـ Python", "دليل المطورين والتوثيق المكتمل لكل مكتبات وخوارزميات بايثون.", "https://docs.python.org/3/"),
    ("library", "البرمجة — MIT OpenCourseWare", "محاضرات ومناهج علوم الحاسب والذكاء الاصطناعي المجانية من MIT.", "https://ocw.mit.edu/"),
    ("library", "الأحياء — OpenStax Biology", "مرجع جامعي أمريكي معتمد ومفتوح لعلوم الأحياء والوراثة وعلم الخلية.", "https://openstax.org/details/books/biology-2e"),
    ("library", "الأحياء — NCBI Bookshelf", "مكتبة أبحاث وكتب الطب الحيوي من المعهد الوطني للصحة الأمريكي.", "https://www.ncbi.nlm.nih.gov/books/"),
    ("library", "الطب والصحة — MedlinePlus", "موسوعة طبية تثقيفية موثوقة للأمراض وعلم وظائف الأعضاء والأدوية.", "https://medlineplus.gov/"),
    ("library", "العلوم — PhET Interactive Simulations", "محاكاة تفاعلية لتجارب الفيزياء، الكيمياء، والأحياء من جامعة كولورادو.", "https://phet.colorado.edu/"),
    ("library", "الأدب — Project Gutenberg", "أكبر مستودع رقمي مجاني لأمهات الكتب والروايات العالمية الكلاسيكية.", "https://www.gutenberg.org/"),
    ("library", "الفلسفة — Stanford Encyclopedia of Philosophy", "أشمل مرجع أكاديمي مفتوح ومحكم في الفلسفة والفكر الإنساني.", "https://plato.stanford.edu/"),
    # السيرة النبوية
    ("seerah", "الرحيق المختوم — صفي الرحمن المباركفوري", "الكتاب الحائز على الجائزة الأولى في مسابقة السيرة النبوية العالمية.", "https://sunnah.com/"),
    ("seerah", "السيرة النبوية — ابن هشام", "المرجع التاريخي والوثائقي الأقدم والأشمل في تدوين وقائع السيرة العطرة.", "https://shamela.ws/"),
    ("seerah", "زاد المعاد في هدي خير العباد — ابن القيم", "مرجع فريد يستعرض فقه السيرة وهديه ﷺ في سائر شؤون الحياة.", "https://shamela.ws/"),
]

SEED_AZKAR = [
    ("الصباح", "أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير."),
    ("الصباح", "اللهم بك أصبحنا، وبك أمسينا، وبك نحيا، وبك نموت، وإليك النشور."),
    ("الصباح", "سيد الاستغفار: اللهم أنت ربي لا إله إلا أنت، خلقتني وأنا عبدك، وأنا على عهدك ووعدك ما استطعت، أعوذ بك من شر ما صنعت، أبوء لك بنعمتك عليّ، وأبوء بذنبي فاغفر لي فإنه لا يغفر الذنوب إلا أنت."),
    ("الصباح", "بسم الله الذي لا يضر مع اسمه شيء في الأرض ولا في السماء وهو السميع العليم. (3 مرات)"),
    ("الصباح", "رضيت بالله رباً، وبالإسلام ديناً، وبمحمد ﷺ نبياً ورسولاً. (3 مرات)"),
    ("الصباح", "يا حي يا قيوم برحمتك أستغيث، أصلح لي شأني كله ولا تكلني إلى نفسي طرفة عين."),
    ("المساء", "أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير."),
    ("المساء", "اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير."),
    ("المساء", "أمسينا على فطرة الإسلام وعلى كلمة الإخلاص، وعلى دين نبينا محمد ﷺ، وعلى ملة أبينا إبراهيم حنيفاً مسلماً وما كان من المشركين."),
    ("المساء", "أعوذ بكلمات الله التامات من شر ما خلق. (3 مرات)"),
    ("المساء", "اللهم ما أمسى بي من نعمة أو بأحد من خلقك فمنك وحدك لا شريك لك، فلك الحمد ولك الشكر."),
    ("النوم", "باسمك ربي وضعت جنبي وبك أرفعه، فإن أمسكت نفسي فارحمها، وإن أرسلتها فاحفظها بما تحفظ به عبادك الصالحين."),
    ("النوم", "اللهم قني عذابك يوم تبعث عبادك. (3 مرات)"),
    ("النوم", "قراءة آية الكرسي، وآخر آيتين من سورة البقرة، والمعوذتين والإخلاص ثلاثاً."),
    ("بعد الصلاة", "أستغفر الله، أستغفر الله، أستغفر الله. اللهم أنت السلام ومنك السلام، تباركت يا ذا الجلال والإكرام."),
    ("بعد الصلاة", "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير، اللهم لا مانع لما أعطيت، ولا معطي لما منعت، ولا ينفع ذا الجد منك الجد."),
    ("بعد الصلاة", "تسبيح 33، تحميد 33، تكبير 33، والتمام مائة: لا إله إلا الله وحده لا شريك له له الملك وله الحمد وهو على كل شيء قدير."),
    ("أدعية وتفريج الكرب", "لا إله إلا أنت سبحانك إني كنت من الظالمين."),
    ("أدعية وتفريج الكرب", "اللهم إني أعوذ بك من الهم والحزن، والعجز والكسل، والبخل والجبن، وضلع الدين وغلبة الرجال."),
    ("أدعية وتفريج الكرب", "يا مقلب القلوب ثبت قلبي على دينك."),
    ("أدعية وتفريج الكرب", "ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار."),
]

TASBEEH_PRESETS = [
    "سبحان الله وبحمده",
    "سبحان الله العظيم",
    "الحمد لله رب العالمين",
    "لا إله إلا الله وحده لا شريك له",
    "الله أكبر كبيراً",
    "لا حول ولا قوة إلا بالله العلي العظيم",
    "أستغفر الله وأتوب إليه",
    "اللهم صلِّ وسلم على نبينا محمد",
    "سبحان الله والحمد لله ولا إله إلا الله والله أكبر",
    "حسبي الله ونعم الوكيل",
]

QUOTES = [
    ("«إنما المجد لمن لا يبتغي المجد، وإنما الفخر لمن أصلح شأن نفسه وعاش عزيزاً مستغنياً.»", "فلسفة الكرامة والاستغناء"),
    ("«لا تطلب أن تحدث الأمور كما تشتهي، بل ارغب في أن تحدث كما هي حادثة بالفعل؛ حينها ستمضي حياتك في سلام وسكينة.»", "إبيكتيتوس — الفلسفة الرواقية"),
    ("«أقوى الناس ذاك الذي يقدر على قيادة رغباته وهزيمة عاداته السيئة.»", "أرسطو"),
    ("«العقل لا يُملأ كما يُملأ الوعاء، بل يُشعل كما تُشعل الشعلة لتستنير بنور الفهم والبحث.»", "بلوتارخ"),
    ("«لا تمشِ أبداً في الطريق المرسوم، لأنه يقودك فقط إلى حيث وصل الآخرون.»", "ألكسندر غراهام بيل"),
    ("«الكرامة ألا نعيش عالة على مشاعر أحد، ولا نستجدي تقديراً من عابر، بل نبني قلاعنا بأيدينا.»", "أدب وعزة النفس"),
    ("«الذي يملك سبباً كبيراً يعيش من أجله، يمكنه أن يتحمل في سبيله أي صعاب تقريباً.»", "فريدريك نيتشه"),
    ("«توقّع الكثير من نفسك والقليل من الآخرين، فهكذا تدخر على نفسك الكثير من الخيبات.»", "كونفوشيوس"),
    ("«ما تتركه خلفك في قلوب الناس وعقولهم أثمن بكثير مما تتركه مسجلاً على الحجر.»", "بريكليس"),
    ("«إذا لم تستطع أن تفعل أشياء عظيمة، فافعل الأشياء الصغيرة بطريقة عظيمة جداً.»", "نابليون هيل"),
]

QUIZ_BANK = [
    ("كم عدد سور القرآن الكريم؟", ["112 سورة", "113 سورة", "114 سورة", "115 سورة"], 2, "عدد سور القرآن الكريم 114 سورة بالإجماع والتواتر."),
    ("ما هي السورة التي تُلقب بـ 'قلب القرآن'؟", ["الرحمن", "يس", "الواقعة", "الملك"], 1, "سورة يس عُرفت بلقب قلب القرآن الكريم."),
    ("ما أول سورة نزلت كاملة في القرآن الكريم؟", ["الفاتحة", "العلق", "المدثر", "الإخلاص"], 0, "سورة الفاتحة هي أول سورة نزلت متكاملة الجملة."),
    ("أي لغة من اللغات التالية تُعد أقدم اللغات الحية انتشاراً واستخداماً متصلاً؟", ["الصينية", "العربية", "اليونانية", "اللاتينية"], 0, "اللغة الصينية المكتوبة من أقدم اللغات المتصلة تاريخياً حتى عصرنا."),
    ("ما هو العضو الأكثر استهلاكاً للأكسجين والطاقة في جسم الإنسان؟", ["القلب", "الدماغ", "الكبد", "الكليتان"], 1, "يستهلك الدماغ نحو 20% من إجمالي أكسجين وطاقة الجسم رغم ضآلة وزنه."),
    ("من هو مؤلف كتاب 'الرحيق المختوم' الشهير في السيرة النبوية؟", ["صفي الرحمن المباركفوري", "ابن كثير", "ابن الأثير", "الإمام الطبري"], 0, "الشيخ صفي الرحمن المباركفوري ألّفه وفاز بالجائزة الأولى لرابطة العالم الإسلامي."),
    ("في أي عام هجري وقعت غزوة بدر الكبرى؟", ["السنة الأولى", "السنة الثانية", "السنة الثالثة", "السنة الرابعة"], 1, "وقعت غزوة بدر الكبرى في 17 رمضان في السنة الثانية من الهجرة النبوية."),
    ("ما هي لغة البرمجة التي طورها 'خايدو فان روسم' في أوائل التسعينات؟", ["جافا", "بايثون (Python)", "سي بلس بلس", "روبي"], 1, "طوّر غايدو فان روسوم لغة بايثون لتكون قوية وواضحة وسهلة القراءة."),
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
            user_id INTEGER, item_type TEXT, item_id TEXT, title TEXT DEFAULT '',
            PRIMARY KEY(user_id, item_type, item_id)
        );
        CREATE TABLE IF NOT EXISTS azkar(
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, text TEXT
        );
        CREATE TABLE IF NOT EXISTS tasbeeh(
            user_id INTEGER PRIMARY KEY, preset_index INTEGER DEFAULT 0, count INTEGER DEFAULT 0
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
        """)

        # غرس البيانات الأساسية
        if con.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0:
            now = int(time.time())
            con.executemany(
                "INSERT INTO materials(category,title,body,url,created_at) VALUES(?,?,?,?,?)",
                [(c, t, b, u, now) for c, t, b, u in SEED_MATERIALS],
            )
        if con.execute("SELECT COUNT(*) FROM azkar").fetchone()[0] == 0:
            con.executemany("INSERT INTO azkar(category,text) VALUES(?,?)", SEED_AZKAR)

        defaults = {
            "maintenance": "0",
            "force_sub": "1",
            "welcome_ar": "أهلًا وسهلاً بك في منصة Dua Space 🌙✨\nبوابتك المعرفية الشاملة للقرآن، الأذكار، العلوم، والإنتاجية.",
        }
        for key, value in defaults.items():
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))


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


def hit(category):
    with db() as con:
        con.execute(
            "INSERT INTO visits(category,count) VALUES(?,1) "
            "ON CONFLICT(category) DO UPDATE SET count=count+1",
            (category,),
        )


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


# -------------------- فحص الاشتراك الإجباري الصارم --------------------

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if setting("force_sub") != "1" or is_admin(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            return False
        return True
    except Exception as e:
        log.warning(f"تعذر التحقق من اشتراك العضو (تأكدي من رفع البوت مشرفاً بالقناة): {e}")
        # إذا تعذر التحقق لعدم رفع البوت مشرفاً، نسمح للأدمن فقط
        return is_admin(user_id)


def sub_required_markup():
    channel_clean = CHANNEL_ID.replace("@", "")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 اشترك في قناة Dua Space", url=f"https://t.me/{channel_clean}")],
        [InlineKeyboardButton("✅ تأكيد الاشتراك والمتابعة", callback_data="check_sub_again")],
    ])


# -------------------- القوائم والواجهات --------------------

def main_menu():
    buttons = [
        [InlineKeyboardButton("📖 القرآن الكريم (114 سورة)", callback_data="q:0"),
         InlineKeyboardButton("🤲 الأذكار والسبحة", callback_data="azkar")],
        [InlineKeyboardButton("📚 المكتبة والمعارف", callback_data="cats"),
         InlineKeyboardButton("🎨 خدمات التصميم", callback_data="design")],
        [InlineKeyboardButton("📜 درر وحكم واقتباسات", callback_data="quotes"),
         InlineKeyboardButton("⏱️ مؤقت التركيز للمذاكرة", callback_data="pomodoro")],
        [InlineKeyboardButton("🧠 تحدي المسابقات", callback_data="quiz"),
         InlineKeyboardButton("⭐ محفوظاتي المفضلة", callback_data="favorites")],
        [InlineKeyboardButton("🔎 محرك البحث السريع", callback_data="search"),
         InlineKeyboardButton("✉️ الدعم والتواصل", callback_data="support")],
    ]
    return InlineKeyboardMarkup(buttons)


async def send_home(update, context, edit=False):
    user = update.effective_user
    text = setting("welcome_ar")
    if setting("maintenance") == "1" and not is_admin(user.id):
        text = "🛠 البوت حالياً في وضع التحديث والصيانة. نعود قريباً بإذن الله 🌿"
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu())
    else:
        await update.effective_message.reply_text(text, reply_markup=main_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)

    if not await check_subscription(user.id, context):
        await update.message.reply_text(
            f"مرحباً بكِ في <b>Dua Space</b> 🌙🌿\n\n"
            f"للوصول إلى جميع المصادر، المحاضرات، والتلاوات، يُرجى الانضمام إلى قناتنا أولاً:\n"
            f"👉 <b>{CHANNEL_ID}</b>\n\nثم اضغطي على زر التأكيد بالأسفل:",
            parse_mode="HTML",
            reply_markup=sub_required_markup(),
        )
        return
    await send_home(update, context)


def page_keyboard(prefix, page, total):
    last = max(0, (total - 1) // PAGE_SIZE)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{prefix}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1} / {last+1}", callback_data="noop"))
    if page < last:
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{prefix}:{page+1}"))
    return [nav, [InlineKeyboardButton("🏠 العودة للقائمة", callback_data="home")]]


# -------------------- قسم القرآن الكريم الصوتي --------------------

async def show_quran(query, page):
    total = len(SURAHS)
    start_i = page * PAGE_SIZE
    rows = []
    for i in range(start_i, min(start_i + PAGE_SIZE, total)):
        ar, verses = SURAHS[i]
        rows.append([
            InlineKeyboardButton(f"{i+1:03d}. سورة {ar} ({verses} آية)", callback_data=f"qr:{i+1}"),
            InlineKeyboardButton("⭐", callback_data=f"favadd:s:{i+1}:{ar}"),
        ])
    rows.extend(page_keyboard("q", page, total))
    await query.edit_message_text(
        "📖 <b>فهرس سور القرآن الكريم (114 سورة كاملة)</b>\n"
        "اختر السورة للاستماع الفوري إليها أو أضفها للمفضلة:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def send_surah_audio(query, number, context):
    ar_name, verses = SURAHS[number - 1]
    await query.answer(f"جارٍ إرسال تلاوة سورة {ar_name}…")
    
    audio_url = f"https://server8.mp3quran.net/afs/{number:03d}.mp3"
    quran_reader_url = f"https://quran.com/{number}"

    caption = (
        f"📖 <b>سورة {html.escape(ar_name)}</b>\n"
        f"• عدد الآيات: {verses} آية\n"
        f"• القارئ: مشاري بن راشد العفاسي 🎧\n\n"
        f"🔗 <a href='{quran_reader_url}'>اضغط هنا لقراءة السورة بالرسم العثماني المعتمد</a>"
    )
    
    try:
        await context.bot.send_audio(
            chat_id=query.message.chat_id,
            audio=audio_url,
            title=f"سورة {ar_name}",
            performer="مشاري العفاسي",
            caption=caption,
            parse_mode="HTML",
        )
    except Exception:
        backup_audio = f"https://cdn.islamic.network/quran/audio-surah/128/ar.alafasy/{number}.mp3"
        await context.bot.send_audio(
            chat_id=query.message.chat_id,
            audio=backup_audio,
            title=f"سورة {ar_name}",
            performer="مشاري العفاسي",
            caption=caption,
            parse_mode="HTML",
        )


# -------------------- قسم الأذكار والسبحة الرقمية --------------------

async def show_azkar_menu(query):
    rows = [
        [InlineKeyboardButton("🌅 أذكار الصباح", callback_data="az:الصباح"),
         InlineKeyboardButton("🌆 أذكار المساء", callback_data="az:المساء")],
        [InlineKeyboardButton("🌙 أذكار النوم", callback_data="az:النوم"),
         InlineKeyboardButton("🕌 بعد الصلاة المكتوبة", callback_data="az:بعد الصلاة")],
        [InlineKeyboardButton("🤲 تفريج الكرب وجوامع الدعاء", callback_data="az:أدعية وتفريج الكرب")],
        [InlineKeyboardButton("📿 السبحة الإلكترونية الذكية", callback_data="tasbeeh")],
        [InlineKeyboardButton("🏠 العودة للقائمة", callback_data="home")],
    ]
    await query.edit_message_text(
        "🤲 <b>واحة الأذكار والسبحة الرقمية</b>\nاختر الورد الذي تريده للبدء:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_azkar_content(query, category):
    with db() as con:
        rows = con.execute("SELECT text FROM azkar WHERE category=?", (category,)).fetchall()
    
    items_text = "\n\n──────────────────\n\n".join(f"• {html.escape(r['text'])}" for r in rows)
    if not items_text:
        items_text = "لا توجد أذكار مضافة في هذا القسم حالياً."

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ حفظ القسم للمفضلة", callback_data=f"favadd:az:{category}:{category}")],
        [InlineKeyboardButton("↩️ رجوع لقائمة الأذكار", callback_data="azkar")],
    ])
    await query.edit_message_text(
        f"🤲 <b>{html.escape(category)}</b>\n\n{items_text}",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def show_tasbeeh(query, user_id):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO tasbeeh(user_id,preset_index,count) VALUES(?,0,0)", (user_id,))
        row = con.execute("SELECT preset_index, count FROM tasbeeh WHERE user_id=?", (user_id,)).fetchone()
    
    idx = row["preset_index"] % len(TASBEEH_PRESETS)
    count = row["count"]
    current_phrase = TASBEEH_PRESETS[idx]

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📿 تسبيح (+1)  [ {count} ]", callback_data="tas:+")],
        [InlineKeyboardButton("🔁 الذكر التالي", callback_data="tas:next"),
         InlineKeyboardButton("🔄 تصفير العداد", callback_data="tas:0")],
        [InlineKeyboardButton("↩️ رجوع للأذكار", callback_data="azkar")],
    ])

    await query.edit_message_text(
        f"📿 <b>السبحة الإلكترونية المباركة</b>\n\n"
        f"الذكر الحالي:\n<b>« {current_phrase} »</b>\n\n"
        f"مجموع التسبيحات: <b>{count}</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )


# -------------------- قسم خدمات التصميم الفاخر --------------------

def design_menu():
    rows = [
        [InlineKeyboardButton("🎨 تصميم الهويات والشعارات (Logos)", callback_data="req_design:شعار وهوية بصرية")],
        [InlineKeyboardButton("📱 بوستات وإعلانات سوشيال ميديا", callback_data="req_design:تصاميم سوشيال ميديا")],
        [InlineKeyboardButton("📄 تصاميم المطبوعات والبروشورات", callback_data="req_design:مطبوعات وبروشور")],
        [InlineKeyboardButton("💻 تصميم واجهات المستخدم (UI/UX)", callback_data="req_design:واجهات UI/UX")],
        [InlineKeyboardButton("🖼️ تعديل ومونتاج ودمج الصور الاحترافي", callback_data="req_design:تعديل صور وموكاب")],
        [InlineKeyboardButton("💬 تواصل مباشر مع المصممة", url="https://t.me/elmore_citizen")],
        [InlineKeyboardButton("🏠 العودة للقائمة", callback_data="home")],
    ]
    return InlineKeyboardMarkup(rows)


async def show_design(query):
    text = (
        "🎨 <b>استوديو تصميم Dua Space</b> ✨\n\n"
        "نصنع لك تصاميم بصرية تجمع بين الإبداع والهوية المميزة.\n\n"
        "<b>مجالات العمل:</b>\n"
        "• ابتكار الشعارات والهويات التجارية الكاملة.\n"
        "• تصاميم السوشيال ميديا الإعلانية.\n"
        "• تصميم الكتب والمجلات والمطبوعات.\n"
        "• واجهات الاستخدام (UI/UX).\n\n"
        "👇 <i>اختاري الخدمة لتسجيل المواصفات، أو تواصلي مباشرة للاتفاق على التفاصيل والسعر المناسبين.</i>"
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=design_menu())


# -------------------- قسم الاقتباسات ودرر الفلسفة --------------------

async def show_quotes(query):
    idx = random.randint(0, len(QUOTES) - 1)
    quote, author = QUOTES[idx]
    short_title = quote[:25] + "..."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 اقتباس آخر", callback_data="quotes:next")],
        [InlineKeyboardButton("⭐ حفظ للاقتباسات المفضلة", callback_data=f"favadd:q:{idx}:{short_title}")],
        [InlineKeyboardButton("🏠 العودة للقائمة", callback_data="home")],
    ])
    await query.edit_message_text(
        f"📜 <b>درر وحكم مختارة</b>\n\n"
        f"<i>{quote}</i>\n\n"
        f"— <b>{author}</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )


# -------------------- قسم المكتبة والمراجع --------------------

async def show_categories(query):
    rows = [
        [InlineKeyboardButton("🌍 اللغات الست العالمية", callback_data="m:languages:0")],
        [InlineKeyboardButton("🔬 العلوم الطبية والأحياء والتقنية", callback_data="m:library:0")],
        [InlineKeyboardButton("🕌 السيرة النبوية والمراجع الإسلامية", callback_data="m:seerah:0")],
        [InlineKeyboardButton("🏠 العودة للقائمة", callback_data="home")],
    ]
    await query.edit_message_text(
        "📚 <b>مكتبة المعارف الرقمية</b>\nاختر الباب العلمي الذي تبحث عن مصادره:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_materials(query, category, page):
    with db() as con:
        items = con.execute("SELECT * FROM materials WHERE category=? ORDER BY id DESC", (category,)).fetchall()
    
    titles = {
        "languages": "بوابات اللغات الست المعتمدة",
        "library": "المراجع العلمية والبرمجية والأدب",
        "seerah": "السيرة النبوية والتاريخ العطر",
    }
    
    rows = []
    slice_items = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    for item in slice_items:
        clean_title = item["title"][:40]
        rows.append([
            InlineKeyboardButton(clean_title, callback_data=f"mat:{item['id']}"),
            InlineKeyboardButton("⭐", callback_data=f"favadd:m:{item['id']}:{clean_title}"),
        ])
    rows.extend(page_keyboard(f"m:{category}", page, len(items)))
    await query.edit_message_text(
        f"📚 <b>{html.escape(titles.get(category, category))}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# -------------------- قسم المفضلة المصحح بالكامل --------------------

async def show_favorites(query, user_id):
    with db() as con:
        favs = con.execute(
            "SELECT item_type, item_id, title FROM favorites WHERE user_id=? ORDER BY rowid DESC LIMIT 30",
            (user_id,),
        ).fetchall()
    
    if not favs:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 العودة للقائمة", callback_data="home")]])
        await query.edit_message_text("⭐ <b>محفوظاتك المفضلة فارغة حالياً.</b>\nيمكنك حفظ السور، الأذكار، والمواد بالضغط على علامة النجمة ⭐.", reply_markup=kb, parse_mode="HTML")
        return

    rows = []
    for f in favs:
        t = f["item_type"]
        iid = f["item_id"]
        title = f["title"] or "عنصر محفوظ"
        
        if t == "s":
            rows.append([InlineKeyboardButton(f"📖 سورة {title}", callback_data=f"qr:{iid}")])
        elif t == "m":
            rows.append([InlineKeyboardButton(f"📚 {title}", callback_data=f"mat:{iid}")])
        elif t == "az":
            rows.append([InlineKeyboardButton(f"🤲 {title}", callback_data=f"az:{iid}")])
        elif t == "q":
            rows.append([InlineKeyboardButton(f"📜 اقتباس: {title}", callback_data="quotes")])

    rows.append([InlineKeyboardButton("🏠 العودة للقائمة", callback_data="home")])
    await query.edit_message_text("⭐ <b>قائمة محفوظاتي المفضلة</b>\nاضغط على أي عنصر لفتحه فوراً:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


# -------------------- لوحة تحكم الإدارة الكاملة --------------------

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات البوت الحية", callback_data="admin:stats"),
         InlineKeyboardButton("📢 نشر تذكير بالقناة (@DuaSpace1)", callback_data="admin:post_channel")],
        [InlineKeyboardButton("🔒 تفعيل/تعطيل الاشتراك الإجباري", callback_data="admin:subscription"),
         InlineKeyboardButton("🛠 تفعيل/تعطيل وضع الصيانة", callback_data="admin:maintenance")],
        [InlineKeyboardButton("📢 إذاعة للمشتركين (Broadcast)", callback_data="admin:broadcast"),
         InlineKeyboardButton("🗄 سحب نسخة احتياطية للبيانات", callback_data="admin:do_backup")],
        [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="home")],
    ])


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = (
        "🛡️ <b>لوحة القيادة والتحكم الشاملة — Dua Space</b>\n\n"
        "أهلاً بكِ في مركز إدارة البوت ومحتواه بالكامل:\n\n"
        "<b>أوامر الإدارة المباشرة:</b>\n"
        "• <code>/addmaterial القسم|العنوان</code> — ثم أرسلي نصاً أو ملف PDF/صوت/صورة.\n"
        "• <code>/delmaterial الرقم</code> — لحذف مادة من المكتبة.\n"
        "• <code>/addzekr القسم|النص</code> — لإضافة ذكر جديد.\n"
        "• <code>/delzekr الرقم</code> — لحذف ذكر.\n"
        "• <code>/post النص</code> — لنشر تذكير فوري في القناة.\n"
        "• <code>/broadcast النص</code> — لإرسال إذاعة فورية لجميع مستخدمي البوت.\n"
        "• <code>/reply رقم_التذكرة نص الرد</code> — للرد على استفسار مستخدم.\n"
        "• <code>/backup</code> — لتحميل ملف قاعدة البيانات مباشرة."
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_keyboard())


# -------------------- معالجة النصوص والملفات والبحث --------------------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    state = context.user_data.get("state")

    # البحث السريع
    if state == "search":
        context.user_data.pop("state", None)
        query = text.strip()
        results = []
        
        # البحث في القرآن
        matched_surahs = [f"• سورة {s[0]} (رقم {i+1})" for i, s in enumerate(SURAHS) if query in s[0]]
        if matched_surahs:
            results.append("📖 <b>في القرآن الكريم:</b>\n" + "\n".join(matched_surahs[:5]))
            
        # البحث في المكتبة
        with db() as con:
            mats = con.execute("SELECT id, title, category FROM materials WHERE title LIKE ? OR body LIKE ? LIMIT 6",
                               (f"%{query}%", f"%{query}%")).fetchall()
        if mats:
            results.append("📚 <b>في المكتبة والمراجع:</b>\n" + "\n".join([f"• {m['title']} (/mat_{m['id']})" for m in mats]))

        reply_msg = "\n\n".join(results) if results else "لم نعثر على نتائج مطابقة لكلمة البحث."
        await update.message.reply_text(f"🔎 <b>نتائج البحث عن:</b> {html.escape(query)}\n\n{reply_msg}", parse_mode="HTML")
        return

    # استلام تفاصيل التصميم
    if state == "design_order":
        category = context.user_data.pop("design_type", "تصميم عام")
        context.user_data.pop("state", None)
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🎨 <b>طلب تصميم جديد!</b>\n\n"
                    f"• <b>النوع:</b> {html.escape(category)}\n"
                    f"• <b>العميل:</b> {html.escape(user.full_name)} (ID: <code>{user.id}</code>)\n"
                    f"• <b>المعرف:</b> @{user.username or 'بدون معرف'}\n\n"
                    f"<b>التفاصيل:</b>\n{html.escape(text)}",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await update.message.reply_text("✅ استلمنا تفاصيل طلبك بنجاح! سيتم التواصل معكِ قريباً لمناقشة التفاصيل والاتفاق 🌿")
        return

    # تذاكر الدعم
    if state == "support":
        context.user_data.pop("state", None)
        with db() as con:
            cur = con.execute("INSERT INTO tickets(user_id,message,created_at) VALUES(?,?,?)",
                              (user.id, text, int(time.time())))
            ticket_id = cur.lastrowid
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"✉️ <b>تذكرة دعم جديدة #{ticket_id}</b>\nمن: {user.full_name} (<code>{user.id}</code>)\n\n"
                    f"{html.escape(text)}\n\nللرد: <code>/reply {ticket_id} نص الرد</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await update.message.reply_text(f"تم إرسال رسالتك للإدارة بنجاح. رقم تذكرتك: #{ticket_id}")
        return

    # إضافة مادة كأدمن
    if state == "admin_upload" and is_admin(user.id):
        cat, title = context.user_data.get("upload_meta", ("library", "مادة جديدة"))
        is_url = text.startswith(("http://", "https://"))
        with db() as con:
            con.execute("INSERT INTO materials(category,title,body,url,created_at) VALUES(?,?,?,?,?)",
                        (cat, title, text, text if is_url else "", int(time.time())))
        context.user_data.pop("state", None)
        context.user_data.pop("upload_meta", None)
        await update.message.reply_text("✅ تم حفظ المادة بنجاح في القسم المخصص.")
        return

    if is_admin(user.id) and state == "post_to_channel":
        context.user_data.pop("state", None)
        try:
            await context.bot.send_message(CHANNEL_ID, text)
            await update.message.reply_text("✅ تم نشر التذكير في القناة بنجاح.")
        except Exception as e:
            await update.message.reply_text(f"❌ تعذر النشر في القناة: {e}")
        return

    await update.message.reply_text("استخدم الأزرار أدناه أو أرسل /start لفتح القائمة الرئيسية.")


async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) or context.user_data.get("state") != "admin_upload":
        return
    cat, title = context.user_data.get("upload_meta", ("library", "ملف مرفوع"))
    msg = update.message
    file_id, file_type = "", ""
    if msg.document:
        file_id, file_type = msg.document.file_id, "document"
    elif msg.audio:
        file_id, file_type = msg.audio.file_id, "audio"
    elif msg.photo:
        file_id, file_type = msg.photo[-1].file_id, "photo"
    elif msg.video:
        file_id, file_type = msg.video.file_id, "video"
        
    if not file_id:
        return
    with db() as con:
        con.execute(
            "INSERT INTO materials(category,title,body,file_id,file_type,created_at) VALUES(?,?,?,?,?,?)",
            (cat, title, msg.caption or "", file_id, file_type, int(time.time())),
        )
    context.user_data.pop("state", None)
    context.user_data.pop("upload_meta", None)
    await msg.reply_text("✅ تم استلام الملف وإتاحته كملف قابل للتحميل داخل القسم.")


# -------------------- التفاعلات (Callbacks) --------------------

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "noop":
        return
    if data == "check_sub_again":
        if await check_subscription(user_id, context):
            await query.edit_message_text("✅ تم التحقق من الاشتراك بنجاح! أهلاً بكِ في Dua Space 🌙")
            await send_home(update, context)
        else:
            await query.answer("لم يتم التحقق من اشتراكك في القناة بعد! اشترك ثم اضغط تأكيد.", show_alert=True)
    elif data == "home":
        await send_home(update, context, edit=True)
    elif data.startswith("q:"):
        await show_quran(query, int(data.split(":")[1]))
    elif data.startswith("qr:"):
        await send_surah_audio(query, int(data.split(":")[1]), context)
    elif data == "azkar":
        hit("azkar")
        await show_azkar_menu(query)
    elif data.startswith("az:"):
        await show_azkar_content(query, data.split(":", 1)[1])
    elif data == "tasbeeh":
        await show_tasbeeh(query, user_id)
    elif data == "tas:+":
        with db() as con:
            con.execute("UPDATE tasbeeh SET count=count+1 WHERE user_id=?", (user_id,))
        await show_tasbeeh(query, user_id)
    elif data == "tas:0":
        with db() as con:
            con.execute("UPDATE tasbeeh SET count=0 WHERE user_id=?", (user_id,))
        await show_tasbeeh(query, user_id)
    elif data == "tas:next":
        with db() as con:
            con.execute("UPDATE tasbeeh SET preset_index=preset_index+1, count=0 WHERE user_id=?", (user_id,))
        await show_tasbeeh(query, user_id)
    elif data == "design":
        await show_design(query)
    elif data.startswith("req_design:"):
        design_name = data.split(":", 1)[1]
        context.user_data["state"] = "design_order"
        context.user_data["design_type"] = design_name
        await query.message.reply_text(
            f"اخترتِ: <b>{design_name}</b>\n\nأرسلي الآن وصفاً لما تحتاجينه وأي تفاصيل ترغبين بها وسنتواصل معكِ مباشرة للتنفيذ ✨",
            parse_mode="HTML",
        )
    elif data == "quotes" or data == "quotes:next":
        await show_quotes(query)
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
            await query.message.reply_text("المادة غير متوفرة.")
            return
        caption = f"📚 <b>{html.escape(item['title'])}</b>\n\n{html.escape(item['body'] or '')}"
        if item["url"]:
            caption += f"\n\n🔗 {html.escape(item['url'])}"
        if item["file_id"]:
            m_funcs = {
                "document": context.bot.send_document,
                "audio": context.bot.send_audio,
                "photo": context.bot.send_photo,
                "video": context.bot.send_video,
            }
            fn = m_funcs.get(item["file_type"], context.bot.send_document)
            await fn(query.message.chat_id, item["file_id"], caption=item["title"])
        await query.message.reply_text(
            caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ حفظ للمفضلة", callback_data=f"favadd:m:{item_id}:{item['title'][:30]}")],
                [InlineKeyboardButton("↩️ رجوع", callback_data=f"m:{item['category']}:0")],
            ]),
            disable_web_page_preview=True,
        )
    elif data.startswith("favadd:"):
        parts = data.split(":", 3)
        itype = parts[1]
        iid = parts[2]
        ititle = parts[3] if len(parts) > 3 else "عنصر محفوظ"
        with db() as con:
            con.execute("INSERT OR REPLACE INTO favorites(user_id,item_type,item_id,title) VALUES(?,?,?,?)",
                        (user_id, itype, iid, ititle))
        await query.answer("تمت الإضافة للمفضلة بنجاح ⭐", show_alert=True)
    elif data == "favorites":
        await show_favorites(query, user_id)
    elif data == "search":
        context.user_data["state"] = "search"
        await query.message.reply_text("🔎 أرسلي الكلمة التي تبحثين عنها في القرآن أو المكتبة:")
    elif data == "support":
        context.user_data["state"] = "support"
        await query.message.reply_text("✉️ اكتبي استفسارك أو رسالتك وسنرد عليكِ فوراً:")
    elif data == "quiz":
        q, options, ans, exp = random.choice(QUIZ_BANK)
        context.user_data["quiz_data"] = (ans, exp)
        btns = [[InlineKeyboardButton(opt, callback_data=f"qz:{i}")] for i, opt in enumerate(options)]
        btns.append([InlineKeyboardButton("🏠 القائمة", callback_data="home")])
        await query.message.reply_text(f"🧠 <b>سؤال التحدي:</b>\n\n{q}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
    elif data.startswith("qz:"):
        choice = int(data.split(":")[1])
        ans, exp = context.user_data.get("quiz_data", (-1, ""))
        res = "✅ إجابة صحيحة وممتازة!" if choice == ans else "❌ للأسف إجابة غير صحيحة."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("سؤال آخر 🔄", callback_data="quiz")],
            [InlineKeyboardButton("🏠 القائمة", callback_data="home")],
        ])
        await query.message.reply_text(f"{res}\n\n💡 <b>التوضيح:</b>\n{exp}", parse_mode="HTML", reply_markup=kb)
    elif data == "pomodoro":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("25 دقيقة تركيز", callback_data="pom:25"),
             InlineKeyboardButton("50 دقيقة تركيز عميق", callback_data="pom:50")],
            [InlineKeyboardButton("90 دقيقة ماراتون دراسي", callback_data="pom:90")],
            [InlineKeyboardButton("🏠 القائمة", callback_data="home")],
        ])
        await query.edit_message_text("⏱️ <b>مؤقت الإنتاجية والمذاكرة (Pomodoro)</b>\nاختر مدة الجلسة:", reply_markup=kb)
    elif data.startswith("pom:"):
        mins = int(data.split(":")[1])
        if context.job_queue:
            context.job_queue.run_once(pomodoro_done, when=mins * 60, chat_id=query.message.chat_id)
            await query.message.reply_text(f"بدأ مؤقت التركيز لمدة {mins} دقيقة! أبعدي المشتتات وبالتوفيق في دراستكِ 🌿")
        else:
            await query.message.reply_text(f"تم ضبط المنبه التقديري لجلسة {mins} دقيقة.")
    # لوحة الأدمن
    elif data.startswith("admin:") and is_admin(user_id):
        act = data.split(":")[1]
        if act == "stats":
            with db() as con:
                u_cnt = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                m_cnt = con.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                t_cnt = con.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
            await query.message.reply_text(f"📊 <b>إحصائيات المنصة:</b>\n• المستخدمون: {u_cnt}\n• المواد والكتب: {m_cnt}\n• تذاكر قيد الرد: {t_cnt}", parse_mode="HTML")
        elif act == "subscription":
            cur = setting("force_sub", "1")
            new_val = "0" if cur == "1" else "1"
            set_setting("force_sub", new_val)
            await query.message.reply_text(f"الاشتراك الإجباري بالقناة: {'مفعّل ✅' if new_val == '1' else 'معطّل ❌'}")
        elif act == "maintenance":
            cur = setting("maintenance", "0")
            new_val = "0" if cur == "1" else "1"
            set_setting("maintenance", new_val)
            await query.message.reply_text(f"وضع الصيانة: {'مفعّل 🛠' if new_val == '1' else 'معطّل ✅'}")
        elif act == "post_channel":
            context.user_data["state"] = "post_to_channel"
            await query.message.reply_text("أرسلي الآن المنشور أو الذكر الذي تريدين نشره فوراً في القناة:")
        elif act == "do_backup":
            if DB_PATH.exists():
                with DB_PATH.open("rb") as f:
                    await query.message.reply_document(document=f, filename=DB_PATH.name, caption="🗄 نسخة احتياطية فورية لقاعدة البيانات.")


async def pomodoro_done(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(context.job.chat_id, "⏰ <b>انتهت جلسة التركيز المحددة بنجاح!</b>\nخذي استراحة قصيرة لتجديد نشاطكِ 🌿", parse_mode="HTML")
    except Exception:
        pass


# -------------------- أوامر الإدارة المباشرة --------------------

async def add_material_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    raw = " ".join(context.args).strip()
    if "|" not in raw:
        await update.message.reply_text("الصيغة: <code>/addmaterial languages|عنوان المادة</code>", parse_mode="HTML")
        return
    cat, title = [x.strip() for x in raw.split("|", 1)]
    context.user_data["state"] = "admin_upload"
    context.user_data["upload_meta"] = (cat, title)
    await update.message.reply_text(f"تم تهيئة قسم ({cat}). أرسلي الآن الرابط أو الملف (PDF/صوت/صورة) لحفظه فوراً.")


async def del_material_cmd(update, context):
    if not is_admin(update.effective_user.id) or not context.args:
        await update.message.reply_text("الصيغة: <code>/delmaterial ID</code>", parse_mode="HTML")
        return
    try:
        mid = int(context.args[0])
        with db() as con:
            con.execute("DELETE FROM materials WHERE id=?", (mid,))
        await update.message.reply_text(f"✅ تم حذف المادة #{mid} بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")


async def add_zekr_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    raw = " ".join(context.args).strip()
    if "|" not in raw:
        await update.message.reply_text("الصيغة: <code>/addzekr الصباح|نص الذكر</code>", parse_mode="HTML")
        return
    cat, text = [x.strip() for x in raw.split("|", 1)]
    with db() as con:
        con.execute("INSERT INTO azkar(category,text) VALUES(?,?)", (cat, text))
    await update.message.reply_text(f"✅ تمت إضافة الذكر بنجاح لقسم ({cat}).")


async def del_zekr_cmd(update, context):
    if not is_admin(update.effective_user.id) or not context.args:
        await update.message.reply_text("الصيغة: <code>/delzekr ID</code>", parse_mode="HTML")
        return
    try:
        zid = int(context.args[0])
        with db() as con:
            con.execute("DELETE FROM azkar WHERE id=?", (zid,))
        await update.message.reply_text(f"✅ تم حذف الذكر #{zid} بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")


async def post_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("الصيغة: <code>/post نص التذكير</code>", parse_mode="HTML")
        return
    try:
        await context.bot.send_message(CHANNEL_ID, text)
        await update.message.reply_text("✅ تم النشر في القناة بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ تعذر النشر: {e}")


async def broadcast_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("الصيغة: <code>/broadcast نص الرسالة</code>", parse_mode="HTML")
        return
    with db() as con:
        users = con.execute("SELECT user_id FROM users").fetchall()
    count = 0
    for u in users:
        try:
            await context.bot.send_message(u["user_id"], text)
            count += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
    await update.message.reply_text(f"تم إرسال الإذاعة بنجاح إلى {count} مستخدم.")


async def reply_cmd(update, context):
    if not is_admin(update.effective_user.id) or len(context.args) < 2:
        return
    try:
        tid = int(context.args[0])
    except ValueError:
        return
    ans = " ".join(context.args[1:])
    with db() as con:
        row = con.execute("SELECT user_id FROM tickets WHERE id=?", (tid,)).fetchone()
        if row:
            con.execute("UPDATE tickets SET status='answered' WHERE id=?", (tid,))
    if row:
        await context.bot.send_message(row["user_id"], f"💬 <b>رد الإدارة على استفسارك #{tid}:</b>\n\n{ans}", parse_mode="HTML")
        await update.message.reply_text("تم إرسال الرد للعميل.")


async def backup_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    if DB_PATH.exists():
        with DB_PATH.open("rb") as f:
            await update.message.reply_document(document=f, filename=DB_PATH.name, caption="🗄 نسخة احتياطية لقاعدة البيانات.")


# -------------------- خادم ويب Render (Health Server) --------------------

async def health(_req):
    return web.json_response({"status": "ok", "app": "Dua Space"})


async def root(_req):
    return web.Response(text="Dua Space Running.", content_type="text/plain")


async def run_server():
    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    return runner


# -------------------- نقطة الانطلاق الرئيسية --------------------

async def run():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing!")
    init_db()
    runner = await run_server()

    app = Application.builder().token(BOT_TOKEN).build()

    # أوامر الإدارة الأساسية
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("addmaterial", add_material_cmd))
    app.add_handler(CommandHandler("delmaterial", del_material_cmd))
    app.add_handler(CommandHandler("addzekr", add_zekr_cmd))
    app.add_handler(CommandHandler("delzekr", del_zekr_cmd))
    app.add_handler(CommandHandler("post", post_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))

    # التفاعلات والرسائل
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, on_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        log.info("Dua Space running smoothly.")
        await asyncio.Event().wait()
    finally:
        if app.updater and app.updater.running:
            await app.updater.stop()
        if app.running:
            await app.stop()
        await app.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run())
