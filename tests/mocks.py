from unittest.mock import Mock


execute = Mock()

def _bot_mock() -> Mock:
    bot = Mock(id=1, username="bot_username")

    # Моки для методов telebot.TeleBot
    bot.edit_message_reply_markup = Mock()
    bot.edit_message_text = Mock()
    bot.send_message = Mock()
    bot.send_dice = Mock()
    bot.send_chat_action = Mock()
    bot.send_document = Mock()
    bot.send_media_group = Mock()
    bot.reply_to = Mock()
    bot.send_photo = Mock()
    bot.answer_callback_query = Mock()
    bot.delete_message = Mock()
    bot.set_my_commands = Mock()

    # Моки для хэндлеров telebot.TeleBot
    bot.callback_query_handler = Mock()
    bot.message_handler = Mock()

    bot.get_me.return_value = Mock(id=1, username="test_user")
    bot.set_commands.return_value = Mock()
    bot.log_info.return_value = Mock()
    return bot

bot_mock = _bot_mock()

settings_mock = Mock(
    user_id=1,
    lang="ru",
    sub_urls=1,
    city="Москва",
    timezone=3,
    direction="⬇️",
    user_status=0,
    notifications=1,
    notifications_time="09:00",
    direction_sql="DESC",
)

def user_mock():
    return Mock(
        id=1,
        is_bot=False,
        first_name="first_name",
        username="username",
        last_name="last_name",
        full_name="first_name last_name",
    )

chat_mock = Mock(
    id=1,
    type="private",
    title=None,
    username="username",
    first_name="first_name",
    last_name="last_name",
)

def message_mock(message_id, text, html_text=None) -> Mock:
    if html_text is None:
        html_text = text

    return Mock(
        message_id=message_id,
        from_user=user_mock(),
        chat=chat_mock(),
        content_type="text",
        text=text,
        html_text=html_text,
    )

def user_message(text, html_text=None):
    return message_mock(1, text, html_text)

def bot_message(text, html_text=None):
    return message_mock(2, text, html_text)

def session_mock():
    json_data1 = {
        "ok": True,
        "result": {
            "message_id": 1,
            "from": {
                "id": 2,
                "is_bot": True,
                "first_name": "botfirstname",
                "username": "botname"
            },
            "chat": {
                "id": 1,
                "first_name": "first_name",
                "last_name": "last_name",
                "username": "username",
                "type": "private"
            },
            "date": 1690409502,
            "text": "."
        }
    }
    json_data2 = {
        "ok": True,
        "result": {
            "id": 2,
            "is_bot": True,
            "first_name": "bot_first_name",
            "username": "botname",
            "can_join_groups": True,
            "can_read_all_group_messages": True,
            "supports_inline_queries": False
        }
    }
    json_data3 = {
        "ok": True,
        "result": {
            "id": 1,
            "is_bot": True,
            "first_name": "bot_first_name",
            "username": "botname",
            "can_join_groups": True,
            "can_read_all_group_messages": True,
            "supports_inline_queries": False,
            "message_id": 1,
            "from": {
                "id": 2,
                "is_bot": True,
                "first_name": "bot_first_name",
                "username": "botname"
            },
            "chat": {
                "id": 1,
                "first_name": "first_name",
                "last_name": "last_name",
                "username": "username",
                "type": "private"
            },
            "date": 1690409502,
            "text": "."
        }
    }

    response_mock = Mock()
    request_mock = Mock()
    session_mock = Mock()

    response_mock.json.return_value = json_data3
    request_mock.request.return_value = response_mock
    session_mock.return_value = request_mock
    # Session() == request_mock
    # Session().request() == response_mock
    return session_mock

def connect_mock(return_value: list[tuple[str | int | bytes]]):
    connect = Mock()
    cursor = Mock()
    execute = Mock()
    commit = Mock()
    fetchall = Mock(return_value=return_value)
    close = Mock()

    connect.return_value = cursor
    cursor.execute.return_value = execute
    connect.commit.return_value = commit
    cursor.fetchall.return_value = fetchall
    cursor.description.return_value = [("",) * len(return_value[0][0])]
    connect.close.return_value = close

    return connect


# def generate_mock_recursive(data):
#     if "__call__" in data:
#         mock = Mock()
#         for key, value in data["__call__"].items():
#             setattr(mock, key, generate_mock_recursive(value))
#         return mock
#     elif "__getattr__" in data:
#         mock = Mock()
#         for key, value in data["__getattr__"].items():
#             setattr(mock, key, value)
#         return mock
#     else:
#         return data
#
# def generate_mock(data):
#     return generate_mock_recursive(data)
# session_mock_ = generate_mock(
#     {
#         "__call__": {
#             "request": {
#                 "__call__": {
#                     "json": {
#                         "__call__": {
#                             "return_value": {
#                                 "ok": True
#                             }
#                         }
#                     }
#                 }
#             }
#         }
#     }
# )
