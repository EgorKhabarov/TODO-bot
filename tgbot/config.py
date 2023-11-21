import os

from dotenv import load_dotenv

from todoapi.config import DATABASE_PATH


load_dotenv()

DATABASE_PATH = DATABASE_PATH
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
POKE_LINK = int(os.getenv("POKE_LINK", 0))
LINK = os.getenv("LINK")

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
    "weather",
    "search",
    "bell",
    "dice",
    "help",
    "settings",
    "today",
    "sqlite",
    "account",
    "SQL",
    "export",
    "setuserstatus",
    "id",
    "deleteuser",
    "idinfo",
    "commands",
)
callbackTab = "⠀⠀⠀"  # Специальные прозрачные символы для заполнения


__version__ = "22.11.2023"
__autor__ = "EgorKhabarov"

bot_settings = """
Bot settings => Group Privacy => disabled
Bot settings => Inline Mode   => disabled
"""
