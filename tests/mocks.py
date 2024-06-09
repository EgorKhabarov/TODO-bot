from telebot.types import Message, CallbackQuery, User, Chat


def message_mock(message_id: int, text: str, html_text=None) -> Message:
    if html_text is None:
        html_text = text

    return Message(
        message_id=message_id,
        from_user=User(
            id=1,
            is_bot=False,
            first_name="first_name",
            username="username",
            last_name="last_name",
            full_name="first_name last_name",
        ),
        date=100,
        chat=Chat(
            id=1,
            type="private",
            title=None,
            username="username",
            first_name="first_name",
            last_name="last_name",
        ),
        content_type="text",
        options={"text": text},
        json_string="",
    )


def callback_mock(
    data: str, message: Message = message_mock(1, "message text")
) -> CallbackQuery:
    return CallbackQuery(
        id=100,
        from_user=User(
            id=1,
            is_bot=False,
            first_name="first_name",
            username="username",
            last_name="last_name",
            full_name="first_name last_name",
        ),
        data=data,
        chat_instance="",
        json_string="",
        message=message,
        inline_message_id=100,
    )
