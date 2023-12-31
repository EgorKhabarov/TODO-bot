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
from tgbot.bot_actions import delete_message_action
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.message_generator import EventsMessage, TextMessage
from tgbot.buttons_utils import (
    delmarkup,
    create_monthly_calendar_keyboard,
    encode_id,
    edit_button_data,
)
from tgbot.utils import (
    sqlite_format_date2,
    is_secure_chat,
    add_status_effect,
    html_to_markdown,
    re_edit_message,
    highlight_text_difference,
)
from todoapi.api import User
from todoapi.types import db, string_status, Event
from todoapi.utils import (
    sqlite_format_date,
    is_valid_year,
    is_admin_id,
    is_premium_user,
)
from telegram_utils.buttons_generator import generate_buttons


def start_message() -> TextMessage:
    markup = generate_buttons(
        [
            [{"/menu": "mnm"}],
            [{"/calendar": "mnc ('now',)"}],
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
            {"📚 Помощь": "mnh"},
            {"📆 Календарь": "mnc ('now',)"},
        ],
        [
            {"👤 Аккаунт": "mna"},
            {"👥 Группы": "mngr"},
        ],
        [
            {"📆 7 дней": "pw"},
            {"🔔 Уведомления": "mnn"},
        ],
        [
            {"⚙️ Настройки": "mns"},
            {"🗑 Корзина": "mnb"} if is_premium_user(request.user) else {},
        ],
        [{"😎 Админская": "mnad"}] if is_secure_chat(request.query) else [],
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
        *("-3", f"ste timezone {utz - 3}") if utz > -10 else ("    ", "None")
    )
    time_zone_dict.__setitem__(
        *("-1", f"ste timezone {utz - 1}") if utz > -12 else ("   ", "None")
    )
    time_zone_dict[str_utz] = "ste timezone 3"
    time_zone_dict.__setitem__(
        *("+1", f"ste timezone {utz + 1}") if utz < 12 else ("   ", "None")
    )
    time_zone_dict.__setitem__(
        *("+3", f"ste timezone {utz + 3}") if utz < 10 else ("    ", "None")
    )

    notifications_time = {}
    if not_notifications_[0] == "🔕":
        now = datetime(2000, 6, 5, n_hours, n_minutes)
        notifications_time = {
            k: f"ste notifications_time {v}"
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
        html.escape(settings.city),
        str_utz,
        f"{now_time():%H:%M  %d.%m.%Y}",
        {"DESC": "⬇️", "ASC": "⬆️"}[settings.direction],
        "🔔" if settings.notifications else "🔕",
        f"{n_hours:0>2}:{n_minutes:0>2}" if settings.notifications else "",
        not_theme[2],
    )
    markup = generate_buttons(
        [
            [
                {f"🗣 {settings.lang}": f"ste lang {not_lang}"},
                {f"🔗 {bool(settings.sub_urls)}": f"ste sub_urls {not_sub_urls}"},
                {f"{not_direction_smile}": f"ste direction {not_direction_sql}"},
                {
                    f"{not_notifications_[0]}": f"ste notifications {not_notifications_[1]}"
                },
                {f"{not_theme[0]}": f"ste theme {not_theme[1]}"},
            ],
            [{k: v} for k, v in time_zone_dict.items()],
            [{k: v} for k, v in notifications_time.items()],
            [{get_translate("text.restore_to_default"): "std"}],
            [{get_theme_emoji("back"): "mnm"}],
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
        for row in keyboard:
            button = row[0]
            key = list(button)[0]
            if button[key] != "mnm":
                button[key] = "mnh " + button[key]
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


def daily_message(
    date: datetime | str, id_list: list[int] = (), page: int | str = 0
) -> EventsMessage:
    """
    Генерирует сообщение на один день

    :param date: Дата сообщения
    :param id_list: Список из event_id
    :param page: Номер страницы
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%d.%m.%Y")
    WHERE = (
        f"user_id = {request.user.user_id} "
        f"AND date = '{date:%d.%m.%Y}' "
        f"AND removal_time = 0"
    )

    y = date - timedelta(days=1)
    t = date + timedelta(days=1)
    yesterday = f"dl {y:%d.%m.%Y}" if is_valid_year(y.year) else "None"
    tomorrow = f"dl {t:%d.%m.%Y}" if is_valid_year(t.year) else "None"

    markup = generate_buttons(
        [
            [
                {get_theme_emoji("add"): f"ea {date:%d.%m.%Y}"},
                {"🔼": "None"},
                {"↕️": "None"},
                {"Menu": "mnm"},
            ],
            [
                {get_theme_emoji("back"): f"mnc (({date:%Y},{int(date.month)}),)"},
                {"<": yesterday},
                {">": tomorrow},
                {"🔄": f"dl {date:%d.%m.%Y}"},
            ],
        ]
    )
    generated = EventsMessage(f"{date:%d.%m.%Y}", reply_markup=markup, page=page)

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE, lambda np, ids: f"pd {date:%d.%m.%Y} {np} {ids}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(
        generated.reply_markup, 0, 1, f"se _ {string_id} pd {date:%d.%m.%Y}"
    )
    edit_button_data(
        generated.reply_markup, 0, 2, f"ses _ {string_id} pd {date:%d.%m.%Y}"
    )

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
        generated.reply_markup.row(
            InlineKeyboardButton("📅", callback_data=f"pr {date:%d.%m.%Y}")
        )

    return generated


def event_message(
    event_id: int, in_wastebasket: bool = False, message_id: int | None = None
) -> TextMessage | None:
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
        edit_date = get_translate("text.edit_date")
        markup = [
            [
                {
                    "📝": {
                        "switch_inline_query_current_chat": (
                            f"event({event_id}, {message_id}).text\n"
                            f"{html.unescape(event.text)}"
                        )
                    }
                }
                if message_id
                else {"📝": "None"},
                {"🏷" or "🚩": f"esp 0 {event.date} {event_id}"},
                {"🗑": f"ebd {event_id} {event.date}"},
            ],
            [
                # add_media = get_translate("add_media") {f"🖼 {add_media}": "None"}, # "✏️"
                {f"📅 {edit_date}": f"esdt {event_id} {event.date}"},
            ],
            [
                {get_theme_emoji("back"): f"dl {event.date}"},
                {"ℹ️": f"eab {event_id}"},
                {"🔄": f"em {event_id}"},
            ],
        ]
    else:
        relatively_date = get_translate("func.deldate")(event.days_before_delete())
        delete_permanently_translate = get_translate("text.delete_permanently")
        recover_translate = get_translate("text.recover")
        markup = [
            [
                {f"❌ {delete_permanently_translate}": f"bed {event_id}"},
                {f"↩️ {recover_translate}": f"ber {event_id} {event.date}"},
            ],
            [{get_theme_emoji("back"): "mnb"}],
        ]
    text = f"""
<b>{get_translate("select.what_do_with_event")}:
{event.date}.{event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({relatively_date})
{add_status_effect(event.text, event.status)}
"""
    return TextMessage(text, generate_buttons(markup))


def events_message(
    id_list: list[int],
    is_in_wastebasket: bool = False,
    is_in_search: bool = False,
) -> EventsMessage | None:
    """
    Сообщение для взаимодействия с одним событием
    """

    generated = EventsMessage()
    generated.get_events(
        WHERE=f"removal_time != {int(not is_in_wastebasket)}",
        values=id_list,
    )

    string_id = encode_id(id_list)
    if generated.event_list:
        date = generated.event_list[0].date
    else:
        date = ""
    if not is_in_wastebasket:
        markup = [
            [
                # {"➕🏷": f"essa {string_id}"},  # events status
                {"📅": f"essd {string_id}"},  # events edit date
                {"🗑": f"esbd {string_id}"},  # events before delete
            ],
            [{get_theme_emoji("back"): "us" if is_in_search else f"dl {date}"}],
        ]
        args = (
            "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
            "{weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n"
        )
    else:
        delete_permanently_translate = get_translate("text.delete_permanently")
        recover_translate = get_translate("text.recover")
        markup = [
            [
                {f"❌ {delete_permanently_translate}": f"bsd {string_id}"},
                {f"↩️ {recover_translate}": f"bsr {string_id} {date}"},
            ],
            [{get_theme_emoji("back"): "mnb"}],
        ]
        args = (
            "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
            "{weekday}</i></u> ({days_before_delete})\n{markdown_text}\n"
        )

    generated.format(
        title=f"<b>{get_translate('select.what_do_with_events')}:</b>",
        args=args,
        if_empty=get_translate("errors.message_empty"),
    )
    generated.reply_markup = generate_buttons(markup)
    return generated


def about_event_message(event_id: int) -> TextMessage | None:
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
<b>{get_translate("text.event_about_info")}:
{event.date}.{event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
<pre><code class='language-event-metadata'>{len(event.text)} - длинна текста
{parse_utc_datetime(event.adding_time)} - время добавления
{parse_utc_datetime(event.recent_changes_time)} - время последних изменений</code></pre>
"""
    markup = [[{get_theme_emoji("back"): f"em {event_id}"}]]
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

    response, event = user.get_event(event_id)

    if not response:
        return 1  # Этого события нет

    text = markdown_text.split("\n", maxsplit=1)[-1].strip("\n")
    # Убираем @bot_username из начала текста remove_html_escaping
    edit_text = markdown_text.split(maxsplit=1)[-1]

    if len(message.text.split("\n")) == 1:
        try:
            before_event_delete_message(event_id).send(chat_id)
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
                {get_theme_emoji("del"): "md"},
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
<b>{get_translate("text.are_you_sure_edit")}:
{event.date} {event_id}</b> <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
<i>{text_diff}</i>
"""
        generated = TextMessage(
            text,
            markup=generate_buttons(
                [
                    [
                        {get_theme_emoji("back"): f"em {event.event_id}"},
                        {"📝": {"switch_inline_query_current_chat": edit_text}},
                        {"💾": f"eet {event.event_id} {event.date}"},
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


def recurring_events_message(
    date: str, id_list: list[int] = (), page: int | str = 0
) -> EventsMessage:
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
        [[{get_theme_emoji("back"): f"pd {date}"}, {"↖️": "None"}]]
    )
    generated = EventsMessage(date, reply_markup=backopenmarkup, page=page)

    if id_list:
        generated.get_events(WHERE, id_list)
    else:
        generated.get_data(WHERE, lambda np, ids: f"pr {date} {np} {ids}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.reply_markup, 0, 1, f"se o {string_id} pr {date}")
    generated.format(
        title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})"
        + f'\n📅 {get_translate("text.recurring_events")}',
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
                        {
                            f"{title}".ljust(60, "⠀"): (
                                f"esp {page} {event.date} {event.event_id}"
                            )
                        }
                        for (title, page) in row
                    ]
                    for row in buttons_data
                ],
                [
                    {
                        f"{i}"
                        if i
                        else " " * n: f"esr {i} {event.date} {event.event_id}"
                        if i
                        else "None"
                    }
                    for n, i in enumerate(sl)
                ]
                if event.status != "⬜️"
                else [],
                [{get_theme_emoji("back"): f"em {event.event_id}"}],
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
                                f"esa "
                                f"{row.split(maxsplit=1)[0]} "
                                f"{event.date} "
                                f"{event.event_id}"
                            )
                        }
                        for row in status_column
                    ]
                    for status_column in buttons_data
                ],
                [{get_theme_emoji("back"): f"esp 0 {event.date} {event.event_id}"}],
            ]
        )
    day = DayInfo(event.date)
    text = f"""
<b>{get_translate("select.status_to_event")}
{event.date}.{event.event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
{add_status_effect(event.text, event.status)}
"""
    return TextMessage(text, markup)


def edit_event_date_message(
    event_id: int, date: datetime
) -> TextMessage | EventsMessage:
    response, event = request.user.get_event(event_id)
    if not response:
        return daily_message(date)

    day = DayInfo(event.date)
    text = f"""
<b>{get_translate("select.new_date")}:
{event.date}.{event_id}.</b>{event.status}  <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
{add_status_effect(event.text, event.status)}
    """

    markup = create_monthly_calendar_keyboard(
        (date.year, date.month), "eds", "em", f"{event_id}"
    )
    return TextMessage(text, markup)


def edit_events_date_message(id_list: list[int], date: datetime | None = None):
    if date is None:
        date = now_time()
    generated = EventsMessage()
    generated.get_events("1", id_list)
    generated.format(
        title=f"<b>{get_translate('select.what_do_with_events')}:</b>",
        args=(
            "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
            "{weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n"
        ),
        if_empty=get_translate("errors.message_empty"),
    )
    string_ids = encode_id(id_list)
    generated.reply_markup = create_monthly_calendar_keyboard(
        (date.year, date.month), "esds", "esm", f"{string_ids}"
    )
    return generated


def before_event_delete_message(event_id: int) -> TextMessage | None:
    """
    Генерирует сообщение с кнопками удаления,
    удаления в корзину (для премиум) и изменения даты.
    """
    # Если события нет, то обновляем сообщение
    response, event = request.user.get_event(event_id)

    if not response:
        return None

    delete_permanently = get_translate("text.delete_permanently")
    trash_bin = get_translate("text.trash_bin")

    is_wastebasket_available = (
        is_admin_id(request.chat_id) or request.user.settings.user_status == 1
    )

    markup = generate_buttons(
        [
            [
                {f"❌ {delete_permanently}": f"ed {event.event_id} {event.date}"},
                {f"🗑 {trash_bin}": f"edb {event.event_id} {event.date}"}
                if is_wastebasket_available
                else {},
            ],
            [{get_theme_emoji("back"): f"em {event_id}"}],
        ]
    )

    day = DayInfo(event.date)
    text = f"""
<b>{get_translate("select.what_do_with_event")}:
{event.date}.{event_id}.</b>{event.status} <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
{add_status_effect(event.text, event.status)}
"""
    return TextMessage(text, markup)


def before_events_delete_message(
    id_list: list[int], in_wastebasket: bool = False
) -> TextMessage | None:
    """
    Генерирует сообщение с кнопками удаления,
    удаления в корзину (для премиум) и изменения даты.
    """
    generated = EventsMessage()
    generated.get_events(
        WHERE=f"removal_time != {int(not in_wastebasket)}",
        values=id_list,
    )

    delete_permanently = get_translate("text.delete_permanently")
    trash_bin = get_translate("text.trash_bin")

    is_wastebasket_available = (
        is_admin_id(request.chat_id) or request.user.settings.user_status == 1
    )

    string_id = encode_id(id_list)
    if generated.event_list:
        date = generated.event_list[0].date
    else:
        date = ""
    if not in_wastebasket:
        markup = [
            [
                {f"❌ {delete_permanently}": f"esd {string_id} {date}"},
                {f"🗑 {trash_bin}": f"esdb {string_id} {date}"}
                if is_wastebasket_available
                else {},
            ],
            [{get_theme_emoji("back"): f"esm {string_id}"}],
        ]
        args = (
            "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
            "{weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n"
        )
    else:
        return events_message(id_list, in_wastebasket)

    generated.format(
        title=f"<b>{get_translate('select.what_do_with_events')}:</b>",
        args=args,
        if_empty=get_translate("errors.message_empty"),
    )
    generated.reply_markup = generate_buttons(markup)
    return generated


def search_message(
    query: str, id_list: list[int] = (), page: int | str = 0
) -> EventsMessage:
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
            title=f"🔍 {translate_search} ...:\n",
            if_empty=get_translate("errors.request_empty"),
        )
        return generated

    # re_day = re.compile(r"[#\b ]day=(\d{1,2})[\b]?")
    # re_month = re.compile(r"[#\b ]month=(\d{1,2})[\b]?")
    # re_year = re.compile(r"[#\b ]year=(\d{4})[\b]?")
    # re_id = re.compile(r"[#\b ]id=(\d{,6})[\b]?")
    # re_status = re.compile(r"[#\b ]status=(\S+)[\b]?")

    markup = generate_buttons(
        [[{get_theme_emoji("del"): "md"}, {"🔄": "us"}, {"↖️": "None"}, {"↕️": "None"}]]
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
        generated.get_data(WHERE, lambda np, ids: f"ps {np} {ids}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.reply_markup, 0, 2, f"se os {string_id} us")
    edit_button_data(generated.reply_markup, 0, 3, f"ses s {string_id} us")
    generated.format(
        title=f"🔍 {translate_search} <u>{html.escape(query)}</u>:",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({reldate})\n{markdown_text}\n",
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def week_event_list_message(
    id_list: list[int] = (), page: int | str = 0
) -> EventsMessage:
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

    markup = generate_buttons(
        [[{get_theme_emoji("back"): "mnm"}, {"🔄": "mnw"}, {"↖️": "None"}]]
    )
    generated = EventsMessage(reply_markup=markup, page=page)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(
            WHERE=WHERE,
            call_back_func=lambda np, ids: f"pw {np} {ids}",
            column="DAYS_BEFORE_EVENT(date, status), "
            "status LIKE '%📬%', status LIKE '%🗞%',status LIKE '%📅%', "
            "status LIKE '%📆%', status LIKE '%🎉%', status LIKE '%🎊%'",
            direction="ASC",
        )
    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.reply_markup, 0, 2, f"se o {string_id} mnw")
    generated.format(
        title=f"📆 {get_translate('text.week_events')}",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n",
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def trash_can_message(id_list: list[int] = (), page: int | str = 0) -> EventsMessage:
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

    clean_bin_translate = get_translate("text.clean_bin")
    basket_translate = get_translate("messages.basket")
    message_empty_translate = get_translate("errors.message_empty")

    markup = generate_buttons(
        [
            [{"🔼": "None"}, {"↕️": "None"}],
            [{f"🧹 {clean_bin_translate}": "bcl"}, {"🔄": "mnb"}],
            [{get_theme_emoji("back"): "mnm"}],
        ]
    )
    generated = EventsMessage(reply_markup=markup, page=page)

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE, lambda np, ids: f"pb {np} {ids}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.reply_markup, 0, 0, f"se b {string_id} mnb")
    edit_button_data(generated.reply_markup, 0, 1, f"ses b {string_id} mnb")

    generated.format(
        title=f"🗑 {basket_translate} 🗑",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({days_before_delete})\n{markdown_text}\n",
        if_empty=message_empty_translate,
    )
    return generated


def send_notifications_messages() -> None:
    n_date = datetime.utcnow()
    with db.connection(), db.cursor():
        user_id_list = [
            int(user_id)
            for user in db.execute(
                queries["select user_ids_for_sending_notifications"],
                params=(n_date.hour, n_date.minute),
            )
            if user[0]
            for user_id in user[0].split(",")
        ]  # [('id1,id2,id3',)] -> [id1, id2, id3]

    for user_id in user_id_list:
        request.user = User(user_id)
        request.chat_id = user_id
        settings = request.user.settings

        if settings.notifications:
            generated = notification_message(user_id, from_command=True)
            if generated.event_list:
                try:
                    generated.send(user_id)
                    logging.info(f"notifications -> {user_id} -> Ok")
                except ApiTelegramException:
                    logging.info(f"notifications -> {user_id} -> Error")


def notification_message(
    user_id: int,
    n_date: datetime | None = None,
    id_list: list[int] = (),
    page: int | str = 0,
    from_command: bool = False,
) -> EventsMessage | None:
    request.user = User(user_id)
    request.chat_id = user_id
    settings = request.user.settings

    if n_date is None:
        n_date = datetime.utcnow()

    dates = [
        n_date + timedelta(days=days, hours=settings.timezone)
        for days in (0, 1, 2, 3, 7)
    ]
    weekdays = ["0" if (w := date.weekday()) == 6 else f"{w + 1}" for date in dates[:2]]
    WHERE = f"""
user_id = {user_id}
AND
removal_time = 0
AND
status NOT LIKE '%🔕%'
AND
(
    ( -- На сегодня и +1 день
        date IN ('{dates[0]:%d.%m.%Y}', '{dates[1]:%d.%m.%Y}')
    )
    OR
    ( -- Совпадения на +2, +3 и +7 дней
        date IN ({", ".join(f"'{date:%d.%m.%Y}'" for date in dates[2:])})
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
        AND SUBSTR(date, 1, 5) IN ({", ".join(f"'{date:%d.%m}'" for date in dates)})
    )
    OR
    ( -- Каждый месяц
        SUBSTR(date, 1, 2) IN ({", ".join(f"'{date:%d}'" for date in dates)})
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
    markup = generate_buttons(
        [
            [
                {get_theme_emoji("back"): "mnn" if from_command else "mnm"},
                {get_theme_emoji("del"): "md"} if not from_command else {},
                {"↖️": "None"},
            ]
        ]
    )

    generated = EventsMessage(reply_markup=markup, page=page)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(
            WHERE=WHERE,
            call_back_func=lambda np, ids: f"pn {n_date:%d.%m.%Y} {np} {ids}",
            column=(
                "DAYS_BEFORE_EVENT(date, status), "
                "status LIKE '%📬%', status LIKE '%🗞%', status LIKE '%📅%',"
                "status LIKE '%📆%', status LIKE '%🎉%', status LIKE '%🎊%'"
            ),
            direction="ASC",
        )
        string_id = encode_id([event.event_id for event in generated.event_list])
        edit_button_data(
            generated.reply_markup, 0, -1, f"se o {string_id} mnn {n_date:%d.%m.%Y}"
        )

    if generated.event_list or from_command:
        reminder_translate = get_translate("messages.reminder")
        generated.format(
            title=f"🔔 {reminder_translate} <b>{n_date:%d.%m.%Y}</b>🔔",
            args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
            "{weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n",
            if_empty=get_translate("errors.message_empty"),
        )
        return generated
    return None


def monthly_calendar_message(
    command: str | None = None, back: str | None = None, custom_text: str | None = None
) -> TextMessage:
    text = custom_text if custom_text else get_translate("select.date")
    markup = create_monthly_calendar_keyboard(command=command, back=back)
    return TextMessage(text, markup)


def limits_message(
    date: datetime | str | None = None, message: Message | None = None
) -> None:
    chat_id = request.chat_id
    if date is None or date == "now":
        date = now_time()

    if not is_valid_year(date.year):
        TextMessage(get_translate("errors.error")).send(chat_id)
        return

    image = create_image(date.year, date.month, date.day)
    markup = generate_buttons([[{get_theme_emoji("back"): "mnm"}]])
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
        markup = generate_buttons([[{get_theme_emoji("back"): "mnm"}]])
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

↖️ <i>reply</i> <u>int</u> <u>str</u>: ("user_id"? | "page")
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
                    [{user: f"mnau {user_id}"}]
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
                        + tg_numbers_emoji: f"mnad {page - 1}"
                    }
                    if page > 1
                    else {" ": "None"},
                    {get_theme_emoji("back"): "mnm"},
                    {
                        tg_numbers_emoji.join(c for c in f"{page + 1}")
                        + tg_numbers_emoji: f"mnad {page + 1}"
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
        markup = generate_buttons([[{get_theme_emoji("back"): "mnad"}]])
        return TextMessage(text, markup)

    user = User(user_id)
    user_status = string_status[user.settings.user_status]
    text = f"""👤 User 👤
user_id: {user_id}

<pre><code class='language-settings'>lang:          {user.settings.lang}
sub_urls:      {bool(user.settings.sub_urls)}
city:          {html.escape(user.settings.city)}
timezone:      {user.settings.timezone}
direction:     {'⬇️' if user.settings.direction == 'DESC' else '⬆️'}
status:        {user_status}
notifications: {'🔔' if user.settings.notifications else '🔕'}
n_time:        {user.settings.notifications_time}
theme:         {'⬛️' if user.settings.theme else '⬜️'}</code></pre>
"""
    markup = generate_buttons(
        [
            [
                {"🗑": f"mnau {user_id} del"},
                {
                    f"{'🔔' if not user.settings.notifications else '🔕'}": (
                        f"mnau {user_id} edit settings.notifications {int(not user.settings.notifications)}"
                    )
                },
            ],
            [
                {"ban": f"mnau {user_id} edit settings.status -1"},
                {"normal": f"mnau {user_id} edit settings.status 0"},
                {"premium": f"mnau {user_id} edit settings.status 1"},
            ],
            [{get_theme_emoji("back"): "mnad"}, {"🔄": f"mnau {user_id}"}],
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
            [{get_theme_emoji("back"): "mnm"}],
        ]
    else:
        text = "👥 Группы 👥\n\nУ вас групп: 0"
        markup = [
            [{"👥 Создать группу": "create_group"}],
            [{get_theme_emoji("back"): "mnm"}],
        ]
    return TextMessage(text, generate_buttons(markup))


def account_message() -> TextMessage:
    email = "..."  # request.user.email
    password = "..."  # request.user.password
    string_email = "*" * len(email[:-3]) + email[-3:]
    string_password = "*" * len(password)
    markup = [
        [{"logout": "logout"}],
        [{get_theme_emoji("back"): "mnm"}],
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


def select_one_message(
    id_list: list[int],
    back_data: str,
    is_in_wastebasket: bool = False,
    is_in_search: bool = False,
    is_open: bool = False,
    message_id: int = None,
) -> TextMessage | None:
    # Если событий нет
    if len(id_list) == 0:
        return None

    events_list = request.user.get_events(id_list, is_in_wastebasket)[1]

    # Если событий нет
    if len(events_list) == 0:
        return None

    # Если событие одно
    if len(events_list) == 1:
        event = events_list[0]
        if is_open:
            generated = daily_message(event.date)
        else:
            generated = event_message(event.event_id, is_in_wastebasket, message_id)
        return generated

    # Если событий несколько
    markup = []
    for event in events_list:
        button_title = f"{event.event_id}.{event.status} {event.text}"
        button_title = button_title.ljust(60, "⠀")[:60]

        if is_in_wastebasket or is_in_search or is_open:
            button_title = f"{event.date}.{button_title}"[:60]

        if is_open:
            button_data = f"dl {event.date}"
        elif is_in_wastebasket:
            button_data = f"bem {event.event_id}"
        else:
            button_data = f"em {event.event_id}"

        markup.append([{button_title: button_data}])

    if is_open:
        text = get_translate("select.event_to_open")
    else:
        text = get_translate("select.event")

    markup.append([{get_theme_emoji("back"): back_data}])
    return TextMessage(text, generate_buttons(markup))


def select_events_message(
    id_list: list[int],
    back_data: str,
    is_in_wastebasket: bool = False,
    is_in_search: bool = False,
) -> TextMessage | None:
    # Если событий нет
    if len(id_list) == 0:
        return None

    events_list = request.user.get_events(id_list, is_in_wastebasket)[1]

    # Если событий нет
    if len(events_list) == 0:
        return None

    # Если событие одно
    if len(events_list) == 1:
        return events_message([events_list[0].event_id], is_in_wastebasket)

    # Если событий несколько
    markup = []
    for n, event in enumerate(events_list):
        button_title = f"{event.event_id}.{event.status} {event.text}"
        button_title = button_title.ljust(60, "⠀")[:60]
        if is_in_wastebasket or is_in_search:
            button_title = f"{event.date}.{button_title}"[:60]

        if is_in_wastebasket:
            button_data = f"sbon {n} 0 {event.event_id}"
        else:
            button_data = f"son {n} 0 {event.event_id}"

        markup.append([{button_title: button_data}])

    markup.append(
        [
            {get_theme_emoji("back"): back_data},
            {"☑️": "sbal" if is_in_wastebasket else "sal"},
            {"↗️": "bsm _" if is_in_wastebasket else f"esm _"},
        ]
    )
    generated = TextMessage(get_translate("select.events"), generate_buttons(markup))
    return generated
