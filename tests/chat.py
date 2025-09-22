import os
from pprint import pformat
from pathlib import Path

# noinspection PyPackageRequirements
from contextvars import ContextVar

# noinspection PyPackageRequirements
from telebot import apihelper, util

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

from typing import Callable
from sqlalchemy import create_engine

import config
import notes_api.types


class Chat:
    def __init__(self):
        self.conn = None

    def __enter__(self):
        self.conn = notes_api.types.db.connect()
        self.conn.__enter__()
        history.set([])
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.conn.__exit__(exc_type, exc_val, exc_tb)

    def comparer(
        self,
        *funcs: Callable[[str, str, dict[str, str | int | dict[str, str | int]]], bool],
    ):
        length: int = len(funcs)
        assert (
            len(self.history) == length
        ), f"""
len(
{pformat(self.history, sort_dicts=False)}
) != {length}
"""

        for n, func in enumerate(funcs):
            import inspect

            assert func(
                *self.history[n].values()
            ), f"""
(
    {ljust(inspect.getsource(func))}
)(
    *{ljust(pformat(tuple(self.history[n].values()), sort_dicts=False), 5)}
)"""

        return True

    def clear(self) -> None:
        self.history.clear()

    @property
    def history(self) -> list[dict]:
        return history.get()  # type: ignore


history = ContextVar("history")


def custom_sender(method, url, **kwargs):
    history.get().append({"method": method, "url": url, "kwargs": kwargs})
    request_method = url.rsplit("/", maxsplit=1)[-1]

    match request_method:
        case "getWebhookInfo":
            result = util.CustomRequestResponse(
                '{"ok":true,"result":{"url":null,"has_custom_certificate":null,'
                '"pending_update_count":null}}'
            )
        case "getMe":
            result = util.CustomRequestResponse(
                '{"ok":true,"result":{"id":0,"is_bot":true,'
                '"first_name":"bot","username":"test_bot"}}'
            )
        case "sendDice":
            result = util.CustomRequestResponse(
                '{"ok":true,"result":{"text":"ok","message_id":1,"date":1,'
                '"chat":{"id":1,"type":"private"},"dice":{"value":1,"emoji":"🎲"}}}'
            )
        case "setMyCommands":
            result = util.CustomRequestResponse('{"ok":true,"result":{"text":"ok"}}')
        case "answerCallbackQuery":
            result = util.CustomRequestResponse('{"ok":true,"result":{"text":"ok"}}')
        case "sendChatAction":
            result = util.CustomRequestResponse('{"ok":true,"result":{"text":"ok"}}')
        case "sendDocument":
            result = util.CustomRequestResponse(
                '{"ok":true,"result":{"text":"ok","message_id":1,"date":1,'
                '"chat":{"id":1,"type":"private"}}}'
            )
        case "sendMessage":
            result = util.CustomRequestResponse(
                '{"ok":true,"result":{"message_id":1,"date":1,'
                '"chat":{"id":1,"type":"private"}}}'
            )
        case "editMessageText":
            result = util.CustomRequestResponse(
                '{"ok":true,"result":{"text":"ok","message_id":1,"date":1,'
                '"chat":{"id":1,"type":"private"}}}'
            )
        case "deleteMessage":
            result = util.CustomRequestResponse(
                '{"ok":true,"result":{"message_id":1,"date":1,'
                '"chat":{"id":1,"type":"private"}}}'
            )
        case _:
            result = ""

    return result


def setup_request(x: Message | CallbackQuery):
    request.set(x)

    if request.is_user:
        request.entity = TelegramAccount(request.chat_id)
    else:
        request.entity = TelegramAccount(x.from_user.id, request.chat_id)


def ljust(text: str, indent: int = 4) -> str:
    return f"\n{' ' * indent}".join(text.splitlines()).lstrip(" ")


apihelper.CUSTOM_REQUEST_SENDER = custom_sender


config.BOT_TOKEN = "0:TEST_TOKEN"

test_database_path = Path("tests/data/test_database.sqlite3")
test_database_path.parent.mkdir(parents=True, exist_ok=True)

if test_database_path.exists():
    os.remove(test_database_path)

config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{test_database_path}"
notes_api.types.engine = create_engine(config.SQLALCHEMY_DATABASE_URI, echo=False)
notes_api.types.db = notes_api.types.DataBase()

from notes_api.db_creator import create_tables  # noqa: E402

create_tables()
history.set([])

if True:  # noqa: E402  # import not at top of file
    from notes_api.types import create_user, get_account_from_password
    from notes_bot.request import request
    from notes_bot.types import set_user_telegram_chat_id, TelegramAccount

with notes_api.types.db.connect():
    create_user("example@gmail.com", "example_username", "example_password")
    account = get_account_from_password("example_username", "example_password")
    set_user_telegram_chat_id(account, 1)

notes_api.types.db.execute_ = notes_api.types.db.execute
notes_api.types.db.execute = lambda *args, **kwargs: notes_api.types.db.execute_(
    *args, **{**kwargs, "commit": False}
)

history.set(None)
