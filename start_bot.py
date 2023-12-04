# TODO Убрать если https://github.com/eternnoir/pyTelegramBotAPI/pull/2083 будет добавлен
from unittest import mock
from telegram_utils.patch import PathedMessage


with mock.patch("telebot.types.Message", PathedMessage):

    from threading import Thread

    from tgbot import config
    from tgbot.bot import bot
    from tgbot.main import schedule_loop

    if __name__ == "__main__":
        if config.NOTIFICATIONS or config.POKE_LINK:
            Thread(target=schedule_loop, daemon=True).start()

        bot.infinity_polling()
