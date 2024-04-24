import logging
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
)
from telegram.ext import (
    Application, 
    CallbackQueryHandler, 
    ContextTypes, 
    CommandHandler, 
    AIORateLimiter, 
    InlineQueryHandler, 
)
from dotenv import load_dotenv
from os import getenv
from re import fullmatch
from tools import *
from conversations import (
    gfp_handler, 
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

data = load_json(getenv("DATA_PATH"))

async def get_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    query_data = load_query(query.data)
    if query_data == ':':
        keys=[]
    elif not fullmatch(r'\w+(?::\w+)*', query_data):
        await query.answer(data["init"]["dialog"]["error_bad_callback_query"])
        return
    else:
        keys = query_data.split(':')
    res = get_value(data, keys)
    if res.keys()=={"IK_TEXT"}:
        await query.answer(data["init"]["dialog"]["empty_data_for_the_key"])
        return
    if not any(type(v) is dict for v in res.values()):
        try:
            res = await send_message_by_props(props=res, chat=update.effective_chat)
            await query.answer()
        except EmptyProps:
            await query.answer(data["init"]["dialog"]["empty_data_for_the_key"])
        return
    await query.answer()
    await edit_inline_keyboard(data=data, keys=keys, message=update.effective_message)

@cache_users_data(data, update_data = lambda new_data: data.update(new_data))
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    inline_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text=data[key]["IK_TEXT"], 
                callback_data=dump_query(key, code="get")
            )
        ]
        for key in data if key!="init"
    ])
    await update.effective_message.reply_text(
        data["init"]["dialog"]["start_title"], 
        reply_markup=inline_keyboard
    )

async def get_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query
    if not query:  # empty query should not be handled
        return
    results = inline_query_search.find_keywords(query)
    await update.inline_query.answer(results)

if __name__ == "__main__":
    builder = Application.builder()
    builder.rate_limiter(AIORateLimiter())
    builder.token(getenv("TELEGRAM_BOT_TOKEN"))
    builder.proxy(getenv("TELEGRAM_PROXY"))
    builder.get_updates_proxy(getenv("TELEGRAM_PROXY"))
    application = builder.build()
    application.add_handler(CallbackQueryHandler(get_callback_query, pattern=r'get.+'))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(gfp_handler)
    application.add_handler(InlineQueryHandler(get_inline_query))
    application.run_polling(allowed_updates=Update.ALL_TYPES)
