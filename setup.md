
# Установка

```bash
git clone https://github.com/EgorKhabarov/TODO-bot.git .
```

# Подготовка

## Linux

```bash
mv .env.example .env
mv .\todoapi\.env.example .\todoapi\.env
pip install -r requirements.txt
```

## Windows

```bash
move .env.example .env
move .\todoapi\.env.example .\todoapi\.env
pip install -r requirements.txt
```

# Настройка
Изменить `.env` в корневой директории.

```.env
BOT_TOKEN=        # Токен телеграм бота у t.me/BotFather
WEATHER_API_KEY=  # Получить на home.openweathermap.org/api_keys
POKE_LINK=        # Тыкать ли url сервера? (1 или 0)
LINK=             # url сервера
```

# Запуск
```bash
python main.py
```
