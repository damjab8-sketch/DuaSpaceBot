import os
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
AUTO_POST_TEXT = os.environ.get(
    "AUTO_POST_TEXT",
    "أهلًا بكم في Dua Space ✦"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلًا بك في بوت Dua Space ✦\n"
        "استخدمي /help لمعرفة الأوامر."
    )

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "الأوامر المتاحة:\n"
        "/start - بدء استخدام البوت\n"
        "/help - عرض المساعدة\n"
        "للنشر في القناة، استخدمي /publish "
        "ثم اكتبي المنشور."
    )

async def publish(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "عذرًا، هذا الأمر مخصص للمشرفة فقط."
        )
        return

    text = " ".join(context.args)

    if not text:
        await update.message.reply_text(
            "اكتبي /publish ثم نص المنشور."
        )
        return

    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text
        )
        await update.message.reply_text(
            "تم نشر المنشور في القناة بنجاح."
        )
    except Exception:
        logging.exception("Publishing failed")
        await update.message.reply_text(
            "تعذر النشر. تحققي من صلاحيات البوت."
        )

async def scheduled_posts(app: Application):
    while True:
        await asyncio.sleep(24 * 60 * 60)

        try:
            await app.bot.send_message(
                chat_id=CHANNEL_ID,
                text=AUTO_POST_TEXT
            )
            logging.info("Scheduled post sent")
        except Exception:
            logging.exception("Scheduled post failed")

async def after_start(app: Application):
    app.create_task(scheduled_posts(app))

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(after_start)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("publish", publish))

    app.run_polling()

if __name__ == "__main__":
    main()
