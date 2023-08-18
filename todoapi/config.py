import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", r"database\database.sqlite3")
VEDIS_PATH = os.getenv("VEDIS_PATH", r"database\export_cooldown.vedis")
LOG_FILE = os.getenv("LOG_FILE", r"database\log.log")
admin_id = (1563866138,)

__version__ = "19.08.2023"
__autor__ = "EgorKhabarov"
