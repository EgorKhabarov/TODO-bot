import yaml


with open("config.yaml", "r", encoding="utf-8") as file:
    config: dict = yaml.safe_load(file.read())

DATABASE_PATH = config.get("DATABASE_PATH", "data/database.sqlite3")
VEDIS_PATH = config.get("VEDIS_PATH", "data/export_cooldown.vedis")
LOG_FILE_PATH = config.get("LOG_FILE_PATH", "logs/latest.log")

BOT_TOKEN = config.get("BOT_TOKEN", "")
WEATHER_API_KEY = config.get("WEATHER_API_KEY", "")

BOT_NOTIFICATIONS = config.get("BOT_NOTIFICATIONS", True)
POKE_SERVER_URL = config.get("POKE_SERVER_URL", False)
SERVER_URL = config.get("SERVER_URL", "")
LIMIT_IMAGE_GENERATOR_URL = config.get("LIMIT_IMAGE_GENERATOR_URL")

TELEGRAM_WEBHOOK = config.get("TELEGRAM_WEBHOOK", False)
TELEGRAM_WEBHOOK_URL = config.get("TELEGRAM_WEBHOOK_URL", "")
TELEGRAM_WEBHOOK_FLASK_PATH = config.get("TELEGRAM_WEBHOOK_FLASK_PATH", "")
GITHUB_WEBHOOK = config.get("GITHUB_WEBHOOK", False)
GITHUB_WEBHOOK_URL = config.get("GITHUB_WEBHOOK_URL", "")

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
    "login",
    "signup",
    "logout",
)

ts = chr(10240)  # transparent symbol
"""Специальный прозрачный символ для заполнения пустого места в кнопках"""

__version__ = "09.04.2024"
__autor__ = "EgorKhabarov"
