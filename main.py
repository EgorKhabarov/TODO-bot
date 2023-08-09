import re
from time import sleep
from threading import Thread

from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery, Message, BotCommandScopeDefault

import config
from logger import logging
from lang import get_translate
from bot import bot, bot_log_info
from time_utils import now_time, DayInfo
from bot_actions import delete_message_action
from buttons_utils import generate_buttons, delmarkup
from bot_messages import search_message, notifications_message
from handlers import command_handler, callback_handler, clear_state
from utils import to_html_escaping, poke_link, remove_html_escaping, html_to_markdown, check_user
from todoapi.api import User
from todoapi.types import UserSettings, db
from todoapi.db_creator import create_tables

create_tables()

bot_log_info()

bot.set_my_commands(
    commands=get_translate("0_command_list", "ru"), scope=BotCommandScopeDefault()
)

re_edit_message = re.compile(r"\A@\w{5,32} event\((\d{1,2}\.\d{1,2}\.\d{4}), (\d+), (\d+)\)\.edit(?:\n|\Z)")


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
    settings: UserSettings = user.settings

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
    settings: UserSettings = user.settings
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
    settings: UserSettings = user.settings
    chat_id, edit_message_id = message.chat.id, message.message_id

    settings.log("send", "edit event text")

    markdown_text = html_to_markdown(message.html_text)

    event_date, event_id, message_id = re_edit_message.findall(markdown_text)[0]
    event_id, message_id = int(event_id), int(message_id)
    text = markdown_text.split("\n", maxsplit=1)[-1].strip("\n")

    if len(message.text.split("\n")) == 1:
        try:
            if callback_handler(
                user=user,
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=f"{event_date}",
                call_data=f"before del {event_date} {event_id} _",
                call_id=0,
                message=message,
            ):
                return
        except ApiTelegramException:
            pass
        delete_message_action(settings, chat_id, edit_message_id, message)
        return

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
        len_old_event, tag_len_less = db.execute(
            """
SELECT LENGTH(text),
       LENGTH(text) > ?
  FROM events
 WHERE user_id = ? AND 
       event_id = ? AND 
       date = ? AND 
       removal_time = 0;
""",
            params=(len(text), chat_id, event_id, event_date),
        )[0]
    except ValueError:
        return  # Этого события нет

    # Вычисляем сколько символов добавил пользователь. Если символов стало меньше, то 0.
    added_length = 0 if tag_len_less else len(text) - len_old_event


    tag_limit_exceeded = user.check_limit(event_date, symbol_count=added_length)

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

    delete_message_action(settings, chat_id, edit_message_id, message)


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
    settings: UserSettings = user.settings
    chat_id, message_id = message.chat.id, message.message_id

    settings.log("send", "edit city")
    callback_handler(
        user=user,
        settings=settings,
        chat_id=chat_id,
        message_id=message.reply_to_message.message_id,
        message_text=message.text,
        call_data=f"settings city {message.text[:25]}",
        call_id=0,
        message=message.reply_to_message,
    )

    delete_message_action(settings, chat_id, message_id, message)


def add_event_func(msg) -> int:
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
    settings: UserSettings = user.settings
    chat_id, message_id, markdown_text = (
        message.chat.id,
        message.message_id,
        to_html_escaping(html_to_markdown(message.html_text)),
    )  # Экранируем текст

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
        delete_message_action(settings, chat_id, message_id, message)
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
