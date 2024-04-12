import logging
import traceback
from functools import wraps

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

from cachetools import LRUCache
from tgbot.lang import get_translate
from tgbot.utils import telegram_log
from tgbot.types import TelegramAccount
from tgbot.handlers import not_login_handler
from tgbot.request import request, EntityType, QueryType
from tgbot.message_generator import CallBackAnswer, TextMessage
from todoapi.types import db
from todoapi.utils import is_admin_id, rate_limit
from todoapi.exceptions import UserNotFound, GroupNotFound, ApiError
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
        request.query = _x
        request.query_type = QueryType(
            message=isinstance(_x, Message),
            callback=isinstance(_x, CallbackQuery),
        )
        if request.is_message:
            message = _x
            if _x.content_type != "migrate_to_chat_id" and (
                _x.text.startswith("/") and not command_regex.match(_x.text)
            ):
                # Если команда будет обращена к другим ботам, то не реагировать
                return
        elif request.is_callback:
            message = _x.message
            if _x.data == "None":
                return
        else:
            return

        request.chat_id = chat_id = message.chat.id
        request.entity_type = EntityType(
            user=message.chat.type == "private",
            member=message.chat.type != "private",
        )

        @rate_limit(rate_limit_200_1800, 200, 60 * 30, key_func, else_func)
        @rate_limit(rate_limit_30_60, 30, 60, key_func, else_func)
        def wrapper(x: Message | CallbackQuery):
            with db.connection(), db.cursor():
                try:
                    try:
                        if request.is_user:
                            request.entity = TelegramAccount(chat_id)
                        else:
                            request.entity = TelegramAccount(x.from_user.id, chat_id)
                    except (UserNotFound, GroupNotFound):
                        request.entity = None

                        if request.is_message:
                            telegram_log("send", message.text[:40])
                        else:
                            telegram_log("press", x.data)

                        not_login_handler(x)
                    else:
                        if request.entity.user.user_status == -1 and not is_admin_id(
                            chat_id
                        ):
                            return

                        return func(x)
                except (ApiError, ApiTelegramException):
                    logging.error(traceback.format_exc())
                    text = get_translate("errors.error")

                    if request.is_callback:
                        CallBackAnswer(text).answer(x.id)
                    else:
                        TextMessage(text).send(chat_id)

        return wrapper(_x)

    return check_argument
