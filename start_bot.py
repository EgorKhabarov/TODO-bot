# TODO Убрать если https://github.com/eternnoir/pyTelegramBotAPI/pull/2083 будет добавлен
from unittest import mock
from telegram_utils.patch import PathedMessage, PathedTextQuote


with (
    mock.patch("telebot.types.Message", PathedMessage),
    mock.patch("telebot.types.TextQuote", PathedTextQuote),
):
    from threading import Thread

    import config
    from tgbot.bot import bot, bot_webhook_info
    from tgbot.main import schedule_loop

    if __name__ == "__main__":
        if config.BOT_NOTIFICATIONS or config.POKE_SERVER_URL:
            Thread(target=schedule_loop, daemon=True).start()

        if not config.TELEGRAM_WEBHOOK:
            if not bot_webhook_info.url:
                bot.remove_webhook()
            bot.infinity_polling()
