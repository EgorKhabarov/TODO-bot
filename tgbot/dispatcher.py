import json
import traceback
from sqlite3 import Error
from functools import wraps
from ast import literal_eval
from typing import Callable

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException
from cachetools import LRUCache

from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.utils import telegram_log
from tgbot.types import TelegramAccount
from tgbot.handlers import not_login_handler
from tgbot.message_generator import CallBackAnswer, TextMessage
from todoapi.types import db
from todoapi.logger import logger
from todoapi.utils import is_admin_id, rate_limit
from todoapi.exceptions import UserNotFound, GroupNotFound, ApiError
from telegram_utils.command_parser import command_regex


rate_limit_else = LRUCache(maxsize=100)
rate_limit_200_1800 = LRUCache(maxsize=100)
rate_limit_30_60 = LRUCache(maxsize=100)


def key_func(func: Callable, x: Message | CallbackQuery) -> int:
    return (x if isinstance(x, Message) else x.message).chat.id


@rate_limit(
    rate_limit_else,
    10,
    60 * 2,
    lambda *args, **kwargs: request.chat_id,
    lambda *args, **kwargs: None,
)
def else_func(args, kwargs, key, sec) -> None:  # noqa
    x = kwargs.get("x") or args[1]
    text = get_translate("errors.many_attempts").format(sec)

    if isinstance(x, CallbackQuery):
        CallBackAnswer(text).answer()
    else:
        TextMessage(text).send()


@rate_limit(rate_limit_200_1800, 200, 60 * 30, key_func, else_func)
@rate_limit(rate_limit_30_60, 30, 60, key_func, else_func)
def wrapper(func: Callable, x: Message | CallbackQuery):
    try:
        try:
            if request.is_user:
                request.entity = TelegramAccount(request.chat_id)
            else:
                request.entity = TelegramAccount(x.from_user.id, request.chat_id)
        except (UserNotFound, GroupNotFound):
            request.entity = None

            if request.is_message:
                telegram_log("send", request.message.text[:40])
            else:
                telegram_log("press", x.data)

            not_login_handler(x)
        else:
            if (
                request.entity.user.user_status == -1
                if request.is_user
                else request.entity.group.member_status == -1
            ) and not is_admin_id(request.chat_id):
                return

            return func(x)
    except (ApiError, ApiTelegramException):
        logger.error(traceback.format_exc())
        text = get_translate("errors.error")

        if request.is_callback:
            CallBackAnswer(text).answer()
        else:
            TextMessage(text).send()


def process_account(func):
    @wraps(func)
    def check_argument(_x: Message | CallbackQuery):
        request.set(_x)
        with db.connection(), db.cursor():
            if request.is_message:
                try:
                    db.execute(
                        """
INSERT OR IGNORE INTO chats (
    id,
    type,
    title,
    username,
    first_name,
    last_name,
    bio,
    is_forum,
    json
)
VALUES (
    :id,
    :type,
    :title,
    :username,
    :first_name,
    :last_name,
    :bio,
    :is_forum,
    :json
);
""",
                        {
                            "id": request.chat_id,
                            "type": _x.chat.type,
                            "title": _x.chat.title,
                            "username": _x.chat.username,
                            "first_name": _x.chat.first_name,
                            "last_name": _x.chat.last_name,
                            "bio": _x.chat.bio,
                            "is_forum": bool(_x.chat.is_forum),
                            "json": json.dumps(
                                {
                                    k: v
                                    for k, v in literal_eval(str(_x.chat)).items()
                                    if v
                                },
                                ensure_ascii=False,
                            ),
                        },
                        commit=True,
                    )
                except Error as e:
                    print(type(e), e)  # TODO

            if request.is_message:
                if request.query.content_type != "migrate_to_chat_id" and (
                    request.query.text.startswith("/")
                    and not command_regex.match(_x.text)
                ):
                    # If the command is addressed to other bots, then do not respond
                    return
            elif request.is_callback:
                if request.query.data == "None":
                    return
            else:
                return

            return wrapper(func, _x)

    return check_argument
