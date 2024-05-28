<table>
    <td><a href="/docs/setup.md">EN</a></td>
    <td><a href="/docs/setup_ru.md">RU</a></td>
</table>

# Download

### HTTPS

```shell
git clone https://github.com/EgorKhabarov/TODO-bot.git
```

### SSH

```shell
git clone git@github.com:EgorKhabarov/TODO-bot.git
```

# cd

```shell
cd TODO-bot
```

# Preparation

### Linux

```shell
cp config.example.yaml config.yaml
```

### Windows

```shell
copy config.example.yaml config.yaml
```

# Downloading libraries

```shell
pip install -r requirements.txt
```

# Settings

Edit `config.yaml` in the bot directory.

```.env
BOT_TOKEN: ""        # Telegram bot token from https://t.me/BotFather
WEATHER_API_KEY: ""  # Get it from https://home.openweathermap.org/api_keys
```

Set up a bot at https://t.me/BotFather.

`/mybots` -> `@your_bot_username`
```
Bot Settings -> Group Privacy -> disabled
Bot Settings -> Inline Mode   -> disabled
```

# Launch

### Bot

```shell
python start_bot.py
```

### Server

```shell
python -c "from server import app; app.run('0.0.0.0')"
```

# Getting administrator rights

### Get your telegram **chat_id**.

Launch the bot and send the command `/id`.
Add the resulting **chat_id** to `ADMIN_IDS` in `config.yaml` and restart the bot.

## Important!

**Add only chat_id of personal accounts (private chats)!**
**Private information about users will be available with this chat_id.**

**Any interaction of any person in a telegram group with a bot is perceived as on behalf of the group.**

# Setting up PythonAnyWhere

- Create a web server using the latest available version of Python
- In the `Code` category change `Working directory` to the path to the folder with `server.py`
- In the `Security` category change `Force HTTPS` to `Enabled`

# Docker

```shell
docker build -t todo-bot .
docker volume create todo-bot-data
docker volume create todo-bot-logs
docker run -p 5000:5000 -v todo-bot-data:/app/data -v todo-bot-logs:/app/logs --name todo-bot-container todo-bot
```
