import atexit
from time import sleep
from threading import Thread

import requests

# noinspection PyPackageRequirements
from telebot.types import CallbackQuery, Message, BotCommandScopeDefault

import config
from tgbot.dispatcher import process_account
from tgbot.request import request
from tgbot.queries import queries
from tgbot.lang import get_translate
from tgbot.time_utils import now_time
from tgbot.bot import bot, bot_log_info
from tgbot.buttons_utils import delmarkup
from tgbot.bot_actions import delete_message_action
from tgbot.utils import poke_link, re_edit_message, html_to_markdown
from tgbot.handlers import command_handler, callback_handler, reply_handler, add_event_date
from tgbot.bot_messages import (
    search_message,
    send_notifications_messages,
    confirm_changes_message,
)
from todoapi.types import db
from todoapi.logger import logging
from todoapi.log_cleaner import clear_logs
from todoapi.db_creator import create_tables
from telegram_utils.command_parser import command_regex


create_tables()
logging.info(bot_log_info())
# bot.set_my_commands(get_translate("buttons.commands.0.user", "ru"), BotCommandScopeDefault())
command_regex.set_username(bot.user.username)


def telegram_log(action: str, text: str):
    text = text.replace("\n", "\\n")
    thread_id = getattr(request.query, "message", request.query).message_thread_id
    logging.info(
        f"[{str(request.entity_type).capitalize()}]"
        + f"[{request.entity.request_chat_id:<10}"
        + (f":{thread_id}" if thread_id else "")
        + f"]"
        + (f"[{request.entity.user_status}]" if request.is_user else "")
        + f"[{action:<7}] {text}"
    )


@bot.message_handler(content_types=["migrate_to_chat_id"], chat_types=["group"])
@process_account
def migrate_chat(message: Message):
    logging.info(
        f"[{message.chat.id:<10}][{request.entity.user_status}] "
        f"migrate_to_chat_id {message.migrate_to_chat_id}"
    )
    params = {
        "from_chat_id": message.chat.id,
        "to_chat_id": message.migrate_to_chat_id,
    }
    db.execute(
        queries["update settings_migrate_chat_id"],
        params=params,
        commit=True,
    )
    db.execute(
        queries["update events_migrate_chat_id"],
        params=params,
        commit=True,
    )
    bot.send_message(
        message.migrate_to_chat_id,
        get_translate("text.migrate").format(**params),
        reply_markup=delmarkup(),
    )


@bot.message_handler(commands=[*config.COMMANDS])
@process_account
def bot_command_handler(message: Message):
    """
    Ловит команды от пользователей
    """
    telegram_log("send", html_to_markdown(message.html_text))
    command_handler(message)


@bot.callback_query_handler(func=lambda call: call.data != "None")
@process_account
def bot_callback_query_handler(call: CallbackQuery):
    """
    Ловит нажатия на кнопки
    """
    telegram_log("pressed", call.data)
    callback_handler(call)


@bot.message_handler(
    func=lambda m: m.text.startswith("#") and not m.text.startswith("#️⃣")
)
@process_account
def processing_search_message(message: Message):
    """
    Ловит сообщения поиска
    #   (ИЛИ)
    #!  (И)
    """
    query = html_to_markdown(message.html_text).removeprefix("#")
    telegram_log("search", query)
    generated = search_message(query)
    generated.send(request.chat_id)


@bot.message_handler(func=lambda m: re_edit_message.search(m.text))
@process_account
def processing_edit_message(message: Message):
    """
    Ловит сообщения для изменения событий
    """
    telegram_log("send", "edit event text")
    if confirm_changes_message(message) is None:
        delete_message_action(message)


@bot.message_handler(
    func=lambda m: (
        m.reply_to_message
        and m.reply_to_message.text
        and m.reply_to_message.from_user.id == bot.user.id
    )
)
@process_account
def processing_reply_to_message(message: Message):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    message_start = message.reply_to_message.text.split("\n", 1)[0]
    telegram_log("send", f"reply {message_start}")
    reply_handler(message, message.reply_to_message)


@process_account
def add_event_func(msg) -> int:
    with db.connection(), db.cursor():
        return add_event_date()  # db.execute(queries["select add_event_date"], (msg.chat.id,))


@bot.message_handler(func=add_event_func)
@process_account
def add_event_handler(message: Message):
    """
    Ловит сообщение если пользователь хочет добавить событие
    """
    markdown_text = html_to_markdown(message.html_text)
    telegram_log("send", "add event")
    new_event_date = add_event_date().split(",")[0]

    # Если сообщение длиннее 3800 символов, то ошибка
    if len(markdown_text) >= 3800:
        message_is_too_long = get_translate("errors.message_is_too_long")
        bot.reply_to(message, message_is_too_long, reply_markup=delmarkup())
        return

    if request.entity.limit.is_exceeded_for_events(
        date=new_event_date, event_count=1, symbol_count=len(markdown_text)
    ):
        exceeded_limit = get_translate("errors.exceeded_limit")
        bot.reply_to(message, exceeded_limit, reply_markup=delmarkup())
        return

    # Пытаемся создать событие
    if request.entity.create_event(new_event_date, markdown_text):
        delete_message_action(message)
    else:
        error_translate = get_translate("errors.error")
        bot.reply_to(message, error_translate, reply_markup=delmarkup())

    add_event_date("")


def schedule_loop():
    # ждём чтобы цикл уведомлений начинался
    def process():
        while_time = now_time()
        weekday = while_time.weekday()
        hour = while_time.hour
        minute = while_time.minute

        if config.BOT_NOTIFICATIONS and minute in (0, 10, 20, 30, 40, 50):
            Thread(target=send_notifications_messages, daemon=True).start()

        if (
            config.POKE_SERVER_URL
            and config.SERVER_URL
            and minute in (0, 10, 20, 30, 40, 50)
        ):
            Thread(target=poke_link, daemon=True).start()

        if weekday == hour == minute == 0:  # Monday 00:00
            Thread(target=clear_logs, daemon=True).start()

    process()
    sleep(60 - now_time().second)
    while True:
        process()
        sleep(60)


if config.POKE_SERVER_URL and config.SERVER_URL:
    atexit.register(lambda: requests.get(config.SERVER_URL))
