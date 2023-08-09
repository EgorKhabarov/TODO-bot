import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "..\database\database.sqlite3")
VEDIS_PATH = os.getenv("VEDIS_PATH", "..\database\export_cooldown.vedis")
admin_id = (1563866138,)

__version__ = "09.08.2023"
__autor__ = "EgorKhabarov"
