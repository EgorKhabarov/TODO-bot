import re
from time import sleep
from threading import Thread

from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery, Message, BotCommandScopeDefault

import config
from bot import bot
from db.db import SQL
from logger import logging
from lang import get_translate
from db.sql_utils import create_event
from limits import is_exceeded_limit
from db.db_creator import create_tables
from user_settings import UserSettings
from time_utils import now_time, DayInfo
from messages.message_generators import search, notifications
from buttons_utils import generate_buttons, delmarkup
from handlers import command_handler, callback_handler, clear_state
from utils import (
    to_html_escaping,
    is_admin_id,
    poke_link,
    main_log,
    remove_html_escaping,
    html_to_markdown,
)

create_tables()

bot.log_info()

bot.set_my_commands(
    commands=get_translate("0_command_list", "ru"), scope=BotCommandScopeDefault()
)

re_edit_message = re.compile(r"event\((\d{1,2}\.\d{1,2}\.\d{4}), (\d+), (\d+)\)\.edit")


@bot.message_handler(commands=[*config.COMMANDS])
def message_handler(message: Message):
    """
    Ловит команды от пользователей
    """
    chat_id, message_text = message.chat.id, message.text
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(
        user_status=settings.user_status,
        chat_id=chat_id,
        text=message_text,
        action="send",
    )
    command_handler(settings, chat_id, message_text, message)


@bot.callback_query_handler(func=lambda call: True)
def callback_query_handler(call: CallbackQuery):
    """
    Ловит нажатия на кнопки
    """
    chat_id, message_id, call_data, message_text = (
        call.message.chat.id,
        call.message.message_id,
        call.data,
        call.message.text,
    )
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(
        user_status=settings.user_status,
        chat_id=chat_id,
        text=call_data,
        action="pressed",
    )

    if call.data == "None":
        return 0

    callback_handler(
        settings=settings,
        chat_id=chat_id,
        message_id=message_id,
        message_text=call.message.text,
        call_data=call.data,
        call_id=call.id,
        message=call.message,
    )


@bot.message_handler(func=lambda m: m.text.startswith("#"))
def processing_search_message(message: Message):
    """
    Ловит сообщения поиска
    #   (ИЛИ)
    #!  (И)
    """
    chat_id = message.chat.id
    settings = UserSettings(user_id=chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    query = to_html_escaping(message.text[1:].replace("\n", " ").replace("--", ""))
    main_log(
        user_status=settings.user_status,
        chat_id=chat_id,
        text=message.text,
        action="search ",
    )
    generated = search(settings=settings, chat_id=chat_id, query=query)
    generated.send(chat_id=chat_id)


@bot.message_handler(func=lambda m: re_edit_message.search(m.text))
def processing_edit_message(message: Message):
    """
    Ловит сообщения для изменения событий
    """
    chat_id, edit_message_id = message.chat.id, message.message_id
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(
        user_status=settings.user_status,
        chat_id=chat_id,
        text="edit event text",
        action="send",
    )

    markdown_text = html_to_markdown(message.html_text)

    res = re_edit_message.search(markdown_text)[0]

    event_date, event_id, message_id, text = (
        str(re.findall(r"\((\d{1,2}\.\d{1,2}\.\d{4}),", res)[0]),
        int(re.findall(r" (\d+)", res)[0]),
        int(re.findall(r", (\d+)\)", res)[0]),
        markdown_text.split("\n", maxsplit=1)[-1].strip("\n"),
    )

    edit_text = remove_html_escaping(markdown_text).split(maxsplit=1)[-1]
    markup = generate_buttons(
        [
            {
                f"{event_id} {text[:20]}{config.callbackTab * 20}": {
                    "switch_inline_query_current_chat": edit_text
                }
            },
            {"✖": "message_del"},
        ]
    )

    tag_len_max = len(text) > 3800

    try:  # Уменьшится ли длинна события
        len_old_event, tag_len_less = SQL(
            f"""
SELECT LENGTH(text), {len(text)} < LENGTH(text) FROM events
WHERE user_id={chat_id} AND event_id='{event_id}'
AND date='{event_date}' AND isdel=0;
"""
        )[0]
    except ValueError:
        return  # Этого события нет

    # Вычисляем сколько символов добавил пользователь. Если символов стало меньше, то 0.
    added_length = 0 if tag_len_less else len(text) - len_old_event

    tag_limit_exceeded = is_exceeded_limit(
        settings, date=event_date, event_count=0, symbol_count=added_length
    )

    if tag_len_max:
        bot.reply_to(
            message,
            get_translate("message_is_too_long", settings.lang),
            reply_markup=markup,
        )
    elif tag_limit_exceeded:
        bot.reply_to(
            message, get_translate("exceeded_limit", settings.lang), reply_markup=markup
        )
    else:
        day = DayInfo(settings, event_date)
        edit_text = remove_html_escaping(markdown_text).split(maxsplit=1)[-1]
        try:
            bot.edit_message_text(
                f"""
{event_date} {event_id} <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
<b>{get_translate("are_you_sure_edit", settings.lang)}</b>
<i>{to_html_escaping(text)}</i>
""",
                chat_id,
                message_id,
                reply_markup=generate_buttons(
                    [
                        {
                            "🔙": "back",
                            "📝": {"switch_inline_query_current_chat": edit_text},
                            "✅": "confirm change",
                        }
                    ]
                ),
            )
        except ApiTelegramException as e:
            if "message is not modified" not in str(e):
                logging.info(
                    f'[main.py -> get_edit_message] ApiTelegramException "{e}"'
                )
                return

    try:
        bot.delete_message(chat_id, edit_message_id)
    except ApiTelegramException:
        bot.reply_to(
            message,
            get_translate("get_admin_rules", settings.lang),
            reply_markup=delmarkup,
        )


@bot.message_handler(
    func=lambda m: (
        m.reply_to_message
        and m.reply_to_message.text.startswith("⚙️")
        and m.reply_to_message.from_user.id == bot.id
    )
)
def processing_edit_city_message(message: Message):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    chat_id, message_id = message.chat.id, message.message_id
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(
        user_status=settings.user_status,
        chat_id=chat_id,
        text="edit city",
        action="send",
    )
    callback_handler(
        settings=settings,
        chat_id=chat_id,
        message_id=message.reply_to_message.message_id,
        message_text=message.text,
        call_data=f"settings city {message.text[:25]}",
        call_id=0,
        message=message.reply_to_message,
    )

    try:
        bot.delete_message(chat_id, message_id)
    except ApiTelegramException:
        bot.reply_to(
            message,
            get_translate("get_admin_rules", settings.lang),
            reply_markup=delmarkup,
        )


def add_event_func(msg) -> int:
    add_event_date = SQL(
        f"SELECT add_event_date FROM settings WHERE user_id={msg.chat.id};"
    )
    return add_event_date[0][0] if add_event_date else 0


@bot.message_handler(func=add_event_func)
def add_event(message: Message):
    """
    Ловит сообщение если пользователь хочет добавить событие
    """
    chat_id, message_id, markdown_text = (
        message.chat.id,
        message.message_id,
        to_html_escaping(html_to_markdown(message.html_text)),
    )  # Экранируем текст
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(
        user_status=settings.user_status,
        chat_id=chat_id,
        text="add event",
        action="send",
    )

    new_event_date = SQL(
        f"SELECT add_event_date FROM settings WHERE user_id={chat_id};"
    )[0][0].split(",")[0]

    # Если сообщение команда, то проигнорировать
    if markdown_text.split("@")[0][1:] in config.COMMANDS:
        return

    # Если сообщение длиннее 3800 символов, то ошибка
    if len(markdown_text) >= 3800:
        bot.reply_to(
            message,
            get_translate("message_is_too_long", settings.lang),
            reply_markup=delmarkup,
        )
        return

    if is_exceeded_limit(
        settings, date=new_event_date, event_count=1, symbol_count=len(markdown_text)
    ):
        bot.reply_to(
            message,
            get_translate("exceeded_limit", settings.lang),
            reply_markup=delmarkup,
        )
        return

    # Пытаемся создать событие
    if create_event(chat_id, new_event_date, markdown_text):
        clear_state(chat_id)

        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException:
            # Если в группе у бота нет прав для удаления сообщений
            bot.reply_to(
                message,
                get_translate("get_admin_rules", settings.lang),
                reply_markup=delmarkup,
            )
    else:
        bot.reply_to(
            message, get_translate("error", settings.lang), reply_markup=delmarkup
        )
        clear_state(chat_id)


def schedule_loop():
    # ждём чтобы цикл уведомлений начинался
    sleep(60 - now_time().second)
    while True:
        while_time = now_time()

        if config.NOTIFICATIONS and while_time.minute in (0, 10, 20, 30, 40, 50):
            Thread(target=notifications, daemon=True).start()

        if config.POKE_LINK and while_time.minute in (0, 15, 30, 45):
            if config.LINK:
                Thread(target=poke_link, daemon=True).start()

        sleep(60)


if __name__ == "__main__":
    if config.NOTIFICATIONS or config.POKE_LINK:
        Thread(target=schedule_loop, daemon=True).start()

    bot.infinity_polling()
