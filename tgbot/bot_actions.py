from time import time

from telebot.apihelper import ApiTelegramException  # noqa
from telebot.types import Message, CallbackQuery  # noqa

from tgbot.bot import bot
from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.buttons_utils import delmarkup
from tgbot.message_generator import TextMessage, CallBackAnswer


def delete_message_action(message: Message) -> None:
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except ApiTelegramException:
        if (time() - message.date) / 60 / 60 > 48:
            error_text = get_translate("errors.delete_messages_older_48_h")
            if isinstance(request.query, CallbackQuery):
                return CallBackAnswer(error_text).answer(request.query.id, True)
        else:
            error_text = get_translate("errors.get_permission")

        TextMessage(error_text, delmarkup()).reply(message)
