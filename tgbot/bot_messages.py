import re
import html
import logging
from datetime import timedelta, datetime

from telebot.apihelper import ApiTelegramException  # noqa
from telebot.types import (  # noqa
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from tgbot.bot import bot
from tgbot.queries import queries
from tgbot.request import request
from tgbot.limits import create_image
from tgbot.time_utils import now_time, DayInfo
from tgbot.sql_utils import sqlite_format_date2
from tgbot.bot_actions import delete_message_action
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.message_generator import EventsMessage, TextMessage
from tgbot.buttons_utils import delmarkup, create_monthly_calendar_keyboard
from tgbot.utils import is_secure_chat, add_status_effect, html_to_markdown, re_edit_message, highlight_text_difference
from todoapi.api import User
from todoapi.types import db, string_status, Event
from todoapi.utils import sqlite_format_date, is_valid_year, is_admin_id, is_premium_user
from telegram_utils.buttons_generator import generate_buttons


def start_message() -> TextMessage:
    markup = generate_buttons(
        [
            [{"/menu": "menu"}],
            [{"/calendar": "calendar"}],
            [
                {
                    get_translate("text.add_bot_to_group"): {
                        "url": f"https://t.me/{bot.user.username}?startgroup=AddGroup"
                    }
                },
            ],
        ]
    )
    text = get_translate("messages.start")
    return TextMessage(text, markup)


def menu_message() -> TextMessage:
    """
    Генерирует сообщение меню
    """

    text = "Меню"
    markup = [
        [
            {"📚 Помощь": "help"},
            {"📆 Календарь": "calendar"},
        ],
        [
            {"👤 Аккаунт": "account"},
            {"👥 Группы": "groups"},
        ],
        [
            {"📆 7 дней": "week_event_list"},
            {"🔔 Уведомления": "bell"},
        ],
        [
            {"⚙️ Настройки": "settings"},
            {"🗑 Корзина": "deleted"} if is_premium_user(request.user) else {},
        ],
        [{"😎 Админская": "admin"}] if is_secure_chat(request.query) else [],
    ]
    return TextMessage(text, generate_buttons(markup))


def settings_message() -> TextMessage:
    """
    Ставит настройки для пользователя chat_id
    """
    settings = request.user.settings
    not_lang = "ru" if settings.lang == "en" else "en"
    not_sub_urls = 1 if settings.sub_urls == 0 else 0
    not_direction_smile = {"DESC": "⬆️", "ASC": "⬇️"}[settings.direction]
    not_direction_sql = {"DESC": "ASC", "ASC": "DESC"}[settings.direction]
    not_notifications_ = ("🔕", 0) if settings.notifications else ("🔔", 1)
    n_hours, n_minutes = [int(i) for i in settings.notifications_time.split(":")]
    not_theme = ("⬜️", 0, "⬛️") if settings.theme else ("⬛️", 1, "⬜️")

    utz = settings.timezone
    str_utz = (
        f"{utz} {'🌍' if -2 < int(utz) < 5 else ('🌏' if 4 < int(utz) < 12 else '🌎')}"
    )

    time_zone_dict = {}
    time_zone_dict.__setitem__(
        *("-3", f"settings timezone {utz - 3}") if utz > -10 else ("    ", "None")
    )
    time_zone_dict.__setitem__(
        *("-1", f"settings timezone {utz - 1}") if utz > -12 else ("   ", "None")
    )
    time_zone_dict[str_utz] = "settings timezone 3"
    time_zone_dict.__setitem__(
        *("+1", f"settings timezone {utz + 1}") if utz < 12 else ("   ", "None")
    )
    time_zone_dict.__setitem__(
        *("+3", f"settings timezone {utz + 3}") if utz < 10 else ("    ", "None")
    )

    notifications_time = {}
    if not_notifications_[0] == "🔕":
        now = datetime(2000, 6, 5, n_hours, n_minutes)
        notifications_time = {
            k: f"settings notifications_time {v}"
            for k, v in {
                "-1h": f"{now - timedelta(hours=1):%H:%M}",
                "-10m": f"{now - timedelta(minutes=10):%H:%M}",
                f"{n_hours:0>2}:{n_minutes:0>2} ⏰": "08:00",
                "+10m": f"{now + timedelta(minutes=10):%H:%M}",
                "+1h": f"{now + timedelta(hours=1):%H:%M}",
            }.items()
        }

    text = get_translate("messages.settings").format(
        settings.lang,
        bool(settings.sub_urls),
        settings.city,
        str_utz,
        now_time().strftime("%H:%M  %d.%m.%Y"),
        {"DESC": "⬇️", "ASC": "⬆️"}[settings.direction],
        "🔔" if settings.notifications else "🔕",
        f"{n_hours:0>2}:{n_minutes:0>2}" if settings.notifications else "",
        not_theme[2],
    )
    markup = generate_buttons(
        [
            [
                {f"🗣 {settings.lang}": f"settings lang {not_lang}"},
                {f"🔗 {bool(settings.sub_urls)}": f"settings sub_urls {not_sub_urls}"},
                {f"{not_direction_smile}": f"settings direction {not_direction_sql}"},
                {
                    f"{not_notifications_[0]}": f"settings notifications {not_notifications_[1]}"
                },
                {f"{not_theme[0]}": f"settings theme {not_theme[1]}"},
            ],
            [{k: v} for k, v in time_zone_dict.items()],
            [{k: v} for k, v in notifications_time.items()],
            [{get_translate("text.restore_to_default"): "restore_to_default"}],
            [{get_theme_emoji("back"): "menu"}],
        ]
    )

    return TextMessage(text, markup)


def help_message(path: str = "page 1") -> TextMessage:
    """
    Сообщение помощи
    """

    translate = get_translate(f"messages.help.{path}")
    title = get_translate("messages.help.title")

    if path.startswith("page"):
        text, keyboard = translate
        # Изменяем последнюю кнопку
        last_button: dict = keyboard[-1][-1]
        k, v = last_button.popitem()

        new_k = (
            k
            if not k.startswith("🔙")
            else get_theme_emoji("back") + k.removeprefix("🔙")
        )

        last_button[new_k] = v

        markup = generate_buttons(keyboard)
        generated = TextMessage(f"{title}\n{text}", markup)
    else:
        generated = TextMessage(f"{title}\n{translate}")

    return generated



def daily_message(date: datetime | str, id_list: list | tuple[str] = tuple(), page: int | str = 0) -> EventsMessage:
    """
    Генерирует сообщение на один день

    :param date: Дата сообщения
    :param id_list: Список из event_id
    :param page: Номер страницы
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%d.%m.%Y")
    WHERE = f"user_id = {request.chat_id} AND date = '{date:%d.%m.%Y}' AND removal_time = 0"

    y = date - timedelta(days=1)
    t = date + timedelta(days=1)
    yesterday = f"{y:%d.%m.%Y}" if is_valid_year(y.year) else "None"
    tomorrow = f"{t:%d.%m.%Y}" if is_valid_year(t.year) else "None"

    markup = generate_buttons(
        [
            [
                {get_theme_emoji("add"): f"event_add {date:%d.%m.%Y}"},
                {"🔼": "select one"},
                {"↕️": "select many"},
                {"Menu": "menu"},
            ],
            [
                {get_theme_emoji("back"): "calendar"},
                {"<": yesterday},
                {">": tomorrow},
                {"🔄": f"update {date:%d.%m.%Y}"},
            ],
        ]
    )
    generated = EventsMessage(f"{date:%d.%m.%Y}", reply_markup=markup, page=page)

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE)

    generated.format(
        title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})",
        args="<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n",
        if_empty=get_translate("errors.nodata"),
    )

    # Добавить дополнительную кнопку для дней в которых есть праздники
    daylist = [
        x[0]
        for x in db.execute(
            queries["select recurring_events"],
            params={
                "user_id": request.chat_id,
                "date": f"{date:%d.%m.%Y}",
                "y_date": f"{date:%d.%m}.____",
                "m_date": f"{date:%d}.__.____",
            },
        )
    ]

    if daylist:
        generated.reply_markup.row(InlineKeyboardButton("📅", callback_data=f"recurring {date:%d.%m.%Y}"))

    return generated


def event_message(event_id: int, in_wastebasket: bool = False, message_id: int | None = None) -> TextMessage | None:
    """
    Сообщение для взаимодействия с одним событием
    """

    api_response = request.user.get_event(event_id, in_wastebasket)
    if not api_response[0]:
        return None

    event = api_response[1]
    day = DayInfo(event.date)
    if not in_wastebasket:
        relatively_date = day.relatively_date
        edit_date = get_translate("edit_date")
        add_media = get_translate("add_media")
        markup = [
            [
                {
                    "📝": {
                        "switch_inline_query_current_chat": (
                            f"event({event_id}, {message_id}).text\n"
                            f"{html.unescape(event.text)}"
                        )
                    }
                } if message_id else {"📝": "None"},
                {"🏷" or "🚩": f"status page 0 {event_id} {event.date}"},
                {"🗑": f"event_delete {event_id} {event.date} before"},
            ],
            [
                # {f"🖼 {add_media}": "None"},
                {f"📅 {edit_date}": f"edit_event_date {event_id} back {event.date}"},  # "✏️"
            ],
            [
                {get_theme_emoji("back"): event.date},
                {f"ℹ️": f"event_info {event_id}"},
                {"🔄": f"event {event_id}"}
            ]
        ]
    else:
        relatively_date = get_translate("deldate")(event.days_before_delete())
        delete_permanently_translate = get_translate("delete_permanently")
        recover_translate = get_translate("recover")
        markup = [
            [
                {f"❌ {delete_permanently_translate}": f"event_delete {event_id} {event.date} forever deleted"},
                {f"↩️ {recover_translate}": f"recover {event_id} {event.date}"},
            ],
            [{get_theme_emoji("back"): "deleted"}],
        ]
    text = f"""
<b>{get_translate("what_do_with_event")}:
{event.date}.{event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({relatively_date})
{add_status_effect(event.text, event.status)}
"""
    return TextMessage(text, generate_buttons(markup))


def event_info_message(event_id: int) -> TextMessage | None:
    api_response = request.user.get_event(event_id, False)
    if not api_response[0]:
        return None

    event = api_response[1]
    day = DayInfo(event.date)

    def parse_utc_datetime(time: str) -> str:
        if time == "0":
            return "NEVER"
        time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S") + timedelta(
            hours=request.user.settings.timezone
        )
        return f"{time:%Y.%m.%d %H:%M:%S}"

    text = f"""
<b>{get_translate("event_about_info")}:
{event.date}.{event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
<pre><code class='language-event'>{len(event.text)} - длинна текста
{parse_utc_datetime(event.adding_time)} - время добавления
{parse_utc_datetime(event.recent_changes_time)} - время последних изменений</code></pre>
"""
    markup = [[{get_theme_emoji("back"): f"event {event_id}"}]]
    return TextMessage(text, generate_buttons(markup))


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
            before_move_message(event_id).send(chat_id)
            return 1
        except ApiTelegramException:
            pass
        delete_message_action(message)
        return 1

    markup = generate_buttons(
        [
            [
                {
                    f"{event_id} {text[:20]}".ljust(60, "⠀"): {
                        "switch_inline_query_current_chat": edit_text
                    }
                },
                {get_theme_emoji("del"): "message_del"},
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
        TextMessage(translate, markup).reply(message)
    elif tag_limit_exceeded:
        translate = get_translate("errors.exceeded_limit")
        TextMessage(translate, markup).reply(message)
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
        text = f"""
<b>{get_translate("are_you_sure_edit")}:
{event.date} {event_id}</b> <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
<i>{text_diff}</i>
"""
        generated = TextMessage(
            text,
            markup=generate_buttons(
                [
                    [
                        {get_theme_emoji("back"): f"event {event.event_id}"},
                        {"📝": {"switch_inline_query_current_chat": edit_text}},
                        {"💾": f"confirm_change {event.event_id} {event.date}"},
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


def recurring_events_message(date: str, id_list: list | tuple[str] = tuple(), page: int | str = 0) -> EventsMessage:
    """
    :param date: дата у сообщения
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с повторяющимися событиями:
        recurring(settings=settings, date=date, chat_id=chat_id)
    Изменить страницу:
        recurring(settings=settings, date=date, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"""
user_id = {request.chat_id} AND removal_time = 0
AND 
(
    ( -- Каждый год
        (
            status LIKE '%🎉%'
            OR
            status LIKE '%🎊%'
            OR
            status LIKE '%📆%'
        )
        AND date LIKE '{date[:-5]}.____'
    )
    OR
    ( -- Каждый месяц
        status LIKE '%📅%'
        AND date LIKE '{date[:2]}.__.____'
    )
    OR
    ( -- Каждую неделю
        status LIKE '%🗞%'
        AND strftime('%w', {sqlite_format_date('date')}) =
        CAST(strftime('%w', '{sqlite_format_date2(date)}') as TEXT)
    )
    OR
    ( -- Каждый день
        status LIKE '%📬%'
    )
)
"""
    backopenmarkup = generate_buttons(
        [[{get_theme_emoji("back"): date}, {"↖️": f"select one open recurring {date}"}]]
    )
    generated = EventsMessage(date, reply_markup=backopenmarkup, page=page)

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, prefix="|!")

    generated.format(
        title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})"
        + f'\n📅 {get_translate("recurring_events")}',
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({reldate})\n{markdown_text}\n",
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def event_status_message(event: Event, path: str = "0") -> TextMessage:
    if path == "0":
        sl = event.status.split(",")
        sl.extend([""] * (5 - len(sl)))
        buttons_data = get_translate("buttons.status page.0")
        markup = generate_buttons(
            [
                *[
                    [
                        {f"{title}".ljust(60, "⠀"): f"status page {page} {event.event_id} {event.date}"}
                        for (title, page) in row
                    ]
                    for row in buttons_data
                ],
                [
                    {
                        f"{i}"
                        if i
                        else " " * n: f"status delete {i} {event.event_id} {event.date}"
                        if i
                        else "None"
                    }
                    for n, i in enumerate(sl)
                ]
                if event.status != "⬜️"
                else [],
                [{get_theme_emoji("back"): f"event {event.event_id}"}],
            ]
        )
    else:  # status page
        buttons_data: tuple[tuple[str]] = get_translate(f"buttons.status page.{path}")
        markup = generate_buttons(
            [
                *[
                    [
                        {
                            f"{row}".ljust(60, "⠀"): (
                                f"status set "
                                f"{row.split(maxsplit=1)[0]} "
                                f"{event.event_id} "
                                f"{event.date}"
                            )
                        }
                        for row in status_column
                    ]
                    for status_column in buttons_data
                ],
                [
                    {
                        get_theme_emoji(
                            "back"
                        ): f"status page 0 {event.event_id} {event.date}"
                    },
                ],
            ]
        )
    day = DayInfo(event.date)
    text = f"""
<b>{get_translate("select.status_to_event")}
{event.date}.{event.event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
{add_status_effect(event.text, event.status)}
"""
    return TextMessage(text, markup)


def before_move_message(event_id: int) -> TextMessage | None:
    """
    Генерирует сообщение с кнопками удаления,
    удаления в корзину (для премиум) и изменения даты.
    """
    # Если события нет, то обновляем сообщение
    api_response = request.user.get_event(event_id)

    if not api_response[0]:
        return None

    event = api_response[1]

    delete_permanently = get_translate("delete_permanently")
    trash_bin = get_translate("trash_bin")

    is_wastebasket_available = request.user.settings.user_status in (1, 2) or is_admin_id(request.chat_id)

    markup = generate_buttons(
        [
            [
                {f"❌ {delete_permanently}": f"event_delete {event.event_id} {event.date} forever"},
                {f"🗑 {trash_bin}": f"event_delete {event.event_id} {event.date} wastebasket"}
                if is_wastebasket_available
                else {},
            ],
            [{get_theme_emoji("back"): f"event {event_id}"}],
        ]
    )

    day = DayInfo(event.date)
    text = f"""
<b>{get_translate("what_do_with_event")}:
{event.date}.{event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
{add_status_effect(event.text, event.status)}
"""
    return TextMessage(text, markup)



def search_message(query: str, id_list: list | tuple[str] = tuple(), page: int | str = 0) -> EventsMessage:
    """
    :param query: поисковый запрос
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с поиском:
        search(
            settings=settings,
            chat_id=chat_id,
            query=query
        )
    Изменить страницу:
        search(
            settings=settings,
            chat_id=chat_id,
            query=query,
            id_list=id_list,
            page=page
        )
    TODO шаблоны для поиска
    """
    query = query.replace("\n", " ").replace("--", "").strip()
    translate_search = get_translate("messages.search")

    if query.isspace():
        generated = EventsMessage(reply_markup=delmarkup())
        generated.format(
            title=f"🔍 {translate_search} {html.escape(query).strip()}:\n",
            if_empty=get_translate("errors.request_empty"),
        )
        return generated

    # re_day = re.compile(r"[#\b ]day=(\d{1,2})[\b]?")
    # re_month = re.compile(r"[#\b ]month=(\d{1,2})[\b]?")
    # re_year = re.compile(r"[#\b ]year=(\d{4})[\b]?")
    # re_id = re.compile(r"[#\b ]id=(\d{,6})[\b]?")
    # re_status = re.compile(r"[#\b ]status=(\S+)[\b]?")

    markup = generate_buttons(
        [
            [
                {get_theme_emoji("del"): "message_del"},
                {"🔄": "update search"},
                {"↖️": "select event open"},
            ]
        ]
    )
    generated = EventsMessage(reply_markup=markup, page=page)

    splitquery = " OR ".join(
        f"date LIKE '%{x}%' OR text LIKE '%{x}%' OR "
        f"status LIKE '%{x}%' OR event_id LIKE '%{x}%'"
        for x in query.replace("\n", " ").strip().split()
    )
    WHERE = f"(user_id = {request.chat_id} AND removal_time = 0) AND ({splitquery})"

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE)

    generated.format(
        title=f"🔍 {translate_search} {html.escape(query)}:",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({reldate})\n{markdown_text}\n",
        if_empty=get_translate("errors.nothing_found"),
    )

    return generated


def week_event_list_message(id_list: list | tuple[str] = tuple(), page: int | str = 0) -> EventsMessage:
    """
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с событиями в эту неделю:
        week_event_list(settings=settings, chat_id=chat_id)
    Изменить страницу:
        week_event_list(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
    """
    settings, chat_id = request.user.settings, request.chat_id
    WHERE = f"""
(user_id = {chat_id} AND removal_time = 0) AND (
    (
        {sqlite_format_date('date')}
        BETWEEN DATE('now', '{settings.timezone:+} hours')
            AND DATE('now', '+7 day', '{settings.timezone:+} hours')
    )
    OR
    ( -- Каждый год
        (
            status LIKE '%🎉%' OR status LIKE '%🎊%' OR status LIKE '%📆%'
        )
        AND
        (
            strftime('%m-%d', {sqlite_format_date('date')})
            BETWEEN strftime('%m-%d', 'now', '{settings.timezone:+} hours')
                AND strftime('%m-%d', 'now', '+7 day', '{settings.timezone:+} hours')
        )
    )
    OR
    ( -- Каждый месяц
        status LIKE '%📅%'
        AND SUBSTR(date, 1, 2) 
        BETWEEN strftime('%d', 'now', '{settings.timezone:+} hours')
            AND strftime('%d', 'now', '+7 day', '{settings.timezone:+} hours')
    )
    OR status LIKE '%🗞%' -- Каждую неделю
    OR status LIKE '%📬%' -- Каждый день
)
    """

    markup = [
        [
            {get_theme_emoji("back"): "menu"},
            {"🔄": "update week_event_list"},
            {"↖️": "select one open week_event_list"},
        ]
    ]
    generated = EventsMessage(
        reply_markup=generate_buttons(markup), page=page
    )
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(
            WHERE=WHERE,
            column="DAYS_BEFORE_EVENT(date, status), "
            "status LIKE '%📬%', status LIKE '%🗞%',status LIKE '%📅%', "
            "status LIKE '%📆%', status LIKE '%🎉%', status LIKE '%🎊%'",
            direction="ASC",
        )

    generated.format(
        title=f"📆 {get_translate('week_events')}",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n",
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def trash_can_message(id_list: list | tuple[str] = tuple(), page: int | str = 0) -> EventsMessage:
    """
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с корзиной:
        deleted(settings=settings, chat_id=chat_id)
    Изменить страницу:
        deleted(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"user_id = {request.chat_id} AND removal_time != 0"
    # Удаляем события старше 30 дней
    db.execute(queries["delete events_older_30_days"], commit=True)

    clean_bin_translate = get_translate("clean_bin")
    basket_translate = get_translate("messages.basket")
    message_empty_translate = get_translate("errors.message_empty")

    markup = generate_buttons(
        [
            [{"one": "select one deleted"}, {"many": "select many deleted"}],
            [
                {f"🧹 {clean_bin_translate}": "clean_bin"},
                {"🔄": "deleted"},
            ],
            [{get_theme_emoji("back"): "menu"}],
        ]
    )

    generated = EventsMessage(reply_markup=markup, page=page)

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE)

    generated.format(
        title=f"🗑 {basket_translate} 🗑",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({days_before_delete})\n{markdown_text}\n",
        if_empty=message_empty_translate,
    )
    return generated


def notifications_message(n_date: datetime | None = None, user_id_list: list | tuple[int | str, ...] = None, id_list: list | tuple[str] = tuple(), page: int | str = 0, message_id: int = -1, markup: InlineKeyboardMarkup | None = None, from_command: bool = False) -> None:
    """
    :param n_date: notifications date
    :param user_id_list: user_id_list
    :param id_list: Список из event_id
    :param page: Номер страницы
    :param message_id: message_id сообщения для изменения
    :param markup: markup для изменения сообщения
    :param from_command: Если True то сообщение присылается в любом случае

    Вызвать сообщение с будильником для всех:
        notifications()
    Вызвать сообщение для одного человека:
        notifications(user_id=[chat_id])
    Изменить страницу сообщения:
        notifications(user_id=[chat_id],
                      id_list=id_list,
                      page=page,
                      message_id=message_id,
                      markup=message.reply_markup)
    """
    if not user_id_list:
        n_time = now_time()
        with db.connection(), db.cursor():
            user_id_list = [
                int(user_id)
                for user in db.execute(
                    queries["select user_ids_for_sending_notifications"],
                    params=(n_time.hour, n_time.minute),
                )
                if user[0]
                for user_id in user[0].split(",")
            ]  # [('id1,id2,id3',)] -> [id1, id2, id3]

    for user_id in user_id_list:
        request.user = User(user_id)
        request.chat_id = user_id
        settings = request.user.settings

        if settings.notifications or from_command:
            if n_date is None:
                n_date = datetime.utcnow()
            dates = [
                n_date + timedelta(days=days, hours=settings.timezone)
                for days in (0, 1, 2, 3, 7)
            ]
            strdates = [f"{date:%d.%m.%Y}" for date in dates]
            weekdays = [
                "0" if (w := date.weekday()) == 6 else str(w + 1) for date in dates[:2]
            ]

            WHERE = f"""
user_id = {user_id} AND removal_time = 0
AND
(
    ( -- На сегодня и +1 день
        date IN ('{strdates[0]}', '{strdates[1]}')
    )
    OR
    ( -- Совпадения на +2, +3 и +7 дней
        date IN ({", ".join(f"'{date}'" for date in strdates[2:])})
        AND status NOT LIKE '%🗞%'
    )
    OR
    ( -- Каждый год
        (
            status LIKE '%🎉%'
            OR
            status LIKE '%🎊%'
            OR
            status LIKE '%📆%'
        )
        AND SUBSTR(date, 1, 5) IN ({", ".join(f"'{date[:5]}'" for date in strdates)})
    )
    OR
    ( -- Каждый месяц
        SUBSTR(date, 1, 2) IN ({", ".join(f"'{date[:2]}'" for date in strdates)})
        AND status LIKE '%📅%'
    )
    OR
    ( -- Каждую неделю
        strftime('%w', {sqlite_format_date('date')}) IN ({", ".join(f"'{w}'" for w in weekdays)})
        AND status LIKE '%🗞%'
    )
    OR
    ( -- Каждый день
        status LIKE '%📬%'
    )
)
"""

            generated = EventsMessage(
                reply_markup=generate_buttons(
                    [
                        [
                            {get_theme_emoji("back"): "menu"},
                            {get_theme_emoji("del"): "message_del"} if not from_command else {},
                            {"↖️": f"select one open bell {n_date:%d.%m.%Y}"},
                        ]
                    ]
                ),
                page=page,
            )

            if id_list:
                generated.get_events(WHERE=WHERE, values=id_list)
            else:
                generated.get_data(
                    WHERE=WHERE,
                    column="DAYS_BEFORE_EVENT(date, status), "
                    "status LIKE '%📬%', status LIKE '%🗞%', status LIKE '%📅%',"
                    "status LIKE '%📆%', status LIKE '%🎉%', status LIKE '%🎊%'",
                    direction="ASC",
                )

            if len(generated.event_list) or from_command:
                # Если в generated.event_list есть события
                # или
                # Если уведомления вызывали командой (сообщение на команду приходит даже если оно пустое)
                reminder_translate = get_translate("messages.reminder")

                generated.format(
                    title=f"🔔 {reminder_translate} 🔔 <i>{n_date.strftime('%d.%m.%Y')}</i>",
                    args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
                    "{weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n",
                    if_empty=get_translate("errors.message_empty"),
                )

                try:
                    if id_list or message_id != -1:
                        generated.edit(user_id, message_id, markup=markup)
                    else:
                        generated.send(user_id)

                    logging.info(f"notifications -> {user_id} -> Ok")
                except ApiTelegramException:
                    logging.info(f"notifications -> {user_id} -> Error")


def monthly_calendar_message(command: str | None = None, back: str | None = None, custom_text: str | None = None) -> TextMessage:
    text = custom_text if custom_text else get_translate("select.date")
    markup = create_monthly_calendar_keyboard(command=command, back=back)
    return TextMessage(text, markup)


def limits_message(date: datetime | str | None = None, message: Message | None = None) -> None:
    chat_id = request.chat_id
    if date is None or date == "now":
        date = now_time()

    if not is_valid_year(date.year):
        bot.send_message(chat_id, get_translate("errors.error"))
        return

    image = create_image(date.year, date.month, date.day)
    markup = generate_buttons([[{get_theme_emoji("back"): "menu"}]])
    if message and message.content_type == "photo":
        # Может изменять только сообщения с фотографией
        bot.edit_message_media(
            media=InputMediaPhoto(image),
            chat_id=chat_id,
            message_id=message.message_id,
            reply_markup=markup,
        )
    else:
        bot.send_photo(chat_id, image, reply_markup=markup)


def admin_message(page: int = 1) -> TextMessage:
    if not is_admin_id(request.user.user_id):
        text = "you are not admin\n"
        markup = generate_buttons([[{get_theme_emoji("back"): "menu"}]])
    else:
        text = f"""
😎 Админская 😎

Страница: {page}

<i>i - user id
s - user status
  a - admin
  b - ban
  n - normal
  p - premium
c - events count
m - max events count</i>
"""
        users = db.execute(
            f"""
SELECT user_id,
       user_status,
       user_max_event_id - 1 as user_max_event_id,
       (
          SELECT COUNT(event_id)
            FROM events
           WHERE settings.user_id = events.user_id
       ) as event_count
  FROM settings
 LIMIT 11
OFFSET :page;
""",
            params={"page": 0 if page < 2 else page * 10 - 10},
        )
        tg_numbers_emoji = "️⃣"
        template = "{} {} {} {}"
        markup = generate_buttons(
            [
                *[
                    [
                        {user: f"user {user_id}"},
                    ]
                    for user, user_id in (
                        (
                            template.format(
                                user_id,
                                (
                                    string_status[2]
                                    if is_admin_id(user_id)
                                    else string_status[user_status]
                                )[0],
                                event_count,
                                user_event_count,
                            ),
                            user_id,
                        )
                        for user_id, user_status, user_event_count, event_count in users[
                            :10
                        ]
                    )
                ],
                [
                    {
                        tg_numbers_emoji.join(c for c in f"{page - 1}")
                        + tg_numbers_emoji: f"admin {page - 1}"
                    }
                    if page > 1
                    else {" ": "None"},
                    {get_theme_emoji("back"): "menu"},
                    {
                        tg_numbers_emoji.join(c for c in f"{page + 1}")
                        + tg_numbers_emoji: f"admin {page + 1}"
                    }
                    if len(users) == 11
                    else {" ": "None"},
                ],
            ]
        )

    return TextMessage(text, markup)


def user_message(user_id: int) -> TextMessage | None:
    """
    lang
    sub_urls
    city
    timezone
    direction
    user_status
    notifications
    notifications_time
    user_max_event_id
    add_event_date
    theme
    """
    if not is_admin_id(request.user.user_id):
        return None

    if not all(request.user.check_user(user_id)):
        text = f"""👤 User 👤
user_id: {user_id}

Error: "User Not Exist"
"""
        markup = generate_buttons([[{get_theme_emoji("back"): "admin"}]])
        return TextMessage(text, markup)

    user = User(user_id)
    user_status = string_status[user.settings.user_status]
    text = f"""👤 User 👤
user_id: {user_id}

<pre><code class='language-settings'>lang:      {user.settings.lang}
sub_urls:  {bool(user.settings.sub_urls)}
city:      {user.settings.city}
timezone:  {user.settings.timezone}
direction: {'⬇️' if user.settings.direction == 'DESC' else '⬆️'}
status:    {user_status}
notice:    {'🔔' if user.settings.notifications else '🔕'}
n_time:    {user.settings.notifications_time}
theme:     {'⬛️' if user.settings.theme else '⬜️'}</code></pre>
"""
    markup = generate_buttons(
        [
            [
                {"🗑": f"user {user_id} del"},
                {
                    f"{'🔔' if not user.settings.notifications else '🔕'}": (
                        f"user {user_id} edit settings.notifications {int(not user.settings.notifications)}"
                    )
                },
            ],
            [
                {"ban": f"user {user_id} edit settings.status -1"},
                {"normal": f"user {user_id} edit settings.status 0"},
                {"premium": f"user {user_id} edit settings.status 1"},
            ],
            [{get_theme_emoji("back"): "admin"}, {"🔄": f"user {user_id}"}],
        ]
    )
    return TextMessage(text, markup)


def group_message() -> TextMessage:
    groups = [][:5]  # request.user.get_groups()
    if groups:
        string_groups = "\n\n".join(
            f"""
id:   {group.group_id}
name: {group.name}
            """.strip()
            for group in groups
        )
        text = f"""
👥 Группы 👥

У вас групп: {len(groups)}

{string_groups}
"""
        markup = [
            *[[{f"id: {group.group_id}": "None"}] for group in groups],
            [{"👥 Создать группу": "create_group"}] if len(groups) < 5 else [],
            [{get_theme_emoji("back"): "menu"}],
        ]
    else:
        text = "👥 Группы 👥\n\nУ вас групп: 0"
        markup = [
            [{"👥 Создать группу": "create_group"}],
            [{get_theme_emoji("back"): "menu"}],
        ]
    return TextMessage(text, generate_buttons(markup))


def account_message() -> TextMessage:
    email = "..."  # request.user.email
    password = "..."  # request.user.password
    string_email = "*" * len(email[:-3]) + email[-3:]
    string_password = "*" * len(password)
    markup = [
        [{"logout": "logout"}],
        [{get_theme_emoji("back"): "menu"}],
    ]
    return TextMessage(
        f"""
👤 Аккаунт 👤

<pre><code class='language-account'>id:       {request.user.user_id}
email:    {string_email}
password: {string_password}</code></pre>
""",
        generate_buttons(markup),
    )
