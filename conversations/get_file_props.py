from telegram import (
    Update, 
)
from telegram.ext import (
    ConversationHandler, 
    MessageHandler, 
    CommandHandler, 
    ContextTypes, 
    filters, 
)
from os import getenv

GET_FILE = range(1)

async def start_conversation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if int(getenv("ADMIN_ID")) != update.effective_user.id:
        return ConversationHandler.END
    await update.effective_message.reply_text("OK! send me the file, or /cancel")
    return GET_FILE

async def get_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    attachment = update.effective_message.effective_attachment
    if isinstance(attachment, (list, tuple)):
        attachment=attachment[0]
    await update.effective_message.reply_text(
        text=f"\
_file id: _`{attachment.file_id}`\n\n\
_caption_:`{repr(update.effective_message.caption)[1:-1] if update.effective_message.caption else ''}`\n\n\
or /cancel", 
        parse_mode="markdown", 
    )
    return GET_FILE

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("✅")
    return ConversationHandler.END

gfp_handler = ConversationHandler(
    entry_points=[CommandHandler(
        command="get_file_props", 
        callback=start_conversation_handler, 
    )], 
    states={
        GET_FILE: [MessageHandler(
            filters=filters.ATTACHMENT, 
            callback=get_file_handler, 
        )], 
    }, 
    fallbacks=[CommandHandler("cancel", cancel_handler)]
)
