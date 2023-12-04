import re
import html
import logging
from time import sleep

from telebot.apihelper import ApiTelegramException  # noqa
from telebot.types import Message  # noqa

from tgbot import config
from tgbot.bot import bot
from tgbot.queries import queries
from tgbot.request import request
from tgbot.time_utils import DayInfo
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.utils import re_edit_message, highlight_text_difference, html_to_markdown
from tgbot.message_generator import NoEventMessage, CallBackAnswer
from tgbot.buttons_utils import delmarkup, create_monthly_calendar_keyboard
from tgbot.bot_messages import (
    trash_can_message,
    search_message,
    daily_message,
    week_event_list_message,
)
from todoapi.types import db
from todoapi.utils import is_admin_id
from telegram_utils.buttons_generator import generate_buttons


re_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}")

def delete_message_action(message: Message) -> None:
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except ApiTelegramException:
        if (
            message.chat.type != "private"
            and not bot.get_chat_member(
                message.chat.id, bot.user.id
            ).can_delete_messages
        ):
            error_text = get_translate("errors.get_permission")
        else:
            error_text = get_translate("errors.delete_messages_older_48_h")

        NoEventMessage(error_text, delmarkup()).reply(message)


def press_back_action(
    call_data: str,
    message_id: int,
    message_text: str,
) -> None:
    settings, chat_id = request.user.settings, request.chat_id
    result = db.execute(queries["select add_event_date"], params=(chat_id,))
    add_event_date = result[0][0]

    if add_event_date:
        add_event_message_id = add_event_date.split(",")[1]
        if int(message_id) == int(add_event_message_id):
            db.execute(
                queries["update add_event_date"],
                params=(0, chat_id),
                commit=True,
            )

    msg_date = message_text.removeprefix("<b>")[:10]

    if call_data.endswith("bin"):  # Корзина
        generated = trash_can_message()
        generated.edit(chat_id, message_id)

    elif message_text.startswith("🔍 "):  # Поиск
        first_line = message_text.split("\n", maxsplit=1)[0]
        raw_query = first_line.split(maxsplit=2)[-1][:-1]
        query = html.unescape(raw_query)
        generated = search_message(query)
        generated.edit(chat_id, message_id)

    elif len(msg_date.split(".")) == 3:  # Проверка на дату
        try:  # Пытаемся изменить сообщение
            generated = daily_message(msg_date, message_id=message_id)
            generated.edit(chat_id, message_id)
        except ApiTelegramException:
            # Если сообщение не изменено, то шлём календарь
            # "dd.mm.yyyy" -> [yyyy, mm]
            YY_MM = [int(x) for x in msg_date.split(".")[1:]][::-1]
            text = get_translate("select.date")
            markup = create_monthly_calendar_keyboard(YY_MM)
            NoEventMessage(text, markup).edit(chat_id, message_id)


def update_message_action(
    message_id: int,
    message_text: str,
    call_id: int = None,
) -> None:
    settings, chat_id = request.user.settings, request.chat_id
    if message_text.startswith("🔍 "):  # Поиск
        first_line = message_text.split("\n", maxsplit=1)[0]
        raw_query = first_line.split(maxsplit=2)[-1][:-1]
        query = html.unescape(raw_query)
        generated = search_message(query)

    elif message_text.startswith("📆"):  # Если /week_event_list
        generated = week_event_list_message()

    elif message_text.startswith("🗑"):  # Корзина
        generated = trash_can_message()

    elif re_date.match(message_text) is not None:
        msg_date = re_date.match(message_text)[0]
        generated = daily_message(msg_date, message_id=message_id)

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


def confirm_changes_message(message: Message) -> None | int:
    """
    Генерация сообщения для подтверждения изменений текста события.

    Возвращает 1 если есть ошибка.
    """
    user, chat_id = request.user, request.chat_id

    markdown_text = html_to_markdown(message.html_text)

    event_id, message_id = re_edit_message.findall(markdown_text)[0]
    event_id, message_id = int(event_id), int(message_id)

    api_response = user.get_event(event_id)

    if not api_response[0]:
        return 1  # Этого события нет

    event = api_response[1]

    text = markdown_text.split("\n", maxsplit=1)[-1].strip("\n")
    # Убираем @bot_username из начала текста remove_html_escaping
    edit_text = markdown_text.split(maxsplit=1)[-1]

    if len(message.text.split("\n")) == 1:
        try:
            if before_move_message(
                call_id=0,
                call_data=f"before move {event.date} {event_id} _",
                message_id=message_id,
                message_text=f"{event.date}",
                event_id=event_id,
            ):
                return 1
        except ApiTelegramException:
            pass
        delete_message_action(message)
        return 1

    markup = generate_buttons(
        [
            [
                {
                    f"{event_id} {text[:20]}{config.callbackTab * 20}": {
                        "switch_inline_query_current_chat": edit_text
                    }
                },
                {"✖": "message_del"},
            ]
        ]
    )

    # Уменьшится ли длинна события
    new_event_len = len(text)
    len_old_event = len(event.text)
    tag_len_max = new_event_len > 3800
    tag_len_less = len_old_event > new_event_len

    # Вычисляем сколько символов добавил пользователь. Если символов стало меньше, то 0.
    added_length = 0 if tag_len_less else new_event_len - len_old_event

    tag_limit_exceeded = (
        user.check_limit(event.date, symbol_count=added_length)[1] is True
    )

    if tag_len_max:
        translate = get_translate("errors.message_is_too_long")
        NoEventMessage(translate, markup).reply(message)
    elif tag_limit_exceeded:
        translate = get_translate("errors.exceeded_limit")
        NoEventMessage(translate, markup).reply(message)
    else:
        day = DayInfo(event.date)
        text_diff = highlight_text_difference(
            html.escape(event.text), html.escape(text)
        )
        # Находим пересечения выделений изменений и html экранирования
        # Костыль для исправления старого экранирования
        # На случай если в базе данных окажется html экранированный текст
        text_diff = re.sub(
            r"&(<(/?)u>)(lt|gt|quot|#39);",
            lambda m: (
                f"&{m.group(3)};{m.group(1)}"
                if m.group(2) == "/"
                else f"{m.group(1)}&{m.group(3)};"
            ),
            text_diff,
        )

        generated = NoEventMessage(
            f"{event.date} {event_id} <u><i>{day.str_date}  "
            f"{day.week_date}</i></u> ({day.relatively_date})\n"
            f"<b>{get_translate('are_you_sure_edit')}</b>\n"
            f"<i>{text_diff}</i>",
            reply_markup=generate_buttons(
                [
                    [
                        {get_theme_emoji("back"): "back"},
                        {"📝": {"switch_inline_query_current_chat": edit_text}},
                        {"✅": "confirm change"},
                    ]
                ]
            ),
        )
        try:
            generated.edit(chat_id, message_id)
        except ApiTelegramException as e:
            if "message is not modified" not in f"{e}":
                logging.info(f'ApiTelegramException "{e}"')
                return 1


def before_move_message(
    call_id: int,
    call_data: str,
    message_id,
    message_text,
    event_id: int,
    in_wastebasket: bool = False,
) -> None | int:
    """
    Генерирует сообщение с кнопками удаления,
    удаления в корзину (для премиум) и изменения даты.

    Возвращает 1 если есть ошибка.
    """
    user, chat_id = request.user, request.chat_id
    settings = user.settings
    # Если события нет, то обновляем сообщение
    api_response = user.get_event(event_id, in_wastebasket)

    if not api_response[0]:
        if call_id:
            error = get_translate("errors.error")
            CallBackAnswer(error).answer(call_id)
        press_back_action(call_data, message_id, message_text)
        return 1

    event = api_response[1]

    delete_permanently = get_translate("delete_permanently")
    trash_bin = get_translate("trash_bin")
    edit_date = get_translate("edit_date")
    split_data = call_data.split(maxsplit=1)[-1]

    is_wastebasket_available = (
        settings.user_status in (1, 2) and not in_wastebasket
    ) or is_admin_id(chat_id)

    pre_delmarkup = generate_buttons(
        [
            [
                {f"❌ {delete_permanently}": f"{split_data} delete"},
                {f"🗑 {trash_bin}": f"{split_data} to_bin"}
                if is_wastebasket_available and not in_wastebasket
                else {},
            ],
            [
                {
                    f"✏️📅 {edit_date}": "edit_event_date",
                }
            ]
            if not in_wastebasket
            else [],
            [
                {
                    get_theme_emoji("back"): "back" if not in_wastebasket else "back bin",
                }
            ],
        ]
    )

    day = DayInfo(event.date)
    what_do_with_event = get_translate("what_do_with_event")
    text = (
        f"<b>{event.date}.{event_id}.</b>{event.status} <u><i>{day.str_date}  "
        f"{day.week_date}</i> {day.relatively_date}</u>\n"
        f"<b>{what_do_with_event}:</b>\n{html.escape(event.text)[:3800]}"
    )
    NoEventMessage(text, pre_delmarkup).edit(chat_id, message_id)
