from threading import Thread

import config
from tgbot.main import bot, schedule_loop
from tgbot.bot import bot_webhook_info, bot_log_info
from todoapi.logger import logger


def start_bot():
    if not config.TELEGRAM_WEBHOOK:
        if bot_webhook_info.url:
            bot.remove_webhook()

        bot.infinity_polling()


def start_notifications_thread():
    if config.BOT_NOTIFICATIONS or config.POKE_SERVER_URL:
        Thread(target=schedule_loop, daemon=True).start()


if __name__ == "__main__":
    logger.info(bot_log_info())
    start_notifications_thread()
    start_bot()
