import atexit
from time import sleep
from threading import Thread
from datetime import datetime

import requests

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

# noinspection PyPackageRequirements
from telebot.types import CallbackQuery, Message

import config
from tgbot.request import request
from tgbot.bot import bot, bot_log_info
from tgbot.buttons_utils import delmarkup
from tgbot.dispatcher import process_account
from tgbot.message_generator import TextMessage
from tgbot.bot_actions import delete_message_action
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.utils import (
    poke_link,
    telegram_log,
    re_edit_message,
    html_to_markdown,
    re_inline_message,
    re_user_edit_name_message,
    re_group_edit_name_message,
    re_user_edit_password_message,
)
from tgbot.handlers import (
    reply_handler,
    add_event_cache,
    add_group_cache,
    command_handler,
    callback_handler,
    cache_create_group,
    cache_add_event_date,
)
from tgbot.bot_messages import (
    group_message,
    groups_message,
    account_message,
    search_results_message,
    confirm_changes_message,
    send_notifications_messages,
)
from todoapi.types import db
from todoapi.logger import logging
from todoapi.log_cleaner import clear_logs
from todoapi.db_creator import create_tables
from todoapi.exceptions import (
    WrongDate,
    TextIsTooBig,
    LimitExceeded,
    GroupNotFound,
    NotGroupMember,
    NotUniqueUsername,
    NotEnoughPermissions,
)
from telegram_utils.command_parser import command_regex
from telegram_utils.buttons_generator import generate_buttons


create_tables()
logging.info(bot_log_info())
command_regex.set_username(bot.user.username)


@bot.message_handler(content_types=["migrate_to_chat_id"], chat_types=["group"])
def migrate_chat(message: Message):
    """Миграция chat.id группы в супергруппу"""
    logging.info(
        f"[{message.chat.id:<10}] migrate_to_chat_id {message.migrate_to_chat_id}"
    )
    params = {
        "from_chat_id": message.chat.id,
        "to_chat_id": message.migrate_to_chat_id,
    }
    db.execute(
        """
UPDATE groups
   SET chat_id = :to_chat_id
 WHERE chat_id = :from_chat_id;
""",
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
    telegram_log("press", call.data)
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
    search_results_message(query).send()


@bot.message_handler(func=lambda m: re_inline_message.match(m.text))
@process_account
def inline_message_handler(message: Message):
    is_private = message.chat.type == "private"

    if re_edit_message.findall(message.text):
        telegram_log("send", "edit event text")
        if confirm_changes_message(message) is None:
            delete_message_action(message)

    if not is_private:
        return None

    elif match := re_user_edit_name_message.findall(message.html_text):
        telegram_log("send", "user edit name")
        message_id, name = match[0]

        try:
            request.entity.edit_user_username(html_to_markdown(name))
            request.entity.user.username = html_to_markdown(name)
        except ValueError:
            TextMessage(get_translate("errors.wrong_username")).reply()
        except NotUniqueUsername:
            TextMessage(get_translate("errors.username_is_taken")).reply()
        else:
            delete_message_action(message)
            try:
                account_message(message_id).edit(message_id=message_id)
            except ApiTelegramException:
                pass

    elif match := re_user_edit_password_message.findall(message.html_text):
        telegram_log("send", "user edit password")
        old_password, new_password = map(html_to_markdown, match[0])

        try:
            request.entity.edit_user_password(old_password, new_password)
        except ValueError:
            TextMessage(get_translate("errors.password_too_easy")).reply(message)
        except NotEnoughPermissions:
            TextMessage(get_translate("errors.incorrect_password")).reply(message)
        else:
            text = get_translate("errors.success")
            markup = generate_buttons([[{get_theme_emoji("del"): "md"}]])
            TextMessage(text, markup).send(message.chat.id)
            delete_message_action(message)

    elif match := re_group_edit_name_message.findall(message.html_text):
        telegram_log("send", "group edit name")
        group_id, message_id, name = match[0]
        name = name or "GroupName"

        try:
            request.entity.edit_group_name(html_to_markdown(name), group_id)
        except NotEnoughPermissions:
            bot.reply_to(message, get_translate("errors.limit_exceeded"))
        except (GroupNotFound, NotGroupMember):
            bot.reply_to(message, get_translate("errors.error"))
        else:
            try:
                group_message(group_id, message_id=message_id).edit(
                    message.chat.id, message_id
                )
                delete_message_action(message)
            except ApiTelegramException as e:
                if "Description: Bad Request: message is not modified" in str(e):
                    delete_message_action(message)


@bot.message_handler(
    func=lambda m: (
        m.reply_to_message
        and m.reply_to_message.text
        and m.reply_to_message.from_user.id == bot.user.id
        and not m.quote
    )
)
@process_account
def processing_reply_message(message: Message):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    message_start = message.reply_to_message.text.split("\n", 1)[0]
    telegram_log("send", f"reply {message_start}")
    reply_handler(message, message.reply_to_message)


@bot.message_handler(func=lambda m: add_group_cache[m.chat.id])
@process_account
def processing_group_create_message(message: Message):
    """
    Ловит сообщения для добавления группы
    """
    telegram_log("send", "group create")

    message_id = cache_create_group()
    name = html_to_markdown(message.html_text)[:32]
    chat_id = request.entity.request_chat_id

    try:
        request.entity.create_group(name)
    except LimitExceeded:
        try:
            TextMessage(get_translate("errors.limit_exceeded")).send()
        except ApiTelegramException:
            pass
    else:
        try:
            groups_message().edit()
            delete_message_action(message)
        except ApiTelegramException as e:
            if "Description: Bad Request: message is not modified" in str(e):
                delete_message_action(message)


@bot.message_handler(func=lambda m: add_event_cache[m.chat.id])
@process_account
def add_event_handler(message: Message):
    """
    Ловит сообщение если пользователь хочет добавить событие
    """
    html_text = message.html_text

    if message.quote:
        # noinspection PyUnresolvedReferences TODO
        html_text = f"<blockquote>{message.quote.html_text}</blockquote>\n{html_text}"

    markdown_text = html_to_markdown(html_text.strip())
    telegram_log("send", "add event")
    new_event_date = cache_add_event_date().split(",")[0]

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
    try:
        request.entity.create_event(new_event_date, markdown_text)
    except (TextIsTooBig, WrongDate, LimitExceeded):
        error_translate = get_translate("errors.error")
        bot.reply_to(message, error_translate, reply_markup=delmarkup())
    else:
        delete_message_action(message)

    cache_add_event_date("")


def schedule_loop():
    # ждём чтобы цикл уведомлений начинался
    def process():
        while_time = datetime.utcnow()
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
    sleep(60 - datetime.utcnow().second)
    while True:
        process()
        sleep(60)


if config.POKE_SERVER_URL and config.SERVER_URL:
    atexit.register(lambda: requests.get(config.SERVER_URL))
