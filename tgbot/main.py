import atexit
from time import sleep
from functools import wraps
from threading import Thread

import requests
from telebot.apihelper import ApiTelegramException  # noqa
from telebot.types import CallbackQuery, Message, BotCommandScopeDefault  # noqa

from tgbot import config
from tgbot.request import request
from tgbot.queries import queries
from tgbot.lang import get_translate
from tgbot.time_utils import now_time
from tgbot.bot import bot, bot_log_info
from tgbot.buttons_utils import delmarkup
from tgbot.handlers import command_handler, callback_handler, reply_handler, clear_state
from tgbot.bot_actions import delete_message_action
from tgbot.bot_messages import (
    search_message,
    notifications_message,
    confirm_changes_message,
)
from tgbot.utils import (
    poke_link,
    re_edit_message,
    rate_limit_requests,
    html_to_markdown,
)
from todoapi.api import User
from todoapi.types import db
from todoapi.logger import logging
from todoapi.utils import is_admin_id
from todoapi.log_cleaner import clear_logs
from todoapi.db_creator import create_tables
from telegram_utils.command_parser import command_regex


create_tables()
logging.info(bot_log_info())
bot.set_my_commands(get_translate("buttons.commands.0", "ru"), BotCommandScopeDefault())
command_regex.set_username(bot.user.username)


def check_user(func):
    @wraps(func)
    def check_argument(_x: Message | CallbackQuery):
        if isinstance(_x, Message):
            if _x.content_type != "migrate_to_chat_id" and (
                _x.text.startswith("/") and not command_regex.match(_x.text)
            ):
                return
        elif isinstance(_x, CallbackQuery):
            if _x.data == "None":
                return
        else:
            return

        @rate_limit_requests(
            200, 60 * 30, {"call.message.chat.id", "message.chat.id"}, send=True
        )
        @rate_limit_requests(
            30, 60, {"call.message.chat.id", "message.chat.id"}, send=True
        )
        def wrapper(x: Message | CallbackQuery):
            if isinstance(x, Message):
                chat_id = x.chat.id
                if x.content_type != "migrate_to_chat_id" and (
                    x.text.startswith("/") and not command_regex.match(_x.text)
                ):
                    return
            elif isinstance(x, CallbackQuery):
                chat_id = x.message.chat.id
                if x.data == "None":
                    return 0
            else:
                return

            with db.connection(), db.cursor():
                user = User(chat_id)
                if user.settings.user_status == -1 and not is_admin_id(chat_id):
                    return
                request.user = user
                request.chat_id = chat_id
                request.query = x
                res = func(x)
            return res

        return wrapper(_x)

    return check_argument


@bot.message_handler(content_types=["migrate_to_chat_id"], chat_types=["group"])
@check_user
def migrate_chat(message: Message):
    logging.info(
        f"[{message.chat.id:<10}][{request.user.settings.user_status}] "
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
@check_user
def bot_command_handler(message: Message):
    """
    Ловит команды от пользователей
    """
    request.user.settings.log("send", html_to_markdown(message.html_text))
    command_handler(message)


@bot.callback_query_handler(func=lambda call: call.data != "None")
@check_user
def bot_callback_query_handler(call: CallbackQuery):
    """
    Ловит нажатия на кнопки
    """
    request.user.settings.log("pressed", call.data)
    callback_handler(call)


@bot.message_handler(
    func=lambda m: m.text.startswith("#") and not m.text.startswith("#️⃣")
)
@check_user
def processing_search_message(message: Message):
    """
    Ловит сообщения поиска
    #   (ИЛИ)
    #!  (И)
    """
    query = html_to_markdown(message.html_text).removeprefix("#")

    request.user.settings.log("search", query)
    generated = search_message(query)
    generated.send(request.chat_id)


@bot.message_handler(func=lambda m: re_edit_message.search(m.text))
@check_user
def processing_edit_message(message: Message):
    """
    Ловит сообщения для изменения событий
    """
    request.user.settings.log("send", "edit event text")

    if confirm_changes_message(message) is None:
        delete_message_action(message)


@bot.message_handler(
    func=lambda m: (
        m.reply_to_message
        and m.reply_to_message.text
        and m.reply_to_message.from_user.id == bot.user.id
    )
)
@check_user
def processing_reply_to_message(message: Message):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    message_start = message.reply_to_message.text.split("\n", 1)[0]
    request.user.settings.log("send", f"reply {message_start}")

    reply_handler(message, message.reply_to_message)


def add_event_func(msg) -> int:
    with db.connection(), db.cursor():
        add_event_date = db.execute(queries["select add_event_date"], (msg.chat.id,))
    return add_event_date[0][0] if add_event_date else 0


@bot.message_handler(func=add_event_func)
@check_user
def add_event_handler(message: Message):
    """
    Ловит сообщение если пользователь хочет добавить событие
    """
    markdown_text = html_to_markdown(message.html_text)

    request.user.settings.log("send", "add event")

    new_event_date = db.execute(
        queries["select add_event_date"], params=(request.chat_id,)
    )[0][0].split(",")[0]

    # Если сообщение длиннее 3800 символов, то ошибка
    if len(markdown_text) >= 3800:
        message_is_too_long = get_translate("errors.message_is_too_long")
        bot.reply_to(message, message_is_too_long, reply_markup=delmarkup())
        return

    if (
        request.user.check_limit(
            new_event_date, event_count=1, symbol_count=len(markdown_text)
        )[1]
        is True
    ):
        exceeded_limit = get_translate("errors.exceeded_limit")
        bot.reply_to(message, exceeded_limit, reply_markup=delmarkup())
        return

    # Пытаемся создать событие
    if request.user.add_event(new_event_date, markdown_text)[0]:
        delete_message_action(message)
    else:
        error_translate = get_translate("errors.error")
        bot.reply_to(message, error_translate, reply_markup=delmarkup())

    clear_state(request.chat_id)


def schedule_loop():
    # ждём чтобы цикл уведомлений начинался
    def process():
        while_time = now_time()
        weekday = while_time.weekday()
        hour = while_time.hour
        minute = while_time.minute

        if config.NOTIFICATIONS and minute in (0, 10, 20, 30, 40, 50):
            Thread(target=notifications_message, daemon=True).start()

        if config.POKE_LINK and config.LINK and minute in (0, 10, 20, 30, 40, 50):
            Thread(target=poke_link, daemon=True).start()

        if weekday == hour == minute == 0:  # Monday 00:00
            Thread(target=clear_logs, daemon=True).start()

    process()
    sleep(60 - now_time().second)
    while True:
        process()
        sleep(60)


if config.POKE_LINK and config.LINK:
    atexit.register(lambda: requests.get(config.LINK))
