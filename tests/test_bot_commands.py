from tests.chat import Chat, setup_request

with Chat():
    from tgbot.request import request
    from tests.mocks import message_mock
    from tgbot.handlers import command_handler


def test_bot_command_start():
    with Chat() as chat:
        setup_request(message_mock(1, "/start"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("setMyCommands")
                and '"chat_id": 1' in k["params"]["scope"]
                and k["params"]["commands"]
            ),
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_command_menu():
    with Chat() as chat:
        setup_request(message_mock(1, "/menu"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_command_calendar():
    with Chat() as chat:
        setup_request(message_mock(1, "/calendar"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_command_today():
    with Chat() as chat:
        setup_request(message_mock(1, "/today"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )


# def test_bot_command_weather():
#     with Chat() as chat:
#         setup_request(message_mock(1, "/weather"))
#         command_handler(request.query)
#         assert chat.comparer(
#             lambda  m, u, k: (
#                 u.endswith("sendMessage")
#                 and k["params"]["chat_id"] == "1"
#                 and k["params"]["text"]
#             ),
#         )


# def test_bot_command_forecast():
#     with Chat() as chat:
#         setup_request(message_mock(1, "/forecast"))
#         command_handler(request.query)
#         assert chat.comparer(
#             lambda  m, u, k: (
#                 u.endswith("sendMessage")
#                 and k["params"]["chat_id"] == "1"
#                 and k["params"]["text"]
#             ),
#         )
#         chat.clear()


def test_bot_command_week_event_list():
    with Chat() as chat:
        setup_request(message_mock(1, "/week_event_list"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )


# def test_bot_command_dice():
#     with Chat() as chat:
#         setup_request(message_mock(1, "/dice"))
#         command_handler(request.query)
#         assert chat.comparer(
#             lambda m, u, k: (u.endswith("sendDice") and k["params"]["chat_id"] == 1),
#             lambda m, u, k: (
#                 u.endswith("sendMessage")
#                 and k["params"]["chat_id"] == "1"
#                 and k["params"]["text"] == "1"
#             ),
#         )


def test_bot_command_export():
    with Chat() as chat:
        setup_request(message_mock(1, "/export"))
        command_handler(request.query)

        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendChatAction")
                and k["params"]["chat_id"] == 1
                and k["params"]["action"] == "upload_document"
            ),
            lambda m, u, k: (
                u.endswith("sendDocument")
                and k["params"]["chat_id"] == 1
                and (
                    k["files"]["document"].read()
                    == "event_id,text,datetime,statuses,adding_time,recent_changes_time,history\r\n"
                )
            ),
        )


def test_bot_command_help():
    with Chat() as chat:
        setup_request(message_mock(1, "/help"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_command_settings():
    with Chat() as chat:
        setup_request(message_mock(1, "/settings"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )


def test_bot_command_logout():
    with Chat() as chat:
        setup_request(message_mock(1, "/logout"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_parameters"]
            ),
            lambda m, u, k: (
                u.endswith("setMyCommands")
                and k["params"]["commands"]
                and k["params"]["scope"]
            ),
        )


def test_bot_command_search():
    with Chat() as chat:
        setup_request(message_mock(1, "/search"))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )

        chat.clear()
        setup_request(message_mock(1, "/search ."))
        command_handler(request.query)
        assert chat.comparer(
            lambda m, u, k: (
                u.endswith("sendMessage")
                and k["params"]["chat_id"] == "1"
                and k["params"]["text"]
                and k["params"]["reply_markup"]
            ),
        )
