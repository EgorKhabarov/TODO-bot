import os
from threading import Thread

from flask import Flask, request, abort

from todoapi import config

if config.TELEGRAM_WEBHOOK:
    import logging

    # noinspection PyPackageRequirements
    from telebot.types import Update
    from tgbot.main import bot
    from tgbot.bot import bot_webhook_info


Thread(target=os.system, args=("python start_bot.py",)).start()
app = Flask(__name__)


@app.route("/")
def home():
    return "200", 200


if (
    config.TELEGRAM_WEBHOOK
    and config.TELEGRAM_WEBHOOK_URL
    and config.TELEGRAM_WEBHOOK_FLASK_PATH
):

    @app.route(config.TELEGRAM_WEBHOOK_FLASK_PATH, methods=["POST"])
    def process_updates():
        if request.headers.get("content-type") != "application/json":
            return abort(403)

        update = Update.de_json(request.json)
        # Пока сервер просыпался, телеграм мог успеть прислать
        # один и тот же update несколько раз
        # Для защиты от этого применяется атрибут функции
        if (not hasattr(process_updates, "last_update_id")) or (
            update.update_id > process_updates.last_update_id
        ):
            process_updates.last_update_id = update.update_id
        else:
            return  # ?

        logging.info(f"{request.headers} {request.data}")
        bot.process_new_updates([update])
        return "ok", 200

    if bot_webhook_info.url != config.TELEGRAM_WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(config.TELEGRAM_WEBHOOK_URL)
