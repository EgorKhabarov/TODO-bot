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
    repo = git.Repo()
    try:
        branch = repo.active_branch.name
    except TypeError:
        branch = repo.head.commit.hexsha[:8]
except git.exc.InvalidGitRepositoryError:
    branch = "master"

SQLALCHEMY_DATABASE_URI = config.get("SQLALCHEMY_DATABASE_URI", "sqlite:///data/database.sqlite3")
LOG_FILE_PATH = config.get("LOG_FILE_PATH", "logs/latest.log")

BOT_TOKEN = config.get("BOT_TOKEN", "")
WEATHER_API_KEY = config.get("WEATHER_API_KEY", "")

MIN_CALENDAR_YEAR: int = int(config.get("MIN_CALENDAR_YEAR", 1900))
MAX_CALENDAR_YEAR: int = int(config.get("MAX_CALENDAR_YEAR", 2300))

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

if isinstance(SQLALCHEMY_DATABASE_URI, dict):
    try:
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI[branch]
    except KeyError:
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI["master"]

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
    "account",
    "groups",
    "commands",
    "search",
    "id",
    "clear_logs",
    "version",
    "v",
    "login",
    "signup",
    "logout",
    "open",
)

ts = "\u2800"
"""
Special transparent symbol for filling empty space in buttons
"⠀" or chr(10240) or "\\u2800"
"""

sql_order_dict = {
    "usual": """
ABS(DAYS_BEFORE_EVENT(date, statuses)) ASC, -- Близость к текущему дню
DAYS_BEFORE_EVENT(date, statuses) DESC,    -- Будущие события перед прошедшими
CASE
    WHEN statuses LIKE '%🟥%' THEN 1
    WHEN statuses LIKE '%📬%' THEN 2
    WHEN statuses LIKE '%🗞%' THEN 3
    WHEN statuses LIKE '%📅%' THEN 4
    WHEN statuses LIKE '%📆%' THEN 5
    WHEN statuses LIKE '%🎉%' THEN 6
    WHEN statuses LIKE '%🎊%' THEN 7
    ELSE 8
END ASC, -- Приоритет статусов
IFNULL(recent_changes_time, adding_time) DESC,
event_id DESC -- Если параметры совпадают, сортировать по большему event_id
""",
    "day": """
CASE
    WHEN statuses LIKE '%🟥%' THEN 1
    WHEN statuses LIKE '%📬%' THEN 2
    WHEN statuses LIKE '%🗞%' THEN 3
    WHEN statuses LIKE '%📅%' THEN 4
    WHEN statuses LIKE '%📆%' THEN 5
    WHEN statuses LIKE '%🎉%' THEN 6
    WHEN statuses LIKE '%🎊%' THEN 7
    ELSE 8
END ASC, -- Приоритет статусов
IFNULL(recent_changes_time, adding_time) DESC,
event_id DESC -- Если параметры совпадают, сортировать по большему event_id
""",
    "event_id": """
event_id ASC
""",
    "recent_changes_time": """
recent_changes_time ASC
""",
}

string_branch = "" if branch == "master" else f":{branch}"
__version__ = "2025.09.20.4"
__author__ = "EgorKhabarov"
