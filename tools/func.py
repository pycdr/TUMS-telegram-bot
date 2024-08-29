import json
from typing import List, Union, Dict, Tuple, Union, Callable
from telegram import (
    Message, Chat, Update, 
    InlineKeyboardButton, InlineKeyboardMarkup, 
    InlineQueryResultArticle, InputTextMessageContent, 
    InlineQueryResultCachedDocument, 
    InputMediaDocument, InputMediaAudio, 
    ChatMember
)
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest
from copy import deepcopy
from os import getenv

__all__ = [
    "get_value", "generate_message_args", "send_message_by_props", 
    "load_query", "dump_query", "EmptyProps", "load_json", "dump_json", 
    "inline_query_search", "cache_users_data", 
    "SPLIT_CALLBACK_QUERY", "is_admin", "current_state_inline_button", 
    "NotPermitted", "is_member", "ProtectedChannelForward"
]
from .constant import *

for escape in NORMALIZE_ESCAPE:
    NORMALIZE_TABLE[escape] = None
NORMALIZE_TABLE = {ord(k):(ord(v) if v else None) for k,v in NORMALIZE_TABLE.items()}
def normalize_text(text: str) -> str:
    return text.translate(NORMALIZE_TABLE)

class InlineQuerySearch:
    EXCEPTION_DATA_MAIN_KEYS = ["init"]
    def __init__(self):
        pass
    def update_data(self, data: dict):
        self.main_data = data
        self.unnesting_data_path, self.unnesting_data_text = self.generate_unnesting_data(data)
        self.unnesting_data_text = list(map(normalize_text, self.unnesting_data_text))
    def generate_unnesting_data(self, data: dict, main = True) -> Tuple[List[str],List[str]]:
        new_unnesting_data_path = []
        new_unnesting_data_text = []
        keys = list(data.keys())
        if main:
            for exception in self.EXCEPTION_DATA_MAIN_KEYS:
                keys.remove(exception)
        else:
            assert "IK_TEXT" in keys, f"IK_TEXT is not defined in {repr(data)[:100]}..."
            keys.remove("IK_TEXT")
        for key in keys:
            if not any(type(v) is dict for v in data[key].values()):
                if self.is_empty_data(data[key]):
                    continue
                new_unnesting_data_path.append(key)
                new_unnesting_data_text.append(data[key]["IK_TEXT"])
            else:
                for subpath, subname in zip(*self.generate_unnesting_data(data[key], main=False)):
                    new_unnesting_data_path.append(key+SPLIT_CALLBACK_QUERY+subpath)
                    new_unnesting_data_text.append(subname+','+data[key]["IK_TEXT"])
        return new_unnesting_data_path, new_unnesting_data_text
    def is_empty_data(self, data: Dict[str, str]) -> bool:
        if data.keys() == {"IK_TEXT"}:
            return True
        if data.get("TYPE") in ("document", "audio", "video"):
            if not data.get("FILE_ID"):
                return True
        elif data.get("TYPE") == "message":
            if not data.get("MESSAGE"):
                return True
        return False
    def find_keywords(self, search: str) -> List[InlineQueryResultArticle]:
        """WARN: this mothed does not use usual/standard search algorithms for now."""
        keywords = normalize_text(search).split()
        result_index = [
            index
            for index, value in enumerate(self.unnesting_data_text)
            if all(keyword in value for keyword in keywords)
        ]
        result_path = [self.unnesting_data_path[index] for index in result_index]
        result_text = [self.unnesting_data_text[index] for index in result_index]
        result_article = []
        for path, text in zip(result_path, result_text):
            article = self.generate_article_by_data(
                path, 
                text, 
                self.find_data_by_path(*path.split(SPLIT_CALLBACK_QUERY))
            )
            if not article:
                continue
            if type(article) is list:
                result_article += article # add a list of articles
            else:
                result_article.append(article)
        return result_article
    def find_data_by_path(self, *path: Tuple[str]) -> Dict:
        return self._find_in_data_by_path(path, data = self.main_data)
    def _find_in_data_by_path(self, path: Tuple[str], data: dict) -> Dict:
        if not path:
            return data
        return self._find_in_data_by_path(path[1:], data=data[path[0]])
    def generate_article_by_data(self, path: str, text: str, data: Dict[str, str]) -> Union[InlineQueryResultArticle, List[InlineQueryResultArticle]]:
        if data.get("TYPE") == "message" and data.get("MESSAGE"):
            return InlineQueryResultArticle(
                id=path, 
                title=data.get("IQ_TITLE") or text, 
                input_message_content=InputTextMessageContent(data.get("MESSAGE")), 
                description=data.get("MESSAGE"), 
            )
        elif data.get("TYPE") == "document" and data.get("FILE_ID"):
            if type(data["FILE_ID"]) is str:
                return InlineQueryResultCachedDocument(
                    id=path, 
                    title=data.get("IQ_TITLE") or text, 
                    document_file_id=data.get("FILE_ID"), 
                    caption=data.get("CAPTION"), 
                )
            else:
                captions = data.get("CAPTION")
                if type(captions) is str:
                    captions = [captions]*len(data.get("FILE_ID"))
                return [
                    InlineQueryResultCachedDocument(
                        id=path+f":{index}", 
                        title=data.get("IQ_TITLE") or text, 
                        document_file_id=file_id, 
                        caption=caption, 
                    )
                    for index, (file_id, caption) in enumerate(zip(data.get("FILE_ID"), captions))
                ]
        elif data.get("TYPE") == "audio" and data.get("FILE_ID"):
            if type(data["FILE_ID"]) is str:
                return InlineQueryResultCachedDocument(
                    id=path, 
                    title=data.get("IQ_TITLE") or text, 
                    document_file_id=data.get("FILE_ID"), 
                    caption=data.get("CAPTION"), 
                )
            else:
                captions = data.get("CAPTION")
                if type(captions) is str:
                    captions = [captions]*len(data.get("FILE_ID"))
                return [
                    InlineQueryResultCachedDocument(
                        id=path+f":{index}", 
                        title=data.get("IQ_TITLE") or text, 
                        document_file_id=file_id, 
                        caption=caption, 
                    )
                    for index, (file_id, caption) in enumerate(zip(data.get("FILE_ID"), captions))
                ]

inline_query_search = InlineQuerySearch()

class EmptyProps(Exception):
    pass

class NotPermitted(Exception):
    pass
class ProtectedChannelForward(Exception):
    pass

def get_value(d: dict, keys: List[str]) -> dict:
    if keys:
        return get_value(d[keys[0]], keys[1:])
    return d

def get_path_name(data: Dict[str, Union[Dict, List]], keys: List[str]) -> str:
    names = []
    keys = keys.copy()
    while keys:
        names.append(data[keys[0]]["IK_TEXT"])
        data = data[keys[0]]
        del keys[0]
    return '\n'.join('🔻 '+name for name in names)

def generate_message_args(data: Dict[str, Union[Dict, List]], keys: List[str], is_admin: bool, bot_username: str, is_pinned: bool=False) -> Tuple[str, InlineKeyboardMarkup]:
    value = get_value(data, keys)
    if is_admin:
        keyboard = [
            [
                InlineKeyboardButton(
                    text=value[key]["IK_TEXT"], 
                    callback_data=dump_query(SPLIT_CALLBACK_QUERY.join(keys + [key]), code="get")
                ), 
                InlineKeyboardButton(
                    text=data["init"]["dialog"]["edit_data_inline_keyboard"], 
                    callback_data=dump_query(SPLIT_CALLBACK_QUERY.join(keys + [key]), code="edt")
                ), 
            ]
            for key in value if key != "IK_TEXT" and not (not keys and key=="init")
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    text=value[key]["IK_TEXT"], 
                    callback_data=dump_query(SPLIT_CALLBACK_QUERY.join(keys + [key]), code="get")
                )
            ]
            for key in value if key != "IK_TEXT" and not (not keys and key=="init")
        ]
    pin_inline_button_text = data["init"]["dialog"]["unpin_message_inline_keyboard"] if is_pinned else data["init"]["dialog"]["pin_message_inline_keyboard"]
    if not keys:
        keyboard.append([InlineKeyboardButton(
            text=pin_inline_button_text, 
            callback_data=dump_query(str(int(not is_pinned))+SPLIT_CALLBACK_QUERY, code="pin")
        )])
    elif len(keys)==1:
        keyboard.append([InlineKeyboardButton(
            text=data["init"]["dialog"]["back_to_previous_menu"], 
            callback_data=dump_query(SPLIT_CALLBACK_QUERY, code="get")
        )])
        keyboard.append([InlineKeyboardButton(
            text=pin_inline_button_text, 
            callback_data=dump_query(str(int(not is_pinned))+SPLIT_CALLBACK_QUERY.join(keys), code="pin")
        )])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text=data["init"]["dialog"]["back_to_main_menu"], 
                callback_data=dump_query(SPLIT_CALLBACK_QUERY, code="get")
            ),
            InlineKeyboardButton(
                text=data["init"]["dialog"]["back_to_previous_menu"], 
                callback_data=dump_query(SPLIT_CALLBACK_QUERY.join(keys[:-1]), code="get")
            )
        ])
        keyboard.append([InlineKeyboardButton(
            text=pin_inline_button_text, 
            callback_data=dump_query(str(int(not is_pinned))+SPLIT_CALLBACK_QUERY.join(keys), code="pin")
        )])
    if keys:
        keyboard.append([current_state_inline_button(bot_username, data["init"]["dialog"]["resend_current_state_inline_button"], keys)])
    inline_keyboard = InlineKeyboardMarkup(keyboard)
    return (
        data["init"]["dialog"]["state_text_template"].format(path=get_path_name(data, keys))
        if keys else data["init"]["dialog"]["start_title"], 
        inline_keyboard, 
    )

def current_state_inline_button(bot_username: str, text: str, keys: List[str]) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text, 
        url=f"https://t.me/{bot_username}?start={SPLIT_CALLBACK_QUERY.join(keys)}", 
    )

async def send_message_by_props(props: Dict[str, str], chat_data: dict, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    props = props.copy()
    if props["TYPE"] == "document":
        if not props.get("FILE_ID"):
            raise EmptyProps
        if isinstance(props["FILE_ID"], str):
            if not isinstance(props["CAPTION"], str):
                props["CAPTION"] = props["CAPTION"][-1] if props["CAPTION"] else ""
            await update.effective_chat.send_document(
                document=props["FILE_ID"], 
                caption=props["CAPTION"], 
            )
            return
        if isinstance(props["CAPTION"], str):
            props["CAPTION"] = ['']*(len(props["FILE_ID"])-1) + [props["CAPTION"]]
        media = [
            InputMediaDocument(media=file_id, caption=caption)
            for file_id, caption in zip(props["FILE_ID"], props["CAPTION"])
        ]
        await update.effective_chat.send_media_group(media)
    elif props["TYPE"] == "message":
        if not props.get("MESSAGE"):
            raise EmptyProps
        await update.effective_chat.send_message(
            text=props["MESSAGE"]
        )
    elif props["TYPE"] == "audio":
        if not props.get("FILE_ID"):
            raise EmptyProps
        if type(props["FILE_ID"]) is str:
            await update.effective_chat.send_audio(
                audio=props["FILE_ID"], 
                caption=props["CAPTION"], 
            )
            return
        if type(props["CAPTION"]) is str:
            props["CAPTION"] = ['']*(len(props["FILE_ID"])-1) + [props["CAPTION"]]
        media = [
            InputMediaAudio(media=file_id, caption=caption)
            for file_id, caption in zip(props["FILE_ID"], props["CAPTION"])
        ]
        await update.effective_chat.send_media_group(media)
    elif props["TYPE"] == "forward":
        if not (props.get("CHAT_ID") and props.get("MESSAGE_ID")):
            raise EmptyProps
        if chat_data and chat_data.get("strict_forward"):
            if (await context.bot.get_chat_member(
                chat_id=props.get("CHAT_ID"), 
                user_id=update.effective_user.id, 
            )).status not in JOIN_STATUS:
                raise NotPermitted
        if not isinstance(props.get("MESSAGE_ID"), list):
            props["MESSAGE_ID"] = [props.get("MESSAGE_ID")]
        try:
            await update.effective_chat.forward_messages_from(
                from_chat_id=props.get("CHAT_ID"), 
                message_ids=props.get("MESSAGE_ID"), 
            )
        except BadRequest as err:
            if err.message == "Message has protected content and can't be forwarded":
                raise ProtectedChannelForward
            else:
                raise BadRequest(err.message)

def load_query(data: str) -> str:
    return data[3:]

def dump_query(text: str, code:str) -> str:
    return code+text

def load_json(path: str) -> dict:
    data = json.load(open(path))
    inline_query_search.update_data(data)
    return data

def dump_json(path: str, data: str):
    json.dump(
        data, 
        open(path, 'w'), 
        ensure_ascii=False, 
        indent='\t'
    )

USER_DATA_TEMPLATE = {
    "first_name": "", 
    "last_name": "", 
    "username": "", 
    "permissions": {}, 
}
def cache_users_data(data: Dict, update_data: Callable):
    def get_function(func):
        async def callback_wrappper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_chat.id < 0:
                return
            user_id = str(update.effective_user.id)
            if user_id not in data["init"]["users"]:
                data["init"]["users"][user_id] = deepcopy(USER_DATA_TEMPLATE)
            data["init"]["users"][user_id]["first_name"] = update.effective_user.first_name
            data["init"]["users"][user_id]["last_name"] = update.effective_user.last_name
            data["init"]["users"][user_id]["username"] = update.effective_user.username
            dump_json(getenv("DATA_PATH"), data)
            await func(update, context)
        return callback_wrappper
    return get_function

def is_admin(user_id: int, mode: str, data: dict) -> bool:
    return data["init"]["users"][str(user_id)]["permissions"].get("admin", {}).get(mode, {})

async def is_member(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_ids: List[int]) -> bool:
    for chat_id in chat_ids:
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status in (ChatMember.LEFT, ChatMember.BANNED):
                break
        except TelegramError:
            break
    else:
        return True
    return False
