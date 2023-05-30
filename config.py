import os

os.chdir(".")
database_path = "database.sqlite3"
admin_id = (1563866138, )
hours_difference = 4  # Разница времени для логов (на хостинге другой часовой пояс)
bot_token = "https://t.me/BotFather"
weather_api_key = "https://home.openweathermap.org/users/sign_in"
notifications = True
log_file = "bot.log"
link = "https://example.com"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.42"
}

__version__ = "30.05.2023"
__autor__ = "EgorKhabarov"

"""
Bot settings => Group Privacy => disabled
Bot settings => Inline Mode   => disabled
"""
