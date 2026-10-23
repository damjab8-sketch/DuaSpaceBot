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
logger = logging.getLogger("DuaSpaceMasterProBot")

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

# -------------------- بنك أسئلة الكويز الموسع (ذكاء، مخ، رياضيات، علم نفس) --------------------

QUIZ_QUESTIONS = [
    # --- قسم الذكاء وتدريب المخ ---
    {
        "q": "🧠 ذكاء منطقي: ما هو الشيء الذي يملك عيناً واحدة ولكنه لا يستطيع الرؤية بها أبداً؟",
        "options": ["الإبرة", "الإعصار", "المرآة", "الساعة"],
        "answer": 0,
        "exp": "الإبرة لها عين (ثقب الخيط) ولكنها لا ترى بها!"
    },
    {
        "q": "🧩 لغز ذهني: شيء يزداد كلما أخذت ونقصت منه، فما هو؟",
        "options": ["الحفرة", "العمر", "المعرفة", "المال"],
        "answer": 0,
        "exp": "الحفرة! كلما أخذت منها تراباً زاد عمقها واتسع حجمها."
    },
    {
        "q": "💡 تدريب المخ: ما هو الشيء الذي إذا أطعمته كَبُر وعاش، وإذا سقيته ماءً مات فوراً؟",
        "options": ["النار", "النبات", "الظل", "الرياح"],
        "answer": 0,
        "exp": "النار! الوقود يغذيها، والماء يطفئها ويقضي عليها."
    },
    {
        "q": "🧠 خدعة منطقية: والدان وابنان ذهبوا للصيد، واصطاد كل واحد منهم سمكة، ولكن مجموع الأسماك كان 3 فقط! كيف ذلك؟",
        "options": ["أحدهم فقد سمكته", "هم جد وأب وحفيد", "الصياد كذب في العد", "خدعة بصرية"],
        "answer": 1,
        "exp": "الجد أب، والأب ابن للجد وأب للحفيد، والحفيد ابن! هم 3 أشخاص فقط."
    },
    {
        "q": "💡 لغز التفكير الجانبي: خمسة رجال يمشون تحت المطر دون مظلة أو قبعة، ولم يبتل شعر رأس أحدهم إطلاقاً.. لماذا؟",
        "options": ["لأنهم كانوا صلعاناً", "لأن المطر كان خفيفاً", "كانوا يجرون بسرعة", "كانوا تحت سقف"],
        "answer": 0,
        "exp": "لأنهم صلعان لا يملكون شعراً ليبتل أصلاً!"
    },
    {
        "q": "🧠 نمط وتركيز: ما هو الحرف الذي يأتي تالياً في المتتالية: (س، ث، ر، خ، ج، ...)؟",
        "options": ["س (سبت)", "أ (أحد)", "ج (جمعة)", "ث (ثلاثاء)"],
        "answer": 0,
        "exp": "الحروف تمثل بدايات أيام الأسبوع (سبت، أحد، اثنين، ثلاثاء، أربعاء، خميس، جمعة)."
    },

    # --- قسم الرياضيات والحساب الذهني ---
    {
        "q": "📐 حساب ذهني: عدد إذا ضربته في نفسه ثم أضفت إليه خمسة أصبح الناتج 30، فما هو العدد؟",
        "options": ["4", "5", "6", "25"],
        "answer": 1,
        "exp": "5 × 5 = 25، و 25 + 5 = 30."
    },
    {
        "q": "🔢 متتالية عددية: ما هو العدد التالي في المتتالية: 2، 4، 8، 16، 32، ...؟",
        "options": ["48", "64", "50", "60"],
        "answer": 1,
        "exp": "كل عدد ينتج من مضاعفة (ضرب ×2) العدد الذي قبله: 32 × 2 = 64."
    },
    {
        "q": "💡 مسألة رياضية: مضرب وكرة ثمنهما معاً 1.10 دولار. المضرب يزيد ثمنه عن الكرة بـ 1.00 دولار، فما هو ثمن الكرة؟",
        "options": ["0.10 دولار", "0.05 دولار", "0.01 دولار", "0.50 دولار"],
        "answer": 1,
        "exp": "ثمن الكرة 0.05 دولار، وثمن المضرب 1.05 دولار (المجموع 1.10 والفرق 1.00)."
    },
    {
        "q": "📐 هندسة: كم مجموع قياسات الزوايا الداخلية لأي مثلث في الفضاء الإقليدي؟",
        "options": ["90 درجة", "180 درجة", "360 درجة", "270 درجة"],
        "answer": 1,
        "exp": "مجموع قياسات زوايا أي مثلث داخلياً دائماً 180 درجة."
    },
    {
        "q": "🔢 لغز الأعداد: ما هو أصغر عدد أولي فردي؟",
        "options": ["1", "2", "3", "5"],
        "answer": 2,
        "exp": "العدد 2 هو أصغر عدد أولي ولكنه زوجي، لذا فإن أصغر عدد أولي فردي هو 3."
    },

    # --- قسم علم النفس والسلوك البشري ---
    {
        "q": "🧠 علم نفس: ما هو المصطلح الذي يصف ميل الإنسان للبحث عن المعلومات التي تؤكد معتقداته السابقة وتجاهل غيرها؟",
        "options": ["الانحياز التأكيدي (Confirmation Bias)", "تأثير الهالة (Halo Effect)", "التنافر المعرفي", "عقدة النقص"],
        "answer": 0,
        "exp": "الانحياز التأكيدي يجعل العقل يبحث فقط عما يوافق هواه ومعتقده المسبق."
    },
    {
        "q": "💭 علم نفس الشخصية: ما هي التجربة الشهيرة التي أثبتت تأثير الضغط الاجتماعي ومسايرة رأي الجماعة ولو كان خاطئاً؟",
        "options": ["تجربة سجن ستانفورد", "تجربة سولومون آش (Asch)", "تجربة بافلوف", "تجربة ميلغرام"],
        "answer": 1,
        "exp": "تجربة آش لمطابقة الخطوط أثبتت أن الفرد قد يغير إجابته الصحيحة ليوافق الجماعة."
    },
    {
        "q": "🧠 علم النفس العصبي: ما هو الجزء المسؤول بشكل رئيسي في الدماغ عن معالجة المشاعر والخوف والذاكرة العاطفية؟",
        "options": ["اللوزة الدماغية (Amygdala)", "المخيخ", "الفص الجداري", "الجسم الثفني"],
        "answer": 0,
        "exp": "اللوزة الدماغية (Amygdala) هي مركز التحكم بردود الفعل العاطفية واستجابة الخوف."
    },
    {
        "q": "💡 علم نفس: الشعور بالانزعاج النفسي والتوتر عند وجود تعارض بين معتقدين أو بين المعتقد والسلوك يسمى:",
        "options": ["التنافر المعرفي (Cognitive Dissonance)", "الإسقاط النفسي", "التحويل النفسي", "الاكتئاب التفاعلي"],
        "answer": 0,
        "exp": "التنافر المعرفي يدفع الإنسان لتبرير أفعاله لتخفيف الصراع الداخلي."
    },
    {
        "q": "💭 التحليل النفسي: من هو مؤسس مدرسة التحليل النفسي وصاحب نظرية الـ (أنا، والأنا الأعلى، والهو)؟",
        "options": ["سيغموند فرويد", "كارل يونغ", "جون واطسون", "إبراهام ماسلو"],
        "answer": 0,
        "exp": "سيغموند فرويد هو الأب الروحي لمدرسة التحليل النفسي وتقسيم بنية الشخصية."
    },
    {
        "q": "🧠 علم نفس: قاعدة ماسلو الشهيرة (هرم الاحتياجات) تضع في قمة الهرم رغبة الإنسان في:",
        "options": ["تحقيق الذات (Self-Actualization)", "الأمان والاستقرار", "الحاجة للانتماء", "الاحتياجات الفسيولوجية"],
        "answer": 0,
        "exp": "تحقيق الذات وتطوير أقصى إمكانيات الفرد تتربع على قمة هرم ماسلو."
    },
    {
        "q": "💡 علم النفس السلوكي: تجربة إيفان بافلوف الشهيرة على الكلاب كانت حجر الأساس في اكتشاف نظرية:",
        "options": ["الاشتراط الكلاسيكي (Classical Conditioning)", "التعلم بالاستبصار", "التعلم الاجتماعي", "التنافر الوجداني"],
        "answer": 0,
        "exp": "الاشتراط الكلاسيكي برهن على ربط المثير المحايد (الجرس) باستجابة طبيعية (اللعاب)."
    },

    # --- قسم الطب والمعلومات العامة ---
    {
        "q": "🩺 في جسم الإنسان، ما هو العضو الذي يستهلك حوالي 20% من إجمالي الأكسجين والدم في الجسم رغم صغر وزنه؟",
        "options": ["الكبد", "الدماغ", "القلب", "الكليتان"],
        "answer": 1,
        "exp": "الدماغ يستهلك نحو خمس طاقة الجسم لتغذية مليارات الخلايا العصبية."
    },
    {
        "q": "🩸 ما هي فصيلة الدم التي تلقب بـ «المعطي العام» لعدم احتوائها على أنتيجينات مسببة للتجلط؟",
        "options": ["A+", "AB+", "O-", "B-"],
        "answer": 2,
        "exp": "فصيلة O السالبة (O-) تنقذ المرضى في الطوارئ لنقلها لأي فصيلة بأمان."
    },
    {
        "q": "📖 سورة في القرآن الكريم تعادل قراءتها ثلث القرآن الكريم، فما هي؟",
        "options": ["سورة الفاتحة", "سورة الإخلاص", "سورة الكهف", "سورة يس"],
        "answer": 1,
        "exp": "سورة الإخلاص، لاشتمالها الصافي على توحيد الله وتنزيهه."
    }
]

# -------------------- المنشور الحماسي المعتمد للقناة --------------------

OFFICIAL_LAUNCH_POST = (
    "🪐 انطلاقة جديدة ومساحة متكاملة بين أيديكم!\n\n"
    "يسرّنا أن نعلن لكم رسميًا عن إطلاق بوت Dua Space الشامل | بوابتكم الذكية للمعرفة، الإبداع، والارتقاء ✨\n\n"
    "سواء كنت تبحث عن مرجع دراسي، تطمح لتطوير مهاراتك ولغاتك، تبحث عن حلول وتصاميم مميزة، أو تريد مساحة للهدوء والتركيز.. جمعنا كل ذلك في مكان واحد:\n\n"
    "✨ ماذا ينتظركم داخل البوت؟\n"
    "• 📖 القرآن الكريم كاملاً (114 سورة) تلاوة وتفسيراً.\n"
    "• 📐 الصرح الهندسي والتقني: طبية حيوية، برمجيات وذكاء اصطناعي، مدنية، كهربائية، وميكانيكية.\n"
    "• 🩺 مكتبات تخصصية مجانية: طب، لغات، علم نفس، فكر وفلسفة، وروايات عالمية.\n"
    "• 🎓 دليل المنح الدراسية العالمية والفرص التعليمية بروابطها المباشرة.\n"
    "• 🎌 عالم الأنمي والمانجا والروايات المترجمة.\n"
    "• 🧠 بنك تحديات ومسابقات الذكاء، تدريب المخ، والرياضيات وعلم النفس.\n"
    "• 🛍️ خدمات التصميم الإبداعي والحلول الرقمية.\n"
    "• ⏱️ رفيق دراستك: مؤقت التركيز (Pomodoro) والسبحة الإلكترونية.\n"
    "• ✨ ركن دعاء مجاب الخاص، وإشراقات واقتباسات ملهمة متجددة.\n\n"
    "🌱 هذه خطوتنا الأولى فقط! المنصة في تحديث مستمر، ونعمل دوريًا على إضافة مراجع جديدة، توسيع الأقسام، وتقديم مفاجآت قيّمة تثري تجربتكم.\n\n"
    "🚀 المساحة تكبر بكم ومعكم:\n"
    "جرّبوا البوت الآن وشاركوا الرابط مع أصدقائكم وزملائكم لتعم الفائدة:\n"
    "🤖 ابدأ التجربة من هنا: @DuaSpaceHelperBot\n\n"
    "القادم أعظم وأجمل، وكونوا بالقرب دائمًا 🪐💫"
)

# -------------------- بنك المنشورات التلقائية للقناة (كل 4 ساعات) --------------------

AUTO_POSTS = [
    "﴿أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ﴾ ✨\n\nسبحان الله، والحمد لله، ولا إله إلا الله، والله أكبر.",
    "﴿وَتَوَكَّلْ عَلَى الْعَزِيزِ الرَّحِيمِ * الَّذِي يَرَاكَ حِينَ تَقُومُ﴾ 🪐",
    "قال رسول الله ﷺ: «مَن سَلَكَ طَرِيقًا يَلْتَمِسُ فِيهِ عِلْمًا، سَهَّلَ اللَّهُ له به طَرِيقًا إلى الجَنَّةِ». 🌿",
    "قال رسول الله ﷺ: «إنَّ اللهَ يُحِبُّ إذا عمِلَ أحَدُكُم عمَلًا أنْ يُتْقِنَه». 💫",
    "«لا يقاس النجاح بالموقع الذي يتبوأه المرء في حياته، بقدر ما يقاس بالصعاب التي تغلب عليها.» — بوكر واشنطن",
    "«العقل الذي يتسع لفكرة جديدة لا يعود أبداً إلى حجمه الأصلي.» — أوليفر وندل هولمز 💡",
    "«كن أنت التغيير الذي تريد أن تراه في هذا العالم.» — غاندي ✨",
    "﴿إِنَّ مَعَ الْعُسْرِ يُسْرًا﴾ 🌸",
    "«سَيِّدُ الاِسْتِغْفَارِ: اللَّهُمَّ أَنْتَ رَبِّي لاَ إِلَهَ إِلاَّ أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ، وَأَنَا عَلَى عهدِكَ وَوَعْدِكَ مَا اسْتَطَعْتُ». 📿",
]

# -------------------- الخدمات الافتراضية --------------------

DEFAULT_SERVICES = [
    ("🎨 التصميم الجرافيكي والهويات البصرية", "تصميم شعارات احترافية، بطاقات وهوية بصرية متكاملة لمشروعك.", "حسب تفاصيل الطلب"),
    ("🖼️ تصميم بوسترات وبنرات إعلانية", "تصاميم لمنصات التواصل الاجتماعي بجودة وإتقان عالي.", "حسب تفاصيل الطلب"),
    ("💌 بطاقات التهنئة والدعوات الرقمية", "تصاميم مخصصة ومبتكرة للمناسبات الخاصة والاحتفالات.", "حسب تفاصيل الطلب"),
    ("📦 طلب تصميم وحلول مخصصة", "أرسل فكرتك ومتطلباتك ليتم تقدير التكلفة والوقت المناسب.", "يحدد بعد مراجعة الطلب"),
]

# -------------------- باقة الكتب والمصادر الشاملة الموسعة --------------------

PRELOADED_BOOKS = [
    # 🧠 علم النفس والمجتمع (قسم موسع وشامل)
    ("psychology", "علم النفس المعرفي وسلوك الإنسان", "د. روبرت سولسو", "دراسة شيقة لكيفية عمل الذاكرة والتفكير واتخاذ القرارات.", "https://ar.wikipedia.org/wiki/%D8%B9%D9%84%D9%85_%D8%A7%D9%84%D9%86%D9%81%D8%B3_%D8%A7%D9%84%D9%85%D8%B9%D8%B1%D9%81%D9%8A"),
    ("psychology", "سيكولوجية الجماهير", "غوستاف لوبون", "الكتاب الكلاسيكي الأهم في فهم العقل الجمعي وحركة الشعوب والتأثير فيها.", "https://www.hindawi.org/books/64516358/"),
    ("psychology", "التفكير، بسرعة وببطء", "دانيال كانمان", "فهم النظم الذهنية وسيكولوجية الانحيازات المعرفية التي تحكم قراراتنا اليومية.", "https://ar.wikipedia.org/wiki/%D8%A7%D9%84%D8%AA%D9%81%D9%83%D9%8A%D8%B1_%D8%A8%D8%B3%D8%B1%D8%B9%D8%A9_%D9%88%D8%A8%D8%A8%D8%B7%D8%A1"),
    ("psychology", "الإنسان يبحث عن المعنى", "فيكتور فرانكل", "العلاج بالمعنى وقوة الإرادة البشرية في التغلب على أعتى الصدمات والظروف.", "https://ar.wikipedia.org/wiki/%D8%A7%D9%84%D8%A5%D9%86%D8%B3%D8%A7%D9%86_%D9%8A%D8%A8%D8%AD%D8%AB_%D8%B9%D9%86_%D8%A7%D9%84%D9%85%D8%B9%D8%B1%D9%81%D9%8A"),
    ("psychology", "مقدمة في التحليل النفسي", "سيغموند فرويد", "المرجع التأسيسي لفهم اللاشعور وعقد الشخصية وتفسير الأحلام.", "https://www.hindawi.org/books/65207935/"),
    ("psychology", "علم النفس العيادي والاضطرابات النفسية", "د. عبد الستار إبراهيم", "دليل مبسط لفهم القلق، الاكتئاب، والوساوس وطرق العلاج المعرفي السلوكي (CBT).", "https://ar.wikipedia.org/wiki/%D8%B9%D9%84%D9%85_%D8%A7%D9%84%D9%86%D9%81%D8%B3_%D8%A7%D9%84%D8%B3%D can%D9%8A%D9%86%D9%8A%D9%83%D9%8A"),

    # 📐 الصرح الهندسي الشامل
    ("eng_bio", "مدخل إلى الهندسة الطبية الحيوية (Biomedical Engineering)", "John Enderle", "المرجع التأسيسي في الأجهزة الطبية، الأعضاء الصناعية، وتطبيقات الهندسة في الطب.", "https://www.elsevier.com/"),
    ("eng_bio", "دليل صيانة وتصميم الأجهزة الطبية والمستشفيات", "منظمة الصحة العالمية (WHO)", "دليل تطبيقي شامل عن عمل وصيانة أجهزة الأشعة، العناية المركزة، ومراقبة المرضى.", "https://www.who.int/"),
    ("eng_soft", "أساسيات هندسة البرمجيات وتصميم النظم", "Ian Sommerville", "المرجع الأكاديمي الرائد في دورة حياة البرمجيات، النظم المعمارية، وإدارة المشاريع.", "https://ar.wikipedia.org/wiki/%D9%87%D9%86%D8%AF%D8%B3%D8%A9_%D8%A7%D9%84%D8%A8%D8%B1%D9%85%D8%AC%D9%8A%D8%A7%D8%AA"),
    ("eng_soft", "مقدمة في الخوارزميات وهياكل البيانات (Algorithms)", "Thomas H. Cormen", "الكتاب الأهم عالمياً لبناء التفكير المنطقي البرمجي وحل المشكلات المعقدة.", "https://mitpress.mit.edu/"),
    ("eng_soft", "دليل الذكاء الاصطناعي وتعلم الآلة الشامل", "Stuart Russell & Peter Norvig", "المرجع العالمي الشامل لجامعة بيركلي في الذكاء الاصطناعي والشبكات العصبية.", "https://aima.cs.berkeley.edu/"),
    ("eng_civil", "مبادئ الهندسة المدنية وتصميم المنشآت الخرسانية", "د. شاكر البحيري", "أساسيات التصميم الإنشائي، حساب الأحمال، واشتراطات الكود الهندسي للمباني.", "https://ar.wikipedia.org/wiki/%D9%87%D9%86%D8%AF%D8%B3%D8%A9_%D9%85%D8%AF%D9%86%D9%8A%D8%A9"),
    ("eng_civil", "ميكانيكا التربة وهندسة الأساسات (Soil Mechanics)", "Braja M. Das", "دراسة سلوك التربة، قدرة التحمل، وتصميم الأساسات العميقة والسطحية.", "https://www.cengage.com/"),
    ("eng_elec", "أساسيات الدوائر الكهربائية (Electric Circuits)", "Charles Alexander & Matthew Sadiku", "المرجع المعتمد في الجامعات لتحليل دوائر التيار المستمر والمتردد.", "https://www.mheducation.com/"),
    ("eng_elec", "الإلكترونيات المعاصرة ونبائط أشباه الموصلات", "Robert Boylestad", "شرح عمل الترانزستورات، مكبرات العمليات، والدوائر الإلكترونية المتكاملة.", "https://www.pearson.com/"),
    ("eng_mech", "الديناميكا الحرارية الهندسية (Engineering Thermodynamics)", "Yunus Cengel", "المرجع الكلاسيكي الرائع لفهم الطاقة، انتقال الحرارة، ومحركات الاحتراق.", "https://www.mheducation.com/"),
    ("eng_mech", "ميكانيكا الموائع وتطبيقاتها الهندسية (Fluid Mechanics)", "Frank White", "شرح قوانين تدفق السوائل والغازات، المضخات، وتوربينات الطاقة.", "https://www.mheducation.com/"),

    # 🕌 الإسلامية
    ("islamic", "الأربعون النووية", "الإمام النووي", "أهم الأحاديث الجامعة لقواعد وأصول الدين الإسلامي.", "https://sunnah.com/nawawi40"),
    ("islamic", "رياض الصالحين", "الإمام النووي", "دليل المسلم العملي في الأخلاق والعبادات اليومية.", "https://sunnah.com/riyadussalihin"),
    ("islamic", "الرحيق المختوم", "صفي الرحمن المباركفوري", "السيرة النبوية العطرة كاملة ومحققة بأدق التفاصيل.", "https://ar.m.wikipedia.org/wiki/%D8%A7%D9%84%D8%B1%D8%AD%D9%8A%D9%82_%D8%A7%D9%84%D9%85%D8%AE%D8%AA%D9%88%D9%85"),
    ("islamic", "تفسير السعدي (تيسير الكريم الرحمن)", "الشيخ عبد الرحمن السعدي", "من أيسر وأوضح تفاسير القرآن الكريم فهماً وتدبراً.", "https://quran.ksu.edu.sa/tafseer/saadi/"),
    ("islamic", "الداء والدواء (الجواب الكافي)", "ابن قيم الجوزية", "العلاج الإيماني والنفسي لأمراض القلوب والمعاصي.", "https://www.hindawi.org/books/24016781/"),

    # 🩺 الطبية
    ("medical", "دليل الإسعافات الأولية الشامل", "منظمة الصحة العالمية", "دليل عملي مصور للتعامل مع الحوادث والطوارئ وإنقاذ الأرواح.", "https://www.who.int/ar"),
    ("medical", "أطلس التشريح البشري (Netter Atlas)", "Frank H. Netter", "المرجع العالمي الأكثر شهرة لرسومات تشريح جسم الإنسان بدقة بالغة.", "https://www.elsevier.com/"),
    ("medical", "مبادئ علم وظائف الأعضاء (Guyton Physiology)", "John E. Hall", "المرجع الأساسي لطلاب الطب لفهم وظائف أجهزة الجسم الحيوية.", "https://ar.wikipedia.org/wiki/%D8%B9%D9%84%D9%85_%D9%88%D8%B8%D8%A7%D8%A6%D9%81_%D8%A7%D9%84%D8%A3%D8%B9%D8%B6%D8%A7%D8%A1"),
    ("medical", "المرجع السريع في الأدوية والصيدلة السريرية", "نخبة من الأطباء والصيادلة", "دليل مختصر عن تصنيفات واستخدامات وجرعات الأدوية الشائعة.", "https://www.drugs.com/"),
    ("medical", "أساسيات التحاليل الطبية وقراءة النتائج", "د. أحمد سامي", "شرح لكيفية قراءة وفهم نتائج تحاليل الدم والوظائف المخبرية.", "https://ar.wikipedia.org/wiki/%D8%A7%D8%AE%D8%AA%D8%A8%D8%A7%D8%B1_%D8%AF%D9%85"),

    # 🌍 اللغات
    ("languages", "English Grammar in Use", "Raymond Murphy", "المرجع العالمي الأشهر لتعلم وضبط قواعد اللغة الإنجليزية.", "https://www.cambridge.org/"),
    ("languages", "English Vocabulary in Use", "Michael McCarthy", "بناء حصيلة لغوية إنجليزية ثرية من المفردات اليومية والأكاديمية.", "https://www.cambridge.org/"),
    ("languages", "دليل المحادثة التركية اليومية", "إسطنبول لتعليم اللغات", "أهم الجمل والعبارات لتعلم المحادثة التركية بطلاقة.", "https://www.turkishteatime.com/"),
    ("languages", "سلسلة İstanbul لتعلم اللغة التركية", "جامعة إسطنبول", "المنهج الرسمي المعتمد لتعلم التركية من المستوى A1 حتى C1.", "https://dilmerkezi.istanbul.edu.tr/"),
    ("languages", "أساسيات وقواعد اللغة الفرنسية", "معهد اللغات الدولي", "مدخل مبسط للنطق الصحيح والقواعد الأساسية للمبتدئين.", "https://www.lepointdufle.net/"),

    # 🏛️ الفكر والفلسفة
    ("philosophy", "مقدمة ابن خلدون", "عبد الرحمن بن خلدون", "المرجع التأسيسي الأول في علم الاجتماع وفلسفة التاريخ والعمران.", "https://www.hindawi.org/books/58632617/"),
    ("philosophy", "قصة الفلسفة", "ويل ديورانت", "رحلة ممتعة وشاملة تستعرض حياة وأفكار كبار الفلاسفة عبر العصور.", "https://www.hindawi.org/books/42948638/"),

    # 💡 تطوير الذات
    ("selfdev", "العادات الذرية (Atomic Habits)", "جيمس كلير", "الدليل العملي الأقوى لبناء العادات الإيجابية والتخلص من السلبية.", "https://jamesclear.com/atomic-habits"),
    ("selfdev", "العمل العميق (Deep Work)", "كال نيوپورت", "استراتيجيات للتركيز الفائق والإنتاجية العالية في عالم مليء بالمشتتات.", "https://calnewport.com/"),

    # 📖 روايات وقصص
    ("novels", "البؤساء (Les Misérables)", "فيكتور هوجو", "ملحمة إنسانية خالدة عن العدالة والرحمة والأمل.", "https://www.hindawi.org/books/47268307/"),
    ("novels", "الخيميائي", "باولو كويلو", "رواية رمزية عالمية تحث على البحث عن الكنز الداخلي وتحقيق الحلم.", "https://paulocoelhoblog.com/"),

    # 📑 موضوعات وأدلة عامة
    ("topics", "دليل الطالب الناجح للتفوق الدراسي", "Dua Space", "خطوات واستراتيجيات عملية لتنظيم المذاكرة والمراجعة الذكية.", "https://t.me/DuaSpace1"),
]

# -------------------- اللغات والواجهات --------------------

TEXTS = {
    "ar": {
        "welcome": "أهلًا بكم في Dua Space! 🪐\nمساحتكم الشاملة للإبداع، المعرفة، والارتقاء.\nيرجى اختيار القسم المطلوب عبر الأزرار أدناه:",
        "must_subscribe": "⚠️ **تنبيه للاستمرار:**\n\nيرجى الانضمام إلى قناة Dua Space الرسمية أولاً لتتمكن من استخدام البوت ومكتباته.\n\nاضغط أدناه للانضمام، ثم اضغط على «✅ تحقّق من الاشتراك»:",
        "sub_btn": "📢 انضم للقناة الآن",
        "check_sub": "✅ تحقّق من الاشتراك",
        "sub_success": "🎉 شكراً لانضمامك! تم تفعيل القائمة بالكامل.",
        "sub_failed": "❌ لم يتم التحقق من اشتراكك بالقناة بعد. انضم أولاً ثم أعد المحاولة.",
        "lang_btn": "🌐 تغيير اللغة / Language",
        "quran_btn": "📖 القرآن الكريم كاملاً (114 سورة)",
        "services": "🛍️ الخدمات والتصميم",
        "portfolio": "🎨 معرض الأعمال",
        "anime_hub": "🎌 عالم الأنمي والمانجا",
        "dua_corner": "✨ ركن دعاء مجاب | Dua Corner",
        "engineering_hub": "📐 الصرح الهندسي والتقني",
        "scholarships": "🎓 دليل المنح والفرص الشامل",
        "quiz_btn": "🧠 بنك تحديات الذكاء والمخ والمعرفة",
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
        "share_text": "🪐 أنصحكم بتجربة بوت Dua Space الشامل! القرآن كاملاً، والصرح الهندسي، ومكتبات الطب واللغات وعلم النفس، والمانجا، والمنح، وتحديات الذكاء:\n\nhttps://t.me/DuaSpaceHelperBot",
        "social_text": "🪐 **منصات وحسابات Dua Space الرسمية:**\n\n• القناة الرسمية: https://t.me/DuaSpace1\n• الإدارة والتواصل المباشر: @xdua1\n• ترقبوا قريباً بقية الروابط والمنصات التابعة لنا!",
        "faq_text": "💡 **الأسئلة الشائعة حول خدمات Dua Space:**\n\n• **كيف أطلب خدمة؟**\nمن قائمة «🛍️ الخدمات والتصميم»، اختر الخدمة ثم اضغط «طلب هذه الخدمة».\n\n• **هل الكتب والمصادر مجانية؟**\nنعم، كافة الكتب والمراجع الهندسية والطبية والنفسية مجانية تماماً للقراءة والتحميل المباشر.",
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
        "anime_hub": "🎌 Anime & Manga Realm",
        "dua_corner": "✨ Dua Mujab's Special Corner",
        "engineering_hub": "📐 Engineering & Tech Realm",
        "scholarships": "🎓 Global Scholarships Guide",
        "quiz_btn": "🧠 IQ, Mind & Knowledge Quiz",
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
        "share_text": "🪐 Explore Dua Space Bot! Quran, Engineering, Medicine, Psychology, Languages, Anime, Scholarships, and IQ Quiz:\n\nhttps://t.me/DuaSpaceHelperBot",
        "social_text": "🪐 **Dua Space Links:**\n• Channel: https://t.me/DuaSpace1\n• Admin: @xdua1",
        "faq_text": "💡 All materials and books are completely free.",
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
                quiz_score INTEGER DEFAULT 0,
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

        # إدراج الخدمات الافتراضية
        for title, desc, price in DEFAULT_SERVICES:
            exists = con.execute("SELECT id FROM services WHERE title = ?", (title,)).fetchone()
            if not exists:
                con.execute("INSERT INTO services(title, description, price, active) VALUES(?, ?, ?, 1)", (title, desc, price))

        # إدراج الكتب وتحديث الروابط
        for cat, b_title, b_auth, b_desc, b_url in PRELOADED_BOOKS:
            exists = con.execute("SELECT id FROM books WHERE title = ?", (b_title,)).fetchone()
            if not exists:
                con.execute(
                    "INSERT INTO books(category, title, author, description, file_id, url) VALUES(?, ?, ?, ?, NULL, ?)",
                    (cat, b_title, b_auth, b_desc, b_url)
                )
            else:
                con.execute("UPDATE books SET url = ? WHERE title = ? AND (url IS NULL OR url = '')", (b_url, b_title))
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

# -------------------- القوائم والأزرار الرئيسية --------------------

def language_selection_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇸🇦 العربية", callback_data="setlang:ar"),
                InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en"),
            ]
        ]
    )

def main_menu_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            # القرآن الكريم وركن دعاء المميز
            [InlineKeyboardButton(get_t(user_id, "quran_btn"), callback_data="quran_groups")],
            [InlineKeyboardButton(get_t(user_id, "dua_corner"), callback_data="dua_corner_view")],
            # الصرح الهندسي + عالم الأنمي والمانجا
            [
                InlineKeyboardButton(get_t(user_id, "engineering_hub"), callback_data="eng_hub_view"),
                InlineKeyboardButton(get_t(user_id, "anime_hub"), callback_data="anime_hub_view"),
            ],
            # بنك تحديات الذكاء والمخ + الخدمات والتصميم
            [
                InlineKeyboardButton(get_t(user_id, "quiz_btn"), callback_data="quiz_start"),
                InlineKeyboardButton(get_t(user_id, "services"), callback_data="services"),
            ],
            # المنح والمؤقت ومعرض الأعمال
            [
                InlineKeyboardButton(get_t(user_id, "scholarships"), callback_data="scholarships_hub"),
                InlineKeyboardButton(get_t(user_id, "portfolio"), callback_data="portfolio"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "pomodoro"), callback_data="pomodoro_start"),
                InlineKeyboardButton(get_t(user_id, "quotes"), callback_data="quotes"),
            ],
            # المكتبات التخصصية
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
            # التفاعل والمجتمع
            [
                InlineKeyboardButton(get_t(user_id, "tasbeeh"), callback_data="tasbeeh"),
                InlineKeyboardButton(get_t(user_id, "recommendations"), callback_data="recommend"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "share"), callback_data="share_bot"),
                InlineKeyboardButton(get_t(user_id, "faq"), callback_data="faq_info"),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "follow"), callback_data="follow_us"),
                InlineKeyboardButton(get_t(user_id, "contact"), url=CONTACT_URL),
            ],
            [
                InlineKeyboardButton(get_t(user_id, "lang_btn"), callback_data="change_lang"),
            ],
        ]
    )

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

def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📢 نشر وتثبيت إعلان الإطلاق في القناة", callback_data="admin_pin_official"),
            ],
            [
                InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users"),
                InlineKeyboardButton("📥 طلبات العملاء", callback_data="admin_orders"),
            ],
            [
                InlineKeyboardButton("📢 إذاعة عامة (Broadcast)", callback_data="admin_broadcast"),
                InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
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

# -------------------- نظام الكويز وتحديات الذكاء --------------------

def generate_quiz_keyboard(q_idx):
    q_data = QUIZ_QUESTIONS[q_idx]
    buttons = []
    for opt_idx, opt_text in enumerate(q_data["options"]):
        buttons.append([InlineKeyboardButton(f"• {opt_text}", callback_data=f"quiz_ans:{q_idx}:{opt_idx}")])
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

    if data.startswith("setlang:"):
        lang_code = data.split(":", 1)[1]
        set_user_lang(user_id, lang_code)
        await query.message.reply_text(get_t(user_id, "welcome"), reply_markup=main_menu_keyboard(user_id))
        return

    if data == "change_lang":
        await query.message.reply_text("🌐 اختر لغتك المفضلة / Choose language:", reply_markup=language_selection_keyboard())
        return

    if data == "check_subscription":
        is_sub = await is_user_subscribed(context.bot, user_id)
        if is_sub:
            await query.message.reply_text(get_t(user_id, "sub_success"))
            await query.message.reply_text(get_t(user_id, "welcome"), reply_markup=main_menu_keyboard(user_id))
        else:
            await query.message.reply_text(get_t(user_id, "sub_failed"), reply_markup=force_sub_keyboard(user_id))
        return

    if not is_admin_user(user_id) and not await is_user_subscribed(context.bot, user_id):
        await query.message.reply_text(get_t(user_id, "must_subscribe"), reply_markup=force_sub_keyboard(user_id), parse_mode="Markdown")
        return

    if data == "home":
        context.user_data.pop("flow", None)
        await query.message.reply_text(get_t(user_id, "welcome"), reply_markup=main_menu_keyboard(user_id))
        return

    # 1. الصرح الهندسي والتقني الشامل
    if data == "eng_hub_view":
        text = (
            "📐 **الصرح الهندسي والتقني الشامل | Engineering & Tech Hub 🪐**\n\n"
            "مساحتكم التخصصية لأهم فروع ومراجع الهندسة والتكنولوجيا والذكاء الاصطناعي:\n\n"
            "يرجى اختيار التخصص الهندسي المطلوب لتصفح وتحميل أمهات الكتب والمراجع المعتمدة:"
        )
        await query.message.reply_text(text, reply_markup=engineering_menu_keyboard(), parse_mode="Markdown")
        return

    # 2. كويز الذكاء وتدريب المخ وعلم النفس
    if data in ["quiz_start", "quiz_next"]:
        q_idx = random.randint(0, len(QUIZ_QUESTIONS) - 1)
        q_item = QUIZ_QUESTIONS[q_idx]
        await query.message.reply_text(
            f"🧠 **تحدي الذكاء والمخ والمعرفة:**\n\n{q_item['q']}",
            reply_markup=generate_quiz_keyboard(q_idx),
            parse_mode="Markdown",
        )
        return

    if data.startswith("quiz_ans:"):
        _, q_idx_str, opt_idx_str = data.split(":")
        q_idx = int(q_idx_str)
        opt_idx = int(opt_idx_str)
        q_item = QUIZ_QUESTIONS[q_idx]

        if opt_idx == q_item["answer"]:
            db_execute("UPDATE users SET quiz_score = quiz_score + 1 WHERE user_id = ?", (user_id,))
            res_text = f"🎉 **إجابة عبقرية وصحيحة!**\n\n💡 {q_item['exp']}"
        else:
            correct_opt = q_item["options"][q_item["answer"]]
            res_text = f"❌ **إجابة خاطئة!**\nالصواب هو: **{correct_opt}**\n\n💡 {q_item['exp']}"

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🚀 التحدي التالي", callback_data="quiz_next")],
                [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")],
            ]
        )
        await query.message.reply_text(res_text, reply_markup=kb, parse_mode="Markdown")
        return

    # 3. ركن دعاء مجاب الخاص
    if data == "dua_corner_view":
        text = (
            "✨ **ركن دعاء مجاب | Dua Space • Special Corner 🪐**\n\n"
            "«أهلاً بكم في زاويتي ومساحتي الخاصة. هنا نشارك الشغف، الطموح، ورسائل ملهمة تصنع الفرق. "
            "صُممت منصة Dua Space لتكون بوابتكم المتكاملة نحو التعلم والارتقاء والتميز.»\n\n"
            "📌 **ما الذي ستجدونه هنا دورياً؟**\n"
            "• إضاءات واستراتيجيات ملهمة نحو الطب والتميز الأكاديمي.\n"
            "• ترشيحات منتقاة لأقوى الروايات والكتب العالمية المؤثرة.\n"
            "• تدوينات وتحديثات خاصة بمجتمع Dua Space."
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💬 مراسلة دعاء مباشرة", url=CONTACT_URL)],
                [InlineKeyboardButton("📢 قناة Dua Space الرسمية", url=CHANNEL_URL)],
                [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")],
            ]
        )
        await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # 4. عالم الأنمي والمانجا والروايات الخفيفة
    if data == "anime_hub_view":
        text = (
            "🎌 **عالم الأنمي والمانجا والروايات الخفيفة (Anime & Manga Realm):**\n\n"
            "مساحتكم الترفيهية لمتابعة أقوى الروايات، المانجا، والمانهوا العالمية المترجمة:\n\n"
            "🔥 **أبرز العناوين والمنصات المتاحة:**\n"
            "• **Solo Leveling:** رواية الارتقاء الفردي الخالدة كاملة.\n"
            "• **Jujutsu Kaisen:** فصول مانجا السحر والطاقة الملعونة.\n"
            "• **One Piece & Hunter x Hunter:** ملاحم المغامرة والأسرار.\n"
            "• **روايات لايت نوفل كلاسيكية وشريحة من الحياة.**"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📖 قراءة وتحميل رواية Solo Leveling", url="https://readlightnovels.net/solo-leveling.html")],
                [InlineKeyboardButton("💥 تصفح مانجا جوجوتسو كايسن", url="https://ww1.jujmanga.com/")],
                [InlineKeyboardButton("📚 مكتبة المانجا المترجمة (MangaDex)", url="https://mangadex.org/")],
                [InlineKeyboardButton("📱 تطبيق تاشيومي للمانجا (Mihon)", url="https://mihon.app/")],
                [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")],
            ]
        )
        await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # 5. دليل المنح والفرص التعليمية الشامل
    if data == "scholarships_hub":
        text = (
            "🎓 **دليل المنح والفرص التعليمية الدولية الشاملة:**\n\n"
            "بوابتكم للدراسة المجانية والمنح الممولة بالكامل حول العالم (بكالوريوس ودراسات عليا):\n\n"
            "🌍 **أقوى المنح الحكومية المفتوحة سنوياً:**\n"
            "• **المنحة التركية (Türkiye Bursları):** تمويل 100% يشمل تذاكر الطيران، السكن، الراتب، وسنة لغة مجاناً.\n"
            "• **منحة الحكومة الروسية (Open Doors):** مقاعد مجانية بكافة التخصصات الطبية والهندسية.\n"
            "• **منحة الحكومة المجرية (Stipendium Hungaricum):** أشهر المنح الأوروبية الشاملة.\n"
            "• **منح جامعات قطر وحمد بن خليفة:** تمويل كامل للدراسة والمعيشة.\n"
            "• **منح السعودية للطلاب الدوليين (منصة ادرس في السعودية):** تغطية كاملة وتأمين صحي وسكن."
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🇹🇷 بوابة المنحة التركية الرسمية", url="https://www.turkiyeburslari.gov.tr/")],
                [InlineKeyboardButton("🇭🇺 منحة الحكومة المجرية", url="https://stipendiumhungaricum.hu/")],
                [InlineKeyboardButton("🇷🇺 منحة الحكومة الروسية", url="https://education-in-russia.com/")],
                [InlineKeyboardButton("🇶🇦 منح جامعة قطر الرسمية", url="http://www.qu.edu.qa/students/admission/scholarships")],
                [InlineKeyboardButton("🇸🇦 منصة «ادرس في السعودية»", url="https://studyinsaudi.moe.gov.sa/")],
                [InlineKeyboardButton("📚 مصادر واختبارات الآيلتس (IELTS Ready)", url="https://takeielts.britishcouncil.org/")],
                [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")],
            ]
        )
        await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # 6. الخدمات والتصميم
    if data == "services":
        rows = db_all("SELECT id, title, price FROM services WHERE active = 1 ORDER BY id ASC")
        if not rows:
            await query.message.reply_text("عذرًا، يجري تحديث الخدمات حالياً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]))
            return

        buttons = [
            [InlineKeyboardButton(f"{r['title']}", callback_data=f"show_service:{r['id']}")]
            for r in rows
        ]
        buttons.append([InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")])
        await query.message.reply_text("🛍️ **خدمات وحلول Dua Space:**\nاختر الخدمة المطلوبة لمعرفة التفاصيل وبدء الطلب:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    if data.startswith("show_service:"):
        s_id = int(data.split(":", 1)[1])
        s = db_one("SELECT * FROM services WHERE id = ?", (s_id,))
        if s:
            text = (
                f"✨ **{s['title']}**\n\n"
                f"الوصف:\n{s['description']}\n\n"
                f"السعر: {s['price']}"
            )
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

    # 7. القرآن الكريم
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

    # 8. تصفح أقسام المكتبة العامة والهندسية وعلم النفس
    if data.startswith("cat:"):
        cat_key = data.split(":", 1)[1]
        cat_names = {
            "eng_bio": "🧬 الهندسة الطبية الحيوية",
            "eng_soft": "💻 هندسة البرمجيات والذكاء الاصطناعي",
            "eng_civil": "🏗️ الهندسة المدنية والإنشائية",
            "eng_elec": "⚡ الهندسة الكهربائية والإلكترونية",
            "eng_mech": "⚙️ الهندسة الميكانيكية وهندسة المواد",
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

        back_callback = "eng_hub_view" if cat_key.startswith("eng_") else "home"

        if not rows:
            text = f"{name}\n\n{get_t(user_id, 'empty_sec')}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data=back_callback)]])
            await query.message.reply_text(text, reply_markup=kb)
            return

        buttons = [
            [InlineKeyboardButton(f"📖 {r['title']}", callback_data=f"open_book:{r['id']}")]
            for r in rows
        ]
        buttons.append([InlineKeyboardButton(get_t(user_id, "back"), callback_data=back_callback)])
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
            kb_list.append([InlineKeyboardButton(get_t(user_id, "back"), callback_data=f"cat:{b['category']}")])

            if b["file_id"]:
                try:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=b["file_id"], caption=caption, reply_markup=InlineKeyboardMarkup(kb_list))
                except Exception:
                    await query.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb_list))
            else:
                await query.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode="Markdown")
        return

    # 9. مؤقت بومودورو
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

    # 10. بقية الأدوات
    if data == "faq_info":
        await query.message.reply_text(get_t(user_id, "faq_text"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]), parse_mode="Markdown")
        return

    if data == "quotes":
        quote = random.choice(AUTO_POSTS)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 اقتباس آخر", callback_data="quotes")], [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]])
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
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text={get_t(user_id, 'share_text')}"
        await query.message.reply_text("🪐 شارك رابط البوت مع أصدقائك:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 إرسال الآن", url=share_url)], [InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]))
        return

    if data == "follow_us":
        await query.message.reply_text(get_t(user_id, "social_text"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]))
        return

    if data == "recommend":
        context.user_data["flow"] = {"kind": "rec_msg"}
        await query.message.reply_text(get_t(user_id, "rec_prompt"))
        return

    if data == "portfolio":
        rows = db_all("SELECT id, title FROM portfolio ORDER BY id DESC LIMIT 15")
        if not rows:
            await query.message.reply_text("🎨 معرض الأعمال: يجري رفع التصاميم قريباً 🪐", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")]]))
        else:
            buttons = [[InlineKeyboardButton(f"🖼️ {r['title']}", callback_data=f"show_port:{r['id']}")] for r in rows]
            buttons.append([InlineKeyboardButton(get_t(user_id, "back"), callback_data="home")])
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

    # -------------------- لوحة تحكم الإدارة --------------------
    if not is_admin_user(user_id):
        return

    if data == "admin_home":
        await query.message.reply_text("🎛️ لوحة إدارة Dua Space الشاملة:", reply_markup=admin_keyboard())

    elif data == "admin_pin_official":
        try:
            msg = await context.bot.send_message(chat_id=CHANNEL_ID, text=OFFICIAL_LAUNCH_POST)
            await context.bot.pin_chat_message(chat_id=CHANNEL_ID, message_id=msg.message_id)
            await query.message.reply_text("✅ تم نشر المنشور الحماسي وتثبيته في القناة بنجاح 🪐!")
        except Exception as exc:
            await query.message.reply_text(f"❌ حدث خطأ أثناء النشر والتثبيت: {exc}\n(تأكدي من منح البوت صلاحية تثبيت الرسائل Pin Messages في القناة)")

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
        rows = db_all("SELECT user_id, username, first_name, lang, quiz_score FROM users ORDER BY last_seen DESC LIMIT 50")
        text = f"👥 **مستخدمو البوت النشطين ({len(rows)}):**\n\n"
        for idx, u in enumerate(rows, 1):
            un = f"@{u['username']}" if u["username"] else "بدون يوزر"
            text += f"{idx}. {u['first_name'] or 'مستخدم'} ({un}) - نقاط الذكاء: {u['quiz_score']}\n"
        await query.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="Markdown")

    elif data == "admin_stats":
        u_count = db_one("SELECT COUNT(*) AS n FROM users")["n"]
        b_count = db_one("SELECT COUNT(*) AS n FROM books")["n"]
        o_count = db_one("SELECT COUNT(*) AS n FROM orders")["n"]
        text = f"📊 **إحصائيات Dua Space:**\n\n• المستخدمين: {u_count}\n• الكتب: {b_count}\n• الطلبات: {o_count}\n"
        await query.message.reply_text(text, reply_markup=admin_keyboard())

    elif data == "admin_broadcast":
        context.user_data["flow"] = {"kind": "broadcast"}
        await query.message.reply_text("📢 أرسلي الرسالة التي تودين بثها للجميع:")

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

# -------------------- معالجة النصوص والملفات --------------------

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not msg.text:
        return

    flow = context.user_data.get("flow")

    if flow and flow.get("kind") == "order_details":
        await handle_order_text(update, context, flow)
        return

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

# -------------------- نقطة التشغيل وخادم الويب --------------------

async def handle_health(request):
    return web.Response(text="Dua Space Live Pro 🪐", status=200)

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

        # تفعيل النشر التلقائي في القناة
        asyncio.create_task(channel_auto_poster(application.bot))

        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
