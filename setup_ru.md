<table>
    <td><a href="/setup.md">EN</a></td>
    <td><a href="/setup_ru.md">RU</a></td>
</table>

# Установка

### HTTPS

```shell
git clone https://github.com/EgorKhabarov/TODO-bot.git .
```

### SSH

```shell
git clone git@github.com:EgorKhabarov/TODO-bot.git .
```

# Подготовка

### Linux

```shell
cp config.example.yaml config.yaml
```

### Windows

```shell
copy config.example.yaml config.yaml
```

# Скачиваем библиотеки

```shell
pip install -r requirements.txt
```

# Настройка

Изменить `config.yaml` в директории бота.

```.env
BOT_TOKEN: ""        # Токен телеграм бота у https://t.me/BotFather
WEATHER_API_KEY: ""  # Получить на https://home.openweathermap.org/api_keys
```

Настроить бота в https://t.me/BotFather.

`/mybots` -> `@your_bot_username`
```
Bot Settings -> Group Privacy -> disabled
Bot Settings -> Inline Mode   -> disabled
```

# Запуск

### Бота

```shell
python start_bot.py
```

### Сервера

```shell
python -c "from server import app; app.run('0.0.0.0')"
```

# Получение прав админа

### Получите свой telegram **chat_id**.

Запустите бота и отправьте команду `/id`.
Добавьте полученный **chat_id** в `ADMIN_IDS` в `config.yaml` и перезагрузите бота.

## Важно!

**Добавляйте только chat_id личных аккаунтов (приватных чатов)!**
**Этим chat_id будет доступна приватная информация о пользователях.**

**Любое взаимодействие любого человека в телеграм-группе с ботом воспринимается как от лица группы.**

# Настройка PythonAnyWhere

- Создать веб сервер на последней доступной версии Python
- В категории `Code` изменить `Working directory` на путь до папки с `server.py`
- В категории `Security` изменить `Force HTTPS` на `Enabled`
