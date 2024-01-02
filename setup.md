
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
move tgbot\.env.example tgbot\.env
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

Настроить бота в https://t.me/BotFather.

`/mybots` -> `@your_bot_username`
```
Bot Settings -> Group Privacy -> disabled
Bot Settings -> Inline Mode   -> disabled
```

# Запуск

```shell
python start_bot.py
```

# Получение прав админа

Получить свой telegram **chat_id**.

Запустить бота и отправить команду `/id`.
Добавить полученный **user_id** в `todoapi/config.py` `admin_id` и перезагрузить бота.

## Важно!
**Добавляйте только chat_id личных аккаунтов (приватных чатов)!
Этим chat_id будет доступна приватная информация о пользователях.

Любое взаимодействие любого человека в телеграм-группе с ботом воспринимается как от лица группы.**

# Настройка PythonAnyWhere

- Создать веб сервер на последней доступной версии Python
- В категории `Code` изменить `Working directory` на путь до папки с `server.py`
- В категории `Security` изменить `Force HTTPS` на `Enabled`
