from threading import Thread

import config
from tgbot.main import bot
from tgbot.background_loop import start_background_loop
from tgbot.bot import bot_webhook_info, bot_log_info
from todoapi.logger import logger


def start_bot():
    if not config.TELEGRAM_WEBHOOK:
        if bot_webhook_info.url:
            bot.remove_webhook()

        bot.infinity_polling()


def start_notifications_thread():
    if config.BOT_NOTIFICATIONS:
        Thread(target=start_background_loop, daemon=True).start()


if __name__ == "__main__":
    logger.info(bot_log_info())
    start_notifications_thread()
    start_bot()
