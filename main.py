import logging, re
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ChatMember, 
)
from telegram.ext import (
    Application, 
    CallbackQueryHandler, 
    ContextTypes, 
    CommandHandler, 
    AIORateLimiter, 
    InlineQueryHandler, 
    ChatMemberHandler, 
)
from telegram._callbackquery import CallbackQuery
from dotenv import load_dotenv
from os import getenv
from re import fullmatch
from tools import *
from conversations import *
from typing import List, Tuple, Dict

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

data = load_json(getenv("DATA_PATH"))
_pin_statuses: Dict[Tuple[int, int], bool] = {} # (user_id, message_id) -> pin_status

def get_chat_props(chat_id: int) -> dict:
    return data["init"]["chats"].get(str(chat_id), {})

async def load_keys_from_query(query: CallbackQuery, query_data: str = None) -> List[str]:
    if not query_data:
        query_data = load_query(query.data)
    if query_data == SPLIT_CALLBACK_QUERY:
        keys=[]
    elif not fullmatch(callback_query_path_re, query_data):
        await query.answer(data["init"]["dialog"]["error_bad_callback_query"])
        return
    else:
        keys = query_data.split(SPLIT_CALLBACK_QUERY)
    return keys

async def get_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    keys = await load_keys_from_query(query=query)
    res = get_value(data, keys)
    if res.keys()=={"IK_TEXT"}:
        await query.answer(data["init"]["dialog"]["empty_data_for_the_key"])
        return
    if not any(type(v) is dict for v in res.values()):
        try:
            res = await send_message_by_props(
                props=res, 
                chat_data=(data["init"]["chats"].get(str(res.get("CHAT_ID"))) if res.get("TYPE")=="forward" else {}), 
                update=update, 
                context=context, 
            )
            await query.answer()
        except EmptyProps:
            await query.answer(data["init"]["dialog"]["empty_data_for_the_key"])
        except NotPermitted:
            await query.answer(data["init"]["dialog"]["not_permitted_for_the_key"])
        return
    await query.answer()
    pin_status = _pin_statuses.get((query.from_user.id, query.message.message_id), False)
    text, reply_markup = generate_message_args(data=data, keys=keys, is_admin=is_admin(update.effective_user.id, "edit", data), bot_username=context.bot.username, is_pinned=pin_status)
    await update.effective_message.edit_text(text, reply_markup=reply_markup)

async def pin_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    keys = await load_keys_from_query(query=query, query_data=load_query(query.data)[1:])
    pin_new_status = bool(int(load_query(query.data)[0]))
    _pin_statuses[(query.from_user.id, query.message.message_id)] = pin_new_status
    if pin_new_status:
        await query.pin_message()
    else:
        await query.unpin_message()
    text, reply_markup = generate_message_args(data=data, keys=keys, is_admin=is_admin(update.effective_user.id, "edit", data), bot_username=context.bot.username, is_pinned=pin_new_status)
    await update.effective_message.edit_text(text, reply_markup=reply_markup)

@cache_users_data(data, update_data = lambda new_data: data.update(new_data))
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    match = re.match(r'\/start ('+callback_query_path_re+')', update.effective_message.text)
    if match and match.groups():
        path = match.groups()[0]
        keys = path.split(SPLIT_CALLBACK_QUERY)
        try:
            res = get_value(data, keys)
        except KeyError:
            await update.effective_message.reply_text(data["init"]["dialog"]["invalid_path"])
            return
        if not any(type(v) is dict for v in res.values()):
            try:
                res = await send_message_by_props(
                    props=res, 
                    chat_data=(data["init"]["chats"].get(str(res.get("CHAT_ID"))) if res.get("TYPE")=="forward" else {}), 
                    update=update, 
                    context=context, 
                )
            except EmptyProps:
                await update.effective_chat.send_message(data["init"]["dialog"]["empty_data_for_the_path"])
            except NotPermitted:
                await update.effective_chat.send_message(data["init"]["dialog"]["not_permitted_for_the_key"])
            return
        text, reply_markup = generate_message_args(data=data, keys=keys, is_admin=is_admin(update.effective_user.id, "edit", data), bot_username=context.bot.username)
    else:
        text = data["init"]["dialog"]["start_title"]
        if is_admin(update.effective_user.id, "edit", data):
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text=data[key]["IK_TEXT"], 
                        callback_data=dump_query(key, code="get")
                    ), 
                    InlineKeyboardButton(
                        text=data["init"]["dialog"]["edit_data_inline_keyboard"], 
                        callback_data=dump_query(key, code="edt")
                    )
                ]
                for key in data if key!="init"
            ] + [
                [
                    InlineKeyboardButton(
                        text=data["init"]["dialog"]["pin_message_inline_keyboard"], 
                        callback_data=dump_query("1"+SPLIT_CALLBACK_QUERY, code="pin")
                    )
                ]
            ])
        else:
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text=data[key]["IK_TEXT"], 
                        callback_data=dump_query(key, code="get")
                    )
                ]
                for key in data if key!="init"
            ] + [
                [
                    InlineKeyboardButton(
                        text=data["init"]["dialog"]["pin_message_inline_keyboard"], 
                        callback_data=dump_query("1"+SPLIT_CALLBACK_QUERY, code="pin")
                    )
                ]
            ])
    await update.effective_message.reply_text(text, reply_markup=reply_markup)

async def get_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query
    if not query:  # empty query should not be handled
        return
    results = inline_query_search.find_keywords(query)
    await update.inline_query.answer(results)

async def new_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(getenv("ADMIN_ID")):
        if update.my_chat_member.new_chat_member.status not in (ChatMember.BANNED, ChatMember.LEFT):
            await update.effective_chat.leave()
        return
    after = update.my_chat_member.new_chat_member.status
    if after == ChatMember.ADMINISTRATOR:
        if str(update.effective_chat.id) not in data["init"]["chats"]:
            data["init"]["chats"][str(update.effective_chat.id)] = {
                "username": update.effective_chat.username, 
                "title": update.effective_chat.title, 
                "type": update.effective_chat.type, 
                "admins": [update.effective_user.id], 
                "strict_forward": False, 
            }
    elif str(update.effective_chat.id) in data["init"]["chats"]:
        del data["init"]["chats"][str(update.effective_chat.id)]
    dump_json(getenv("DATA_PATH"), data)
    await update.effective_user.send_message(
        data["init"]["dialog"]["new_chat_added_successfully"].format(
            id = update.effective_chat.id, 
            title = update.effective_chat.title, 
            status = update.my_chat_member.new_chat_member.status, 
        )
    )

if __name__ == "__main__":
    builder = Application.builder()
    builder.rate_limiter(AIORateLimiter())
    builder.token(getenv("TELEGRAM_BOT_TOKEN"))
    if getenv("TELEGRAM_PROXY"):
        builder.proxy(getenv("TELEGRAM_PROXY"))
        builder.get_updates_proxy(getenv("TELEGRAM_PROXY"))
    application = builder.build()
    application.add_handler(CallbackQueryHandler(get_callback_query, pattern=r'get.+'))
    application.add_handler(CallbackQueryHandler(pin_callback_query, pattern=r'pin.+'))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(gfp_handler)
    application.add_handler(create_ed_handler(
        data, load_query, SPLIT_CALLBACK_QUERY, 
        lambda: dump_json(getenv("DATA_PATH"), data)
    ))
    application.add_handler(InlineQueryHandler(get_inline_query))
    application.add_handler(ChatMemberHandler(new_chat_handler, ChatMemberHandler.MY_CHAT_MEMBER))
    if data["init"].get("status") == "demo":
        def handle_get_updates(get_updates):
            async def filter_updates(*args, **kwargs):
                updates: List[Update] = await get_updates(*args, **kwargs)
                result_updates = []
                for update in updates:
                    if not update.effective_user or update._effective_user.id == int(getenv("ADMIN_ID")):
                        result_updates.append(update)
                return tuple(result_updates)
            return filter_updates
        application.bot._unfreeze()
        application.bot.get_updates = handle_get_updates(application.bot.get_updates)
        application.bot._freeze()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
