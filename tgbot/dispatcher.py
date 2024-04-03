from functools import wraps

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

from cachetools import LRUCache
from tgbot.lang import get_translate
from tgbot.types import TelegramAccount
from tgbot.handlers import not_login_handler
from tgbot.request import request, EntityType
from tgbot.utils import rate_limit, telegram_log
from tgbot.message_generator import CallBackAnswer, TextMessage
from todoapi.types import db
from todoapi.utils import is_admin_id
from todoapi.exceptions import UserNotFound, GroupNotFound
from telegram_utils.command_parser import command_regex


rate_limit_else = LRUCache(maxsize=100)
rate_limit_200_1800 = LRUCache(maxsize=100)
rate_limit_30_60 = LRUCache(maxsize=100)


def key_func(x: Message | CallbackQuery) -> int:
    return (x if isinstance(x, Message) else x.message).chat.id


@rate_limit(
    rate_limit_else,
    10,
    60,
    lambda *args, **kwargs: request.entity.user_id,
    lambda *args, **kwargs: None,
)
def else_func(args, kwargs, key, sec) -> None:
    x = kwargs.get("x") or args[0]
    text = get_translate("errors.many_attempts").format(sec)

    if isinstance(x, CallbackQuery):
        func, arg = CallBackAnswer(text).answer, x.id
    else:
        func, arg = TextMessage(text).send, key

    func(arg)


def process_account(func):
    @wraps(func)
    def check_argument(_x: Message | CallbackQuery):
        if isinstance(_x, Message):
            message = _x
            if _x.content_type != "migrate_to_chat_id" and (
                _x.text.startswith("/") and not command_regex.match(_x.text)
            ):
                # Если команда будет обращена к другим ботам, то не реагировать
                return
        elif isinstance(_x, CallbackQuery):
            message = _x.message
            if _x.data == "None":
                return
        else:
            return

        chat_id = message.chat.id

        @rate_limit(rate_limit_200_1800, 200, 60 * 30, key_func, else_func)
        @rate_limit(rate_limit_30_60, 30, 60, key_func, else_func)
        def wrapper(x: Message | CallbackQuery):
            with db.connection(), db.cursor():
                request.query = x
                request.chat_id = chat_id
                request.entity_type = EntityType(
                    user=message.chat.type == "private",
                    member=message.chat.type != "private",
                )
                try:
                    if request.is_user:
                        request.entity = TelegramAccount(chat_id)
                    else:
                        request.entity = TelegramAccount(x.from_user.id, chat_id)
                except (UserNotFound, GroupNotFound):
                    request.entity = None
                    if isinstance(x, Message):
                        telegram_log("send", message.text)
                    else:
                        telegram_log("press", x.data)

                    not_login_handler(x)
                else:
                    if request.entity.user.user_status == -1 and not is_admin_id(
                        chat_id
                    ):
                        return

                    return func(x)

        return wrapper(_x)

    return check_argument
