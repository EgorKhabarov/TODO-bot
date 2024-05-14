import shutil
from pprint import pformat
from pathlib import Path

# noinspection PyPackageRequirements
from contextvars import ContextVar
from typing import Callable

# noinspection PyPackageRequirements
from telebot import apihelper, util

# noinspection PyPackageRequirements
from telebot.types import Message

import config


class Chat:
    def __enter__(self):
        shutil.copy(test_database_copy_path, test_database_path)

        create_user("example@gmail.com", "example_username", "example_password")
        account = get_account_from_password("example_username", "example_password")
        set_user_telegram_chat_id(account, 1)

        history.set([])
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

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
{inspect.getsource(func)}
)(
*{pformat(tuple(self.history[n].values()), sort_dicts=False)}
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
        case _:
            result = ""

    return result


def setup_request(message: Message):
    request.set(message)

    if request.is_user:
        request.entity = TelegramAccount(request.chat_id)
    else:
        request.entity = TelegramAccount(message.from_user.id, request.chat_id)


apihelper.CUSTOM_REQUEST_SENDER = custom_sender


config.BOT_TOKEN = "TEST_TOKEN"
test_database_path = Path("tests/data/test_database.sqlite3")
test_database_copy_path = Path("tests/data/test_database_copy.sqlite3")
test_database_path.parent.mkdir(parents=True, exist_ok=True)
config.DATABASE_PATH = test_database_copy_path
from todoapi.db_creator import create_tables  # noqa: E402
create_tables()
config.DATABASE_PATH = test_database_path
shutil.copy(test_database_copy_path, test_database_path)

history.set([])
from todoapi.types import create_user, get_account_from_password  # noqa: E402
from tgbot.request import request  # noqa: E402
from tgbot.types import set_user_telegram_chat_id, TelegramAccount  # noqa: E402
history.set(None)
