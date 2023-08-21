import re
from time import sleep
from functools import wraps
from threading import Thread

from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery, Message, BotCommandScopeDefault

import config
from lang import get_translate
from bot import bot, bot_log_info
from time_utils import now_time
from message_generator import NoEventMessage
from bot_actions import (
    delete_message_action,
    confirm_changes_message,
    update_message_action,
)
from buttons_utils import delmarkup
from utils import poke_link, re_edit_message
from handlers import command_handler, callback_handler, clear_state
from bot_messages import search_message, notifications_message, settings_message
from todoapi.types import db
from todoapi.logger import logging
from todoapi.api import User, re_date
from todoapi.db_creator import create_tables
from todoapi.utils import to_html_escaping, html_to_markdown, is_admin_id

create_tables()

logging.info(bot_log_info())

bot.set_my_commands(get_translate("0_command_list", "ru"), BotCommandScopeDefault())


def check_user(func):
    @wraps(func)
    # @rate_limit_requests(100, 60 * 20, {"x.message.chat.id", "x.chat.id"})
    def wrapper(x: Message | CallbackQuery):
        if isinstance(x, Message):
            chat_id = x.chat.id
            if (
                x.chat.type != "private"
                and x.text.startswith("/")
                and x.text[1:].split("@")[0].split(" ")[0]
                and x.text.split("@")[-1].split(" ")[0] != bot.username
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

            res = func(x, user)
        return res

    return wrapper


@bot.message_handler(commands=[*config.COMMANDS])
@check_user
def message_handler(message: Message, user: User):
    """
    Ловит команды от пользователей
    """
    user.settings.log("send", message.text)

    command_handler(user, message)


@bot.callback_query_handler(func=lambda call: True)
@check_user
def callback_query_handler(call: CallbackQuery, user: User):
    """
    Ловит нажатия на кнопки
    """
    settings = user.settings

    settings.log("pressed", call.data)

    callback_handler(
        user=user,
        settings=settings,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        message_text=call.message.text,
        call_data=call.data,
        call_id=call.id,
        message=call.message,
    )


@bot.message_handler(func=lambda m: m.text.startswith("#"))
@check_user
def processing_search_message(message: Message, user: User):
    """
    Ловит сообщения поиска
    #   (ИЛИ)
    #!  (И)
    """
    settings = user.settings
    chat_id = message.chat.id

    raw_query = message.text[1:].replace("\n", " ").replace("--", "")
    query = to_html_escaping(raw_query.strip())

    settings.log("search", query)

    generated = search_message(settings=settings, chat_id=chat_id, query=query)
    generated.send(chat_id=chat_id)


@bot.message_handler(func=lambda m: re_edit_message.search(m.text))
@check_user
def processing_edit_message(message: Message, user: User):
    """
    Ловит сообщения для изменения событий
    """
    settings = user.settings

    settings.log("send", "edit event text")

    if confirm_changes_message(user, message) is None:
        delete_message_action(settings, message)


re_edit_event_date_message = re.compile(
    r"\A@\w{5,32} event\((\d+), (\d+)\)\.date(?:\n|\Z)"
)


@bot.message_handler(func=lambda m: re_edit_event_date_message.search(m.text))
@check_user
def edit_event_date_message(message: Message, user: User):
    settings = user.settings

    settings.log("send", "edit event date")

    event_id, message_id = re_edit_event_date_message.findall(message.text)[0]
    event_id, message_id = int(event_id), int(message_id)
    chat_id = message.chat.id

    lines = message.text.split("\n")
    if (
        len(lines) != 2
        or re_date.match(lines[1]) is None
        or not user.edit_event_date(event_id, lines[1])[0]
    ):
        NoEventMessage(get_translate("error", settings.lang)).reply(message)
        return

    try:
        update_message_action(settings, chat_id, message_id, lines[1])
    except ValueError:
        NoEventMessage(get_translate("error", settings.lang)).reply(message)
        return

    delete_message_action(settings, message)


@bot.message_handler(
    func=lambda m: (
        m.reply_to_message
        and m.reply_to_message.text.startswith("⚙️")
        and m.reply_to_message.from_user.id == bot.id
    )
)
@check_user
def processing_edit_city_message(message: Message, user: User):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    settings = user.settings
    chat_id = message.chat.id

    settings.log("send", "edit city")

    if user.set_settings(city=message.text[:25])[0]:
        delete_message_action(settings, message)

    generated = settings_message(settings)
    try:
        generated.edit(chat_id, message.reply_to_message.message_id)
    except ApiTelegramException:
        pass


def add_event_func(msg) -> int:
    with db.connection(), db.cursor():
        add_event_date = db.execute(
            """
SELECT add_event_date
  FROM settings
 WHERE user_id = ?;
""",
            params=(msg.chat.id,),
        )
    return add_event_date[0][0] if add_event_date else 0


@bot.message_handler(func=add_event_func)
@check_user
def add_event(message: Message, user: User):
    """
    Ловит сообщение если пользователь хочет добавить событие
    """
    settings = user.settings
    chat_id = message.chat.id
    # Экранируем текст
    markdown_text = to_html_escaping(html_to_markdown(message.html_text))

    settings.log("send", "add event")

    new_event_date = db.execute(
        """
SELECT add_event_date
  FROM settings
 WHERE user_id = ?;
""",
        params=(chat_id,),
    )[0][0].split(",")[0]

    # Если сообщение команда, то проигнорировать
    if markdown_text.split("@")[0][1:] in config.COMMANDS:
        return

    # Если сообщение длиннее 3800 символов, то ошибка
    if len(markdown_text) >= 3800:
        message_is_too_long = get_translate("message_is_too_long", settings.lang)
        bot.reply_to(message, message_is_too_long, reply_markup=delmarkup)
        return

    if user.check_limit(new_event_date, event_count=1, symbol_count=len(markdown_text)):
        exceeded_limit = get_translate("exceeded_limit", settings.lang)
        bot.reply_to(message, exceeded_limit, reply_markup=delmarkup)
        return

    # Пытаемся создать событие
    if user.add_event(new_event_date, markdown_text)[0]:
        clear_state(chat_id)
        delete_message_action(settings, message)
    else:
        error_translate = get_translate("error", settings.lang)
        bot.reply_to(message, error_translate, reply_markup=delmarkup)
        clear_state(chat_id)


def schedule_loop():
    # ждём чтобы цикл уведомлений начинался
    sleep(60 - now_time().second)
    while True:
        while_time = now_time()

        if config.NOTIFICATIONS and while_time.minute in (0, 10, 20, 30, 40, 50):
            Thread(target=notifications_message, daemon=True).start()

        if config.POKE_LINK and while_time.minute in (0, 15, 30, 45):
            if config.LINK:
                Thread(target=poke_link, daemon=True).start()

        sleep(60)


if __name__ == "__main__":
    if config.NOTIFICATIONS or config.POKE_LINK:
        Thread(target=schedule_loop, daemon=True).start()

    bot.infinity_polling()
