import os
from pathlib import Path

import git
import yaml


config_path = "config.yaml"

if not Path(config_path).exists():
    config_path = "config.example.yaml"

with open(config_path, "r", encoding="utf-8") as file:
    config: dict = yaml.safe_load(file.read()) or {}

try:
    branch = str(git.Repo().active_branch)
except git.exc.InvalidGitRepositoryError:
    branch = "master"

DATABASE_PATH = config.get("DATABASE_PATH", "data/database.sqlite3")
VEDIS_PATH = config.get("VEDIS_PATH", "data/export_cooldown.vedis")
LOG_FILE_PATH = config.get("LOG_FILE_PATH", "logs/latest.log")

BOT_TOKEN = config.get("BOT_TOKEN", "")
WEATHER_API_KEY = config.get("WEATHER_API_KEY", "")

BOT_NOTIFICATIONS = config.get("BOT_NOTIFICATIONS", True)
LIMIT_IMAGE_GENERATOR_URL = config.get("LIMIT_IMAGE_GENERATOR_URL")

TELEGRAM_WEBHOOK = config.get("TELEGRAM_WEBHOOK", False)
TELEGRAM_WEBHOOK_URL = config.get("TELEGRAM_WEBHOOK_URL", "")
TELEGRAM_WEBHOOK_FLASK_PATH = config.get("TELEGRAM_WEBHOOK_FLASK_PATH", "")
TELEGRAM_WEBHOOK_SECRET_TOKEN = config.get("TELEGRAM_WEBHOOK_SECRET_TOKEN", "")

GITHUB_WEBHOOK = config.get("GITHUB_WEBHOOK", False)
GITHUB_WEBHOOK_FLASK_PATH = config.get("GITHUB_WEBHOOK_FLASK_PATH", "")
GITHUB_WEBHOOK_SECRET = config.get("GITHUB_WEBHOOK_SECRET", "")

__wp = config.get("WSGI_PATH")

if isinstance(DATABASE_PATH, dict):
    DATABASE_PATH = DATABASE_PATH.get(branch, "data/database.sqlite3")

if __wp:
    WSGI_PATH = Path(__wp)
else:
    if GITHUB_WEBHOOK and os.getenv("PYTHONANYWHERE_DOMAIN"):
        WSGI_PATH = Path(f"/var/www/{os.getenv('USERNAME')}_pythonanywhere_com_wsgi.py")
    else:
        WSGI_PATH = None

ADMIN_IDS = tuple(config.get("ADMIN_IDS", ()))

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.42"
}
COMMANDS = (
    "start",
    "menu",
    "calendar",
    "today",
    "weather",
    "forecast",
    "week_event_list",
    "dice",
    "export",
    "help",
    "settings",
    "commands",
    "search",
    "id",
    "clear_logs",
    "version",
    "v",
    "login",
    "signup",
    "logout",
)

ts = "\U00002800"
"""
Special transparent symbol for filling empty space in buttons
"⠀" or chr(10240) or "\\U00002800"
"""

string_branch = "" if branch == "master" else f":{branch}"
__version__ = "2024.07.06.0"
__author__ = "EgorKhabarov"
