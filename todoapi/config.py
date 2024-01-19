import os

from dotenv import load_dotenv


load_dotenv("todoapi/.env")

DATABASE_PATH = os.getenv("DATABASE_PATH", r"data\database.sqlite3")
VEDIS_PATH = os.getenv("VEDIS_PATH", r"data\export_cooldown.vedis")
LOG_FILE = os.getenv("LOG_FILE", r"logs/latest.log")
TELEGRAM_WEBHOOK = int(os.getenv("TELEGRAM_WEBHOOK", 0))
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")
TELEGRAM_WEBHOOK_FLASK_PATH = os.getenv("TELEGRAM_WEBHOOK_FLASK_PATH", "")

admin_id = (1563866138,)

__version__ = "18.01.2024"
__autor__ = "EgorKhabarov"
