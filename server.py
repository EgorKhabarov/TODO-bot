from flask import Flask
from threading import Thread

Thread(target=lambda: __import__("os").system("python tgbot\main.py")).start()

app = Flask(__name__)


@app.route("/")
def home():
    return "200"
