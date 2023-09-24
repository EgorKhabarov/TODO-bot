
# Установка

```shell
git clone https://github.com/EgorKhabarov/TODO-bot.git .
```

# Подготовка

### Linux

```shell
mv tgbot/.env.example tgbot/.env
```

### Windows

```shell
mv tgbot\.env.example tgbot\.env
```

# Скачиваем библиотеки

```shell
pip install -r requirements.txt
```

# Настройка

Изменить `.env` в директории бота.

```.env
BOT_TOKEN=        # Токен телеграм бота у t.me/BotFather
WEATHER_API_KEY=  # Получить на home.openweathermap.org/api_keys
POKE_LINK=        # Тыкать ли url сервера? (1 или 0)
LINK=             # url сервера
```

```shell
echo BOT_TOKEN=...>>tgbot\.env
```

```shell
echo WEATHER_API_KEY=...>>tgbot\.env
```

# Запуск

```shell
python main.py
```
