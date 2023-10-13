import html
import atexit
from time import sleep
from functools import wraps
from threading import Thread

import requests
from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery, Message, BotCommandScopeDefault

from tgbot import config
from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.time_utils import now_time
from tgbot.bot import bot, bot_log_info
from tgbot.buttons_utils import delmarkup
from tgbot.handlers import command_handler, callback_handler, clear_state
from tgbot.bot_actions import delete_message_action, confirm_changes_message
from tgbot.utils import poke_link, re_edit_message, rate_limit_requests, msg_check
from tgbot.bot_messages import search_message, notifications_message, settings_message
from todoapi.api import User
from todoapi.types import db
from todoapi.logger import logging
from todoapi.db_creator import create_tables
from todoapi.utils import html_to_markdown, is_admin_id

create_tables()

logging.info(bot_log_info())

bot.set_my_commands(get_translate("buttons.commands.0", "ru"), BotCommandScopeDefault())


def check_user(func):
    @wraps(func)
    def check_argument(_x: Message | CallbackQuery):
        if isinstance(_x, Message):
            if (
                _x.chat.type != "private"
                and _x.text.startswith("/")
                and not msg_check.match(_x.text)
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
                if (
                    _x.chat.type != "private"
                    and _x.text.startswith("/")
                    and not msg_check.match(_x.text)
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
                res = func(x)
            return res

        return wrapper(_x)

    return check_argument


@bot.message_handler(commands=[*config.COMMANDS])
@check_user
def message_handler(message: Message):
    """
    Ловит команды от пользователей
    """
    request.user.settings.log("send", html_to_markdown(message.html_text))
    command_handler(message)


@bot.callback_query_handler(func=lambda call: True)
@check_user
def callback_query_handler(call: CallbackQuery):
    """
    Ловит нажатия на кнопки
    """
    request.user.settings.log("pressed", call.data)
    callback_handler(
        message_id=call.message.message_id,
        message_text=call.message.text,
        call_data=call.data,
        call_id=call.id,
        message=call.message,
    )


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
    if message.entities:
        markdown_text = html.unescape(html_to_markdown(message.html_text))
    else:
        markdown_text = message.html_text

    query = markdown_text[1:].replace("\n", " ").replace("--", "").strip()

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
        and m.reply_to_message.text.startswith("⚙️")
        and m.reply_to_message.from_user.id == bot.id
    )
)
@check_user
def processing_edit_city_message(message: Message):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    request.user.settings.log("send", "edit city")

    if request.user.set_settings(city=message.text[:25])[0]:
        delete_message_action(message)

    generated = settings_message()
    try:
        generated.edit(request.chat_id, message.reply_to_message.message_id)
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
def add_event(message: Message):
    """
    Ловит сообщение если пользователь хочет добавить событие
    """
    # Экранируем текст
    """
    Телеграм экранирует html спец символы ('<', '>', '&', ';') только если в сообщении есть выделение.

    Если написать "<b>text</b>" и взять message.html_text, то он вернёт тот же текст.

    Если же написать "<b>text</b> **text**", то message.html_text вернёт "&lt;b&gt;text&lt;/b&gt; **text**"
    """
    if message.entities:
        markdown_text = html.unescape(html_to_markdown(message.html_text))
    else:
        markdown_text = message.html_text

    request.user.settings.log("send", "add event")

    new_event_date = db.execute(
        """
SELECT add_event_date
  FROM settings
 WHERE user_id = ?;
""",
        params=(request.chat_id,),
    )[0][0].split(",")[0]

    # Если сообщение команда, то проигнорировать
    if markdown_text.split()[0].split("@")[0][1:] in config.COMMANDS:
        return

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
    sleep(60 - now_time().second)
    while True:
        while_time = now_time()

        if config.NOTIFICATIONS and while_time.minute in (0, 10, 20, 30, 40, 50):
            Thread(target=notifications_message, daemon=True).start()

        if (
            config.POKE_LINK
            and config.LINK
            and while_time.minute in (0, 10, 20, 30, 40, 50)
        ):
            Thread(target=poke_link, daemon=True).start()

        sleep(60)


if config.POKE_LINK and config.LINK:
    atexit.register(lambda: requests.get(config.LINK))
