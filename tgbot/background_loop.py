from time import sleep
from threading import Thread
from datetime import datetime, timezone

import config
from tgbot.bot_messages import send_notifications_messages
from notes_api.log_cleaner import clear_logs


def start_background_loop():
    def process():
        while_time = datetime.now(timezone.utc)
        weekday = while_time.weekday()
        hour = while_time.hour
        minute = while_time.minute

        if config.BOT_NOTIFICATIONS and minute in (0, 10, 20, 30, 40, 50):
            Thread(target=send_notifications_messages, daemon=True).start()

        if weekday == hour == minute == 0:  # Monday 00:00
            Thread(target=clear_logs, daemon=True).start()

    process()
    # wait for the notification cycle to start
    sleep(60 - datetime.now(timezone.utc).second)
    while True:
        process()
        sleep(60)
