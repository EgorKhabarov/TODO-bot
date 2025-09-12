import os
from threading import Thread

# noinspection PyPackageRequirements
from telebot.types import Update
from flask import Flask, request, abort, send_file

import config
from todoapi.logger import logger


app = Flask(__name__)

# noinspection PyBroadException
try:
    from start_bot import start_bot, start_notifications_thread
    from tgbot.main import bot
    from tgbot.limits import create_image_from_link
    from tgbot.bot import bot_webhook_info, bot_log_info

    logger.info(bot_log_info())

    if not config.TELEGRAM_WEBHOOK:
        Thread(target=start_bot, daemon=True).start()

    if config.BOT_NOTIFICATIONS:
        start_notifications_thread()
except Exception as e:
    logger.exception(e)
    code = 503
else:
    code = 200


@app.get("/")
def home():
    if code != 200:
        return abort(code)

    return "ok"


@app.get("/favicon.ico")
def favicon():
    return send_file("icon/notepad_icon.png")


@app.get("/v")
@app.get("/version")
def version():
    return f"{config.__version__}{config.string_branch}"


@app.get("/limit")
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
    locals().get("bot")
    and config.TELEGRAM_WEBHOOK
    and config.TELEGRAM_WEBHOOK_URL
    and config.TELEGRAM_WEBHOOK_FLASK_PATH
):

    @app.post(config.TELEGRAM_WEBHOOK_FLASK_PATH)
    def process_updates():
        if request.headers.get("content-type") != "application/json":
            return abort(403)

        if secret_token := request.headers.get("X-Telegram-Bot-Api-Secret-Token", None):
            if secret_token != config.TELEGRAM_WEBHOOK_SECRET_TOKEN:
                return abort(403)

        bot.process_new_updates([Update.de_json(request.json)])
        return "ok", 200

    if bot_webhook_info.url != config.TELEGRAM_WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(
            url=config.TELEGRAM_WEBHOOK_URL,
            secret_token=config.TELEGRAM_WEBHOOK_SECRET_TOKEN or None,
        )


if config.GITHUB_WEBHOOK and config.GITHUB_WEBHOOK_FLASK_PATH:
    """
    From https://habr.com/ru/articles/457348/
    """
    import git
    import json
    import hmac
    import hashlib

    def is_valid_signature(x_hub_signature, data, private_key):
        # x_hub_signature and data are from the webhook payload
        # private key is your webhook secret
        hash_algorithm, github_signature = x_hub_signature.split("=", 1)
        algorithm = hashlib.__dict__.get(hash_algorithm)
        encoded_key = bytes(private_key, "latin-1")
        mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
        return hmac.compare_digest(mac.hexdigest(), github_signature)

    @app.post(config.GITHUB_WEBHOOK_FLASK_PATH)
    def webhook():
        if request.method != "POST":
            return 'request.method != "POST"'
        else:
            abort_code = 418
            # Do initial validations on required headers
            if (
                "X-Github-Event" not in request.headers
                or "X-Github-Delivery" not in request.headers
                or "X-Hub-Signature" not in request.headers
                or "User-Agent" not in request.headers
                or not request.headers.get("User-Agent").startswith("GitHub-Hookshot/")
            ):
                abort(abort_code)

            event = request.headers.get("X-GitHub-Event")
            if event == "ping":
                return json.dumps({"msg": "pong"})
            if event != "push":
                return json.dumps({"msg": "Wrong event type"})

            if not request.is_json:
                abort(415, "Change `Content type` to `application/json`")

            x_hub_signature = request.headers.get("X-Hub-Signature")
            # webhook content type should be application/json for request.data to have the payload
            # request.data is empty in case of x-www-form-urlencoded
            if not is_valid_signature(
                x_hub_signature,
                request.data,
                config.GITHUB_WEBHOOK_SECRET,
            ):
                print("Deploy signature failed: {sig}".format(sig=x_hub_signature))
                abort(abort_code)

            payload = request.get_json()
            if payload is None:
                print("Deploy payload is empty: {payload}".format(payload=payload))
                abort(abort_code)

            update_type, branch = payload["ref"].split("/", maxsplit=2)[1:]
            repo = git.Repo()

            if update_type != "heads" or branch != repo.active_branch.name:
                return json.dumps({"msg": f"Not {repo.active_branch.name}, ignoring"})

            pull_info = repo.remotes.origin.pull()

            if len(pull_info) == 0:
                return json.dumps({"msg": "Didn't pull any information from remote!"})
            if pull_info[0].flags > 128:
                return json.dumps({"msg": "Didn't pull any information from remote!"})

            commit_hash = pull_info[0].commit.hexsha
            print(f'build_commit = "{commit_hash}"')

            os.system("pip install -r requirements.txt")

            if config.WSGI_PATH:
                try:
                    os.system(f"touch {config.WSGI_PATH}")
                except OSError:
                    pass

            return f"Updated PythonAnywhere server to commit {commit_hash}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
