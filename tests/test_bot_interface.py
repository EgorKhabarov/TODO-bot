from unittest import mock

import pytest

from tgbot.handlers import command_handler
from tests.mocks import message_mock, bot_mock, db_decorator


@mock.patch("bot.bot", bot_mock)
@db_decorator
@pytest.mark.parametrize(
    "command, result",
    (
        ("/calendar", ""),
        # ("/start", ""),
        # ("/deleted", ""),
        # ("/week_event_list", ""),
        # ("/weather", ""),
        # ("/forecast", ""),
        # ("/search", ""),
        # ("/dice", ""),
        # ("/help", ""),
        # ("/settings", ""),
        # ("/today", ""),
        # ("/sqlite", ""),
        # ("/SQL ", ""),
        # ("/bell", ""),
        # ("/save_to_csv", ""),
        # ("/version", ""),
        # ("/setuserstatus", ""),
        # ("/idinfo ", ""),
        # ("/idinfo", ""),
        # ("/id", ""),
        # ("/deleteuser", ""),
        # ("/account", ""),
        # ("/commands", ""),
    ),
)
def test_bot_interface(command, result):
    message = message_mock(1, command)
    command_handler(message)
    assert bot_mock.call_args_list, result
