from telegram import (
    Update, Document, Audio, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, 
)
from telegram.ext import (
    ContextTypes, ConversationHandler, 
    CallbackQueryHandler, MessageHandler, 
    filters, CommandHandler
)
from typing import Callable, List

GET_PROP, CHANGE_VALUE = range(2)

def find_subdata(data: dict, path: List[str]) -> dict:
    subdata = data
    while path:
        subdata = subdata[path[0]]
        path = path[1:]
    return subdata

def create_send_props_handler(data: dict, load_query: Callable, SPLIT_CALLBACK_QUERY: str):
    async def send_props_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        path = load_query(query.data).split(SPLIT_CALLBACK_QUERY)
        context.user_data["edit"] = {}
        context.user_data["edit"]["path"] = path.copy()
        subdata = find_subdata(data, path)
        keys = [key for key in subdata.keys() if type(subdata[key]) is not dict]
        await update.effective_message.reply_text(
            data["init"]["dialog"]["edit_data_choose_key"], 
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(text=key)]
                for key in keys
            ])
        )
        return GET_PROP
    return send_props_handler

def create_get_prop_handler(data: dict):
    async def get_prop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["edit"]["key"] = update.effective_message.text
        await update.effective_message.reply_text(
            text=data["init"]["dialog"]["edit_data_get_new_value"], 
            reply_markup=ReplyKeyboardRemove()
        )
        return CHANGE_VALUE
    return get_prop_handler

def create_change_value_handler(data: dict, dump_json_data: Callable):
    async def change_value_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        subdata = find_subdata(data, context.user_data["edit"]["path"])
        key = context.user_data["edit"]["key"]
        if key == "FILE_ID":
            if update.effective_message.effective_attachment:
                subdata[key] = update.effective_message.effective_attachment.file_id
            elif update.effective_message.text:
                subdata[key] = update.effective_message.text.split('\n')
        else:
            subdata[key] = update.effective_message.text
        dump_json_data()
        await update.effective_message.reply_text(
            text=data["init"]["dialog"]["edit_data_saved_successfully"]
        )
        del context.user_data["edit"]
        return ConversationHandler.END
    return change_value_handler

def create_get_attachment_handler(data: dict):
    async def get_attachment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        attachment = update.effective_message.effective_attachment
        if "attachment" not in context.user_data["edit"]:
            context.user_data["edit"]["attachment"] = []
            context.user_data["edit"]["caption"] = []
            if isinstance(attachment, Document):
                context.user_data["edit"]["type"] = "document"
            elif isinstance(attachment, Audio):
                context.user_data["edit"]["type"] = "audio"
        if isinstance(attachment, (list, tuple)):
            attachment = attachment[0]
        context.user_data["edit"]["attachment"].append(attachment)
        context.user_data["edit"]["caption"].append(update.effective_message.caption)
        return GET_PROP
    return get_attachment_handler

def create_change_attachment_handler(data: dict, dump_json_data: Callable):
    async def change_attachment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        subdata = find_subdata(data, context.user_data["edit"]["path"])
        attachments = context.user_data["edit"]["attachment"]
        subdata["FILE_ID"] = [attach.file_id for attach in attachments]
        subdata["CAPTION"] = context.user_data["edit"]["caption"].copy()
        subdata["TYPE"] = context.user_data["edit"]["type"]
        dump_json_data()
        del context.user_data["edit"]
        await update.effective_message.reply_text(
            text=data["init"]["dialog"]["edit_data_saved_successfully"], 
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    return change_attachment_handler

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del context.user_data["edit"]
    update.effective_message.reply_text("done!")
    return ConversationHandler.END

def create_ed_handler(
    data: dict, load_query: Callable, SPLIT_CALLBACK_QUERY: str, 
    dump_json_data: Callable, 
): # sorry but i was tired with solving ImportError for `..tools`
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(create_send_props_handler(data, load_query, SPLIT_CALLBACK_QUERY), pattern=r'edt.+')], 
        states={
            GET_PROP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_get_prop_handler(data)), 
                MessageHandler(filters.ATTACHMENT, create_get_attachment_handler(data)), 
                CommandHandler("change", create_change_attachment_handler(data, dump_json_data))
            ], 
            CHANGE_VALUE: [MessageHandler(filters.ALL, create_change_value_handler(data, dump_json_data))]
        }, 
        fallbacks=[CommandHandler('cancel', cancel)]
    )
