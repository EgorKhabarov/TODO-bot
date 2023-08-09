import re
from time import sleep

from telebot.apihelper import ApiTelegramException
from telebot.types import Message

from bot import bot
from bot_messages import (
    trash_can_message,
    search_message,
    daily_message,
    week_event_list_message,
)
from buttons_utils import delmarkup, create_monthly_calendar_keyboard
from db.db import SQL
from lang import get_translate
from user_settings import UserSettings
from utils import to_html_escaping


re_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}")

def delete_message_action(settings: UserSettings, chat_id: int, message_id: int, message: Message):
    try:
        bot.delete_message(chat_id, message_id)
    except ApiTelegramException:
        get_admin_rules = get_translate("get_admin_rules", settings.lang)
        bot.reply_to(message, get_admin_rules, reply_markup=delmarkup)

def press_back_action(settings: UserSettings, call_data: str, chat_id: int, message_id: int, message_text: str):
    add_event_date = SQL(
        """
SELECT add_event_date
FROM settings
WHERE user_id = ?;
""",
        params=(chat_id,),
    )[0][0]

    if add_event_date:
        add_event_message_id = add_event_date.split(",")[1]
        if int(message_id) == int(add_event_message_id):
            SQL(
                """
UPDATE settings
SET add_event_date = 0
WHERE user_id = ?;
""",
                params=(chat_id,),
                commit=True,
            )

    msg_date = message_text[:10]

    if call_data.endswith("bin"):  # Корзина
        generated = trash_can_message(settings=settings, chat_id=chat_id)
        generated.edit(chat_id=chat_id, message_id=message_id)

    elif message_text.startswith("🔍 "):  # Поиск
        first_line = message_text.split("\n", maxsplit=1)[0]
        raw_query = first_line.split(maxsplit=2)[-1][:-1]
        query = to_html_escaping(raw_query)
        generated = search_message(settings=settings, chat_id=chat_id, query=query)
        generated.edit(chat_id=chat_id, message_id=message_id)

    elif len(msg_date.split(".")) == 3:  # Проверка на дату
        try:  # Пытаемся изменить сообщение
            generated = daily_message(
                settings=settings,
                chat_id=chat_id,
                date=msg_date,
                message_id=message_id,
            )
            generated.edit(chat_id=chat_id, message_id=message_id)
        except ApiTelegramException:
            # Если сообщение не изменено, то шлём календарь
            # "dd.mm.yyyy" -> [yyyy, mm]
            YY_MM = [int(x) for x in msg_date.split(".")[1:]][::-1]
            text = get_translate("choose_date", settings.lang)
            markup = create_monthly_calendar_keyboard(
                chat_id, settings.timezone, settings.lang, YY_MM
            )
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

def update_message_action(settings: UserSettings, chat_id: int, message_id: int, message_text: str, call_id: int = None):
    if message_text.startswith("🔍 "):  # Поиск
        first_line = message_text.split("\n", maxsplit=1)[0]
        raw_query = first_line.split(maxsplit=2)[-1][:-1]
        query = to_html_escaping(raw_query)
        generated = search_message(settings=settings, chat_id=chat_id, query=query)

    elif message_text.startswith("📆"):  # Если /week_event_list
        generated = week_event_list_message(settings=settings, chat_id=chat_id)

    elif message_text.startswith("🗑"):  # Корзина
        generated = trash_can_message(settings=settings, chat_id=chat_id)

    elif re_date.match(message_text) is not None:
        msg_date = re_date.match(message_text)[0]
        generated = daily_message(
            settings=settings, chat_id=chat_id, date=msg_date, message_id=message_id
        )

    else:
        return

    if call_id:
        sleep(0.5)
        bot.answer_callback_query(call_id, "...", show_alert=True)

    try:
        generated.edit(chat_id=chat_id, message_id=message_id)
    except ApiTelegramException:
        pass
