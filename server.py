import os
from threading import Thread

from flask import Flask


Thread(target=os.system, args=("python tgbot\main.py",)).start()

app = Flask(__name__)


@app.route("/")
def home():
    return "200"
