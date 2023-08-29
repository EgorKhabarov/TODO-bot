import re
import logging
from time import sleep

from telebot.apihelper import ApiTelegramException
from telebot.types import Message

import config
from bot import bot
from lang import get_translate
from time_utils import DayInfo
from message_generator import NoEventMessage, CallBackAnswer
from buttons_utils import delmarkup, create_monthly_calendar_keyboard, generate_buttons
from bot_messages import (
    trash_can_message,
    search_message,
    daily_message,
    week_event_list_message,
)
from todoapi.api import User
from todoapi.types import db, UserSettings
from todoapi.utils import (
    to_html_escaping,
    html_to_markdown,
    remove_html_escaping,
    is_admin_id,
)
from utils import re_edit_message, highlight_text_difference

re_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}")


def delete_message_action(settings: UserSettings, message: Message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except ApiTelegramException:
        get_admin_rules = get_translate("errors.get_admin_rules", settings.lang)
        NoEventMessage(get_admin_rules, delmarkup).reply(message)


def press_back_action(
    settings: UserSettings,
    call_data: str,
    chat_id: int,
    message_id: int,
    message_text: str,
):
    add_event_date = db.execute(
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
            db.execute(
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
        generated = trash_can_message(settings, chat_id)
        generated.edit(chat_id, message_id)

    elif message_text.startswith("🔍 "):  # Поиск
        first_line = message_text.split("\n", maxsplit=1)[0]
        raw_query = first_line.split(maxsplit=2)[-1][:-1]
        query = to_html_escaping(raw_query)
        generated = search_message(settings, chat_id, query)
        generated.edit(chat_id, message_id)

    elif len(msg_date.split(".")) == 3:  # Проверка на дату
        try:  # Пытаемся изменить сообщение
            generated = daily_message(
                settings=settings,
                chat_id=chat_id,
                date=msg_date,
                message_id=message_id,
            )
            generated.edit(chat_id, message_id)
        except ApiTelegramException:
            # Если сообщение не изменено, то шлём календарь
            # "dd.mm.yyyy" -> [yyyy, mm]
            YY_MM = [int(x) for x in msg_date.split(".")[1:]][::-1]
            text = get_translate("select.date", settings.lang)
            markup = create_monthly_calendar_keyboard(
                chat_id, settings.timezone, settings.lang, YY_MM
            )
            NoEventMessage(text, markup).edit(chat_id, message_id)


def update_message_action(
    settings: UserSettings,
    chat_id: int,
    message_id: int,
    message_text: str,
    call_id: int = None,
):
    if message_text.startswith("🔍 "):  # Поиск
        first_line = message_text.split("\n", maxsplit=1)[0]
        raw_query = first_line.split(maxsplit=2)[-1][:-1]
        query = to_html_escaping(raw_query)
        generated = search_message(settings, chat_id, query)

    elif message_text.startswith("📆"):  # Если /week_event_list
        generated = week_event_list_message(settings, chat_id)

    elif message_text.startswith("🗑"):  # Корзина
        generated = trash_can_message(settings=settings, chat_id=chat_id)

    elif re_date.match(message_text) is not None:
        msg_date = re_date.match(message_text)[0]
        generated = daily_message(settings, chat_id, msg_date, message_id=message_id)

    else:
        return

    if call_id:
        sleep(0.5)

    try:
        generated.edit(chat_id, message_id)
    except ApiTelegramException:
        pass

    if call_id:
        CallBackAnswer("ok").answer(call_id, True)


def confirm_changes_message(user: User, message: Message):
    settings = user.settings
    chat_id = message.chat.id
    markdown_text = html_to_markdown(message.html_text)

    event_date, event_id, message_id = re_edit_message.findall(markdown_text)[0]
    event_id, message_id = int(event_id), int(message_id)
    text = markdown_text.split("\n", maxsplit=1)[-1].strip("\n")

    if len(message.text.split("\n")) == 1:
        try:
            if before_del_message(
                user=user,
                call_id=0,
                call_data=f"before del {event_date} {event_id} _",
                chat_id=chat_id,
                message_id=message_id,
                message_text=f"{event_date}",
                event_id=event_id,
            ):
                return 1
        except ApiTelegramException:
            pass
        delete_message_action(settings, message)
        return 1

    # Убираем @bot_username из начала текста
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

    # Уменьшится ли длинна события
    event = user.get_event(event_id)[0]
    if not event:
        return 1  # Этого события нет

    new_event_len = len(text)
    len_old_event = len(event.text)
    tag_len_max = new_event_len > 3800
    tag_len_less = len_old_event > new_event_len

    # Вычисляем сколько символов добавил пользователь. Если символов стало меньше, то 0.
    added_length = 0 if tag_len_less else new_event_len - len_old_event

    tag_limit_exceeded = user.check_limit(event_date, symbol_count=added_length)

    if tag_len_max:
        translate = get_translate("errors.message_is_too_long", settings.lang)
        NoEventMessage(translate, markup).reply(message)
    elif tag_limit_exceeded:
        translate = get_translate("errors.exceeded_limit", settings.lang)
        NoEventMessage(translate, markup).reply(message)
    else:
        day = DayInfo(settings, event_date)
        edit_text = remove_html_escaping(markdown_text).split(maxsplit=1)[-1]
        try:
            text_diff = highlight_text_difference(
                to_html_escaping(event.text), to_html_escaping(text)
            )
            generated = NoEventMessage(
                f"{event_date} {event_id} <u><i>{day.str_date}  "
                f"{day.week_date}</i></u> ({day.relatively_date})\n"
                f"<b>{get_translate('are_you_sure_edit', settings.lang)}</b>\n"
                f"<i>{text_diff}</i>",
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
            generated.edit(chat_id, message_id)
        except ApiTelegramException as e:
            if "message is not modified" not in f"{e}":
                logging.info(f'ApiTelegramException "{e}"')
                return 1


def before_del_message(
    user: User,
    call_id: int,
    call_data: str,
    chat_id: int,
    message_id,
    message_text,
    event_id: int,
    in_wastebasket: bool = False,
):
    settings = user.settings
    # Если события нет, то обновляем сообщение
    response, error_text = user.get_event(event_id, in_wastebasket)

    if not response:
        if call_id:
            error = get_translate("errors.error", settings.lang)
            CallBackAnswer(error).answer(call_id)
        press_back_action(settings, call_data, chat_id, message_id, message_text)
        return 1

    text, status, event_date = response.text, response.status, response.date

    delete_permanently = get_translate("delete_permanently", settings.lang)
    trash_bin = get_translate("trash_bin", settings.lang)
    split_data = call_data.split(maxsplit=1)[-1]

    is_wastebasket_available = (
        settings.user_status in (1, 2) and not in_wastebasket
    ) or is_admin_id(chat_id)

    predelmarkup = generate_buttons(
        [
            {
                "🔙": "back" if not in_wastebasket else "back bin",
                f"❌ {delete_permanently}": f"{split_data} delete",
                **(
                    {f"🗑 {trash_bin}": f"{split_data} to_bin"}
                    if is_wastebasket_available
                    else {}
                ),
            },
        ]
    )

    day = DayInfo(settings, event_date)
    sure_text = get_translate("are_you_sure", settings.lang)
    end_text = (
        get_translate("/deleted", settings.lang)
        if (settings.user_status in (1, 2) or is_admin_id(chat_id))
        else ""
    )
    text = (
        f"<b>{event_date}.{event_id}.</b>{status} <u><i>{day.str_date}  "
        f"{day.week_date}</i> {day.relatively_date}</u>\n"
        f"<b>{sure_text}:</b>\n{text[:3800]}\n\n{end_text}"
    )
    NoEventMessage(text, predelmarkup).edit(chat_id, message_id)
