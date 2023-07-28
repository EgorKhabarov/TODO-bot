import os
from dotenv import load_dotenv


os.chdir(".")
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
DATABASE_PATH = os.getenv("DATABASE_PATH", "database.sqlite3")
LOG_FILE = os.getenv("LOG_FILE", "bot.log")
POKE_LINK = int(os.getenv("POKE_LINK", 0))
LINK = os.getenv("LINK")

admin_id = (1563866138,)
NOTIFICATIONS = True
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.42"
}
COMMANDS = (
    "calendar",
    "start",
    "deleted",
    "version",
    "forecast",
    "week_event_list",
    "currency",
    "weather",
    "search",
    "bell",
    "dice",
    "help",
    "settings",
    "today",
    "sqlite",
    "account",
    "files",
    "SQL",
    "save_to_csv",
    "setuserstatus",
    "id",
    "deleteuser",
    "idinfo",
    "commands",
)
callbackTab = "⠀⠀⠀"  # Специальные прозрачные символы для заполнения


__version__ = "28.07.2023"
__autor__ = "EgorKhabarov"

"""
pip install -r requirements.txt

Bot settings => Group Privacy => disabled
Bot settings => Inline Mode   => disabled
"""
