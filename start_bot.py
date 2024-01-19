# TODO Убрать если https://github.com/eternnoir/pyTelegramBotAPI/pull/2083 будет добавлен
from unittest import mock
from telegram_utils.patch import PathedMessage


with mock.patch("telebot.types.Message", PathedMessage):
    from threading import Thread

    from tgbot.bot import bot, bot_webhook_info
    from tgbot.main import schedule_loop
    from tgbot import config as tgbot_config
    from todoapi import config as todoapi_config

    if __name__ == "__main__":
        if tgbot_config.NOTIFICATIONS or tgbot_config.POKE_LINK:
            Thread(target=schedule_loop, daemon=True).start()

        if not todoapi_config.TELEGRAM_WEBHOOK:
            if not bot_webhook_info.url:
                bot.remove_webhook()
            bot.infinity_polling()
