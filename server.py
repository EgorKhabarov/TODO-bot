from threading import Thread

from flask import Flask


Thread(target=lambda: __import__("os").system("python tgbot\main.py")).start()

app = Flask(__name__)


@app.route("/")
def home():
    return "200"
