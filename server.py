import os
from threading import Thread

from flask import Flask, request, abort, send_file

from tgbot.limits import create_image_from_link

import config

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


@app.route("/limit")
def limit():
    if len(str(request.args)) > 200:
        return abort(413)

    lang = request.args.get("lang")
    data = request.args.get("data")
    theme = request.args.get("theme")

    if not data:
        return abort(400)

    try:
        lst = [[int(x) for x in line.split("s")] for line in data.split("n")]
        image = create_image_from_link(lang, lst, theme)
    except ValueError as e:
        print(e)
        return abort(400)

    return send_file(image, mimetype="image/png")


if (
    config.TELEGRAM_WEBHOOK
    and config.TELEGRAM_WEBHOOK_URL
    and config.TELEGRAM_WEBHOOK_FLASK_PATH
):

    @app.route(config.TELEGRAM_WEBHOOK_FLASK_PATH, methods=["POST"])
    def process_updates():
        if request.headers.get("content-type") != "application/json":
            return abort(403)

        logging.info(f"{request.headers} {request.data}")
        bot.process_new_updates([Update.de_json(request.stream.read().decode("utf-8"))])
        return "ok", 200

    if bot_webhook_info.url != config.TELEGRAM_WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(config.TELEGRAM_WEBHOOK_URL)
