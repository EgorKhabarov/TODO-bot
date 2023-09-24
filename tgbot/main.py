from time import sleep
from functools import wraps
from threading import Thread

from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery, Message, BotCommandScopeDefault

from tgbot import config
from tgbot.lang import get_translate
from tgbot.bot import bot, bot_log_info
from tgbot.time_utils import now_time
from tgbot.bot_actions import delete_message_action, confirm_changes_message
from tgbot.buttons_utils import delmarkup
from tgbot.handlers import command_handler, callback_handler, clear_state
from tgbot.utils import poke_link, re_edit_message, rate_limit_requests, msg_check
from tgbot.bot_messages import search_message, notifications_message, settings_message
from todoapi.api import User
from todoapi.types import db
from todoapi.logger import logging
from todoapi.db_creator import create_tables
from todoapi.utils import html_to_markdown, is_admin_id, remove_html_escaping

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
                res = func(x, user)
            return res

        return wrapper(_x)

    return check_argument


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


@bot.message_handler(
    func=lambda m: m.text.startswith("#") and not m.text.startswith("#️⃣")
)
@check_user
def processing_search_message(message: Message, user: User):
    """
    Ловит сообщения поиска
    #   (ИЛИ)
    #!  (И)
    """
    settings = user.settings
    chat_id = message.chat.id

    raw_query = message.html_text[1:].replace("\n", " ").replace("--", "")
    query = html_to_markdown(raw_query.strip())

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
    markdown_text = remove_html_escaping(html_to_markdown(message.html_text))

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
    if markdown_text.split()[0].split("@")[0][1:] in config.COMMANDS:
        return

    # Если сообщение длиннее 3800 символов, то ошибка
    if len(markdown_text) >= 3800:
        message_is_too_long = get_translate("errors.message_is_too_long", settings.lang)
        bot.reply_to(message, message_is_too_long, reply_markup=delmarkup(settings))
        return

    if (
        user.check_limit(
            new_event_date, event_count=1, symbol_count=len(markdown_text)
        )[1]
        is True
    ):
        exceeded_limit = get_translate("errors.exceeded_limit", settings.lang)
        bot.reply_to(message, exceeded_limit, reply_markup=delmarkup(settings))
        return

    # Пытаемся создать событие
    if user.add_event(new_event_date, markdown_text)[0]:
        delete_message_action(settings, message)
    else:
        error_translate = get_translate("errors.error", settings.lang)
        bot.reply_to(message, error_translate, reply_markup=delmarkup(settings))

    clear_state(chat_id)


def schedule_loop():
    # ждём чтобы цикл уведомлений начинался
    sleep(60 - now_time().second)
    while True:
        while_time = now_time()

        if config.NOTIFICATIONS and while_time.minute in (0, 10, 20, 30, 40, 50):
            Thread(target=notifications_message, daemon=True).start()

        if config.POKE_LINK and while_time.minute in (0, 10, 20, 30, 40, 50):
            if config.LINK:
                Thread(target=poke_link, daemon=True).start()

        sleep(60)


if __name__ == "__main__":
    if config.NOTIFICATIONS or config.POKE_LINK:
        Thread(target=schedule_loop, daemon=True).start()

    bot.infinity_polling()
