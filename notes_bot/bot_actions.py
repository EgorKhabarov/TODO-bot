from time import time

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

from notes_bot.bot import bot
from notes_bot.request import request
from notes_bot.lang import get_translate
from notes_bot.buttons_utils import delmarkup
from notes_bot.message_generator import TextMessage, CallBackAnswer


def delete_message_action(message: Message) -> None:
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except ApiTelegramException:
        if (time() - message.date) / 60 / 60 > 48:
            error_text = get_translate("errors.delete_messages_older_48_h")
            error_text = error_text.replace("<b>", "").replace("</b>", "")
            if isinstance(request.query, CallbackQuery):
                return CallBackAnswer(error_text).answer(show_alert=True)
        else:
            error_text = get_translate("errors.get_permission")

        TextMessage(error_text, delmarkup()).reply()
