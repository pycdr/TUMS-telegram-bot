from telegram import ChatMember

__all__ = [
    "NORMALIZE_TABLE", "NORMALIZE_ESCAPE", 
    "callback_query_path_re", "SPLIT_CALLBACK_QUERY", 
    "JOIN_STATUS", 
]

NORMALIZE_TABLE = {
    '«': '<',
    '»': '>',
    '×': 'x',
    '،': ',',
    '؟': '?',
    'آ': 'ا',
    'أ': 'ا',
    'ؤ': 'و',
    'إ': 'ا',
    'ئ': 'ی',
    'ة': 'ه',
    'ك': 'ک',
    'ي': 'ی',
    '٪': '%',
    '٫': '/',
    '٬': ',',
    '\u200c': ' ', 
}
NORMALIZE_ESCAPE = {'َ', 'ٓ', 'ـ', 'ّ', 'ِ', 'ٌ', 'ٰ', 'ٔ', 'ٍ', 'ْ', 'ً', 'ُ', 'ء'}
SPLIT_CALLBACK_QUERY = "-" # because of /start command, we prefer to use this character
callback_query_path_re = fr'\w+(?:{SPLIT_CALLBACK_QUERY}\w+)*'
JOIN_STATUS = {ChatMember.ADMINISTRATOR, ChatMember.OWNER, ChatMember.MEMBER}
