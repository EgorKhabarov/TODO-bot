import re
import html
import logging
from datetime import timedelta, datetime
from typing import Literal

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

# noinspection PyPackageRequirements
from telebot import formatting

# noinspection PyPackageRequirements
from telebot.types import InlineKeyboardButton, Message

from tgbot.bot import bot
from tgbot.request import request
from tgbot.limits import get_limit_link
from tgbot.bot_actions import delete_message_action
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.time_utils import parse_utc_datetime
from tgbot.message_generator import (
    TextMessage,
    EventMessage,
    EventsMessage,
    event_formats,
)
from tgbot.buttons_utils import (
    delmarkup,
    create_monthly_calendar_keyboard,
    encode_id,
    edit_button_data,
)
from tgbot.types import TelegramAccount
from tgbot.utils import (
    sqlite_format_date2,
    html_to_markdown,
    re_edit_message,
    highlight_text_difference,
)
from todoapi.types import db, Event, group_limits
from todoapi.utils import sqlite_format_date, is_valid_year, chunks
from todoapi.exceptions import EventNotFound, GroupNotFound, UserNotFound
from telegram_utils.buttons_generator import generate_buttons


def start_message() -> TextMessage:
    markup = generate_buttons([[{"/menu": "mnm"}], [{"/calendar": "mnc ('now',)"}]])
    text = get_translate("messages.start")
    return TextMessage(text, markup)


def menu_message() -> TextMessage:
    """
    Генерирует сообщение меню
    """
    (
        translate_menu,
        translate_help,
        translate_calendar,
        translate_account,
        translate_groups,
        translate_seven_days,
        translate_notifications,
        translate_Settings,
        translate_wastebasket,
        translate_admin,
        translate_group,
    ) = get_translate("messages.menu")

    text = translate_menu
    markup = [
        [
            {f"📚 {translate_help}": "mnh"},
            {f"📆 {translate_calendar}": "mnc ('now',)"},
        ],
        [
            {f"👤 {translate_account}": "mna"},
            {f"👥 {translate_groups}": "mngrs"},
        ]
        if request.is_user
        else [],
        [
            {f"📆 {translate_seven_days}": "pw"},
            {f"🔔 {translate_notifications}": "mnn"},
        ],
        [
            {f"⚙️ {translate_Settings}": "mns"},
            {f"🗑 {translate_wastebasket}": "mnb"}
            if (request.is_user and request.entity.is_premium) or request.is_member
            else {},
        ],
        [{f"👥 {translate_group}": "mngr self"} if request.is_member else {}],
    ]
    return TextMessage(text, generate_buttons(markup))


def settings_message() -> TextMessage:
    """
    Ставит настройки для пользователя chat_id
    """
    settings = request.entity.settings
    not_lang = "ru" if settings.lang == "en" else "en"
    not_sub_urls = 1 if settings.sub_urls == 0 else 0
    not_direction_smile = {"DESC": "⬆️", "ASC": "⬇️"}[settings.direction]
    not_direction_sql = {"DESC": "ASC", "ASC": "DESC"}[settings.direction]
    not_notifications_ = (("🔕", 1), ("🔔", 2), ("📆", 0))[settings.notifications]
    n_hours, n_minutes = [int(i) for i in settings.notifications_time.split(":")]
    not_theme = ("⬜", 0, "⬛️") if settings.theme else ("⬛️", 1, "⬜")

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
    if settings.notifications != 0:
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
        f"{request.entity.now_time():%Y.%m.%d  <u>%H:%M</u>}",
        {"DESC": "⬇️", "ASC": "⬆️"}[settings.direction],
        ("🔕", "🔔", "📆")[settings.notifications],
        f"{n_hours:0>2}:{n_minutes:0>2}" if settings.notifications else "",
        not_theme[2],
    )
    markup = generate_buttons(
        [
            [
                {f"🗣 {settings.lang}": f"ste lang {not_lang}"},
                {f"🔗 {bool(settings.sub_urls)}": f"ste sub_urls {not_sub_urls}"},
                {not_direction_smile: f"ste direction {not_direction_sql}"},
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
        # Изменяем последнюю кнопку
        last_button: dict = keyboard[-1][-1]
        k, v = last_button.popitem()
        new_k = (
            get_theme_emoji("back") + k.removeprefix("🔙") if k.startswith("🔙") else k
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

    WHERE = """
user_id IS ?
AND group_id IS ?
AND date = ?
AND removal_time IS NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
        f"{date:%d.%m.%Y}",
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
    generated = EventsMessage(f"{date:%d.%m.%Y}", markup=markup, page=page)

    if id_list:
        generated.get_page_events(WHERE, params, id_list)
    else:
        generated.get_pages_data(WHERE, params, f"pd {date:%d.%m.%Y}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 1, f"se _ {string_id} pd {date:%d.%m.%Y}")
    edit_button_data(generated.markup, 0, 2, f"ses _ {string_id} pd {date:%d.%m.%Y}")

    generated.format(
        title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})",
        args=event_formats["dl"],
        if_empty=get_translate("errors.nodata"),
    )

    # Добавить дополнительную кнопку для дней в которых есть праздники
    daylist = [
        x[0]
        for x in db.execute(
            f"""
-- Если находит, то добавлять кнопку повторяющихся событий
SELECT DISTINCT date
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND date != :date
       AND (
    ( -- Каждый год
        (
            status LIKE '%🎉%'
            OR status LIKE '%🎊%'
            OR status LIKE '%📆%'
        )
        AND date LIKE :y_date
    )
    OR
    ( -- Каждый месяц
        status LIKE '%📅%'
        AND date LIKE :m_date
    )
    OR
    ( -- Каждую неделю
        status LIKE '%🗞%'
        AND
        strftime('%w', {sqlite_format_date('date')}) =
        CAST(strftime('%w', {sqlite_format_date(':date')}) as TEXT)
    )
    OR
    ( -- Каждый день
        status LIKE '%📬%'
    )
)
LIMIT 1;
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
                "date": f"{date:%d.%m.%Y}",
                "y_date": f"{date:%d.%m}.____",
                "m_date": f"{date:%d}.__.____",
            },
        )
    ]

    if daylist:
        generated.markup.row(
            InlineKeyboardButton("📅", callback_data=f"pr {date:%d.%m.%Y}")
        )

    return generated


def event_message(
    event_id: int, in_wastebasket: bool = False, message_id: int | None = None
) -> EventMessage | None:
    """
    Сообщение для взаимодействия с одним событием
    """
    generated = EventMessage(event_id, in_wastebasket)
    event = generated.event
    if not event:
        return None

    if not in_wastebasket:
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
                {"📋": f"esh {event_id} {event.date}"},
                {"*️⃣": "None"},
                {"📅": f"esdt {event_id} {event.date}"},
            ],
            [
                {"ℹ️": f"eab {event_id} {event.date}"},
                {"🗄": f"eh {event_id} {event.date}"},
                {"🖼": "None"},
            ],
            [
                {get_theme_emoji("back"): f"dl {event.date}"},
                {" ": "None"},
                {"🔄": f"em {event_id}"},
            ],
        ]
        format_key = "dt"
    else:
        delete_permanently_translate = get_translate("text.delete_permanently")
        recover_translate = get_translate("text.recover")
        markup = [
            [
                {f"❌ {delete_permanently_translate}": f"bed {event_id}"},
                {f"↩️ {recover_translate}": f"ber {event_id} {event.date}"},
            ],
            [{get_theme_emoji("back"): "mnb"}],
        ]
        format_key = "b"

    generated.format(
        f"{get_translate('select.what_do_with_event')}:",
        event_formats[format_key],
        generate_buttons(markup),
    )
    return generated


def events_message(
    id_list: list[int], is_in_wastebasket: bool = False
) -> EventsMessage:
    """
    Сообщение для взаимодействия с одним событием
    """
    generated = EventsMessage()
    WHERE = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS {'NOT' if is_in_wastebasket else ''} NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    generated.get_page_events(WHERE, params, id_list)
    date = generated.event_list[0].date if generated.event_list else ""
    string_id = encode_id(id_list)

    if is_in_wastebasket:
        args_key = "b"
        delete_permanently_translate = get_translate("text.delete_permanently")
        recover_translate = get_translate("text.recover")
        markup = [
            [
                {f"❌ {delete_permanently_translate}": f"bsd {string_id}"},
                {f"↩️ {recover_translate}": f"bsr {string_id} {date}"},
            ],
            [{get_theme_emoji("back"): "mnb"}],
        ]
    else:
        args_key = "r"
        markup = [
            [
                # {"➕🏷": f"essa {string_id}"},  # events status
                {"📅": f"essd {string_id}"},  # events edit date
                {"🗑": f"esbd {string_id}"},  # events before delete
            ],
            [{get_theme_emoji("back"): f"dl {date}"}],
        ]

    generated.format(
        title=f"<b>{get_translate('select.what_do_with_events')}:</b>",
        args=event_formats[args_key],
        if_empty=get_translate("errors.message_empty"),
    )
    generated.markup = generate_buttons(markup)
    return generated


def about_event_message(event_id: int) -> EventMessage | None:
    generated = EventMessage(event_id)
    event = generated.event
    if not event:
        return None

    title, text_length, time_added, time_last_changes = get_translate(
        "text.event_about_info"
    )
    text = f"""
{len(event.text)} - {text_length}
{parse_utc_datetime(event.adding_time)} - {time_added}
{parse_utc_datetime(event.recent_changes_time)} - {time_last_changes}
"""
    event.text = formatting.hpre(text.strip(), language="language-event-metadata")
    generated.format(
        f"{title}:",
        event_formats["a"],
        generate_buttons([[{get_theme_emoji("back"): f"em {event_id}"}]]),
    )
    return generated


def event_show_mode_message(event_id: int) -> EventMessage | None:
    generated = EventMessage(event_id)
    event = generated.event
    if not event:
        return None

    generated.format(
        "",
        event_formats["s"],
        generate_buttons([[{get_theme_emoji("back"): f"em {event_id}"}]]),
    )
    return generated


def event_history(event_id: int, date: datetime, page: int = 1) -> EventMessage | None:
    generated = EventMessage(event_id)
    event = generated.event
    if not event:
        return None

    text = "\n\n".join(
        f"""
[<u>{parse_utc_datetime(time)}] <b>{action}</b></u>
{formatting.hpre(str(old_val)[:50].strip(), language='language-old')}
{formatting.hpre(str(new_val)[:50].strip(), language='language-new')}
""".strip()
        for action, (old_val, new_val), time in event.history[::-1][
            (page - 1) * 4 : (page - 1) * 4 + 4
        ]
    )
    event.text = text.strip()
    markup = generate_buttons(
        [
            [
                {"<": f"eh {event_id} {date:%d.%m.%Y} {page - 1}"}
                if page > 1 and event.history[::-1][: (page - 1) * 4]
                else {" ": "None"},
                {">": f"eh {event_id} {date:%d.%m.%Y} {page + 1}"}
                if event.history[::-1][(page - 1) * 4 + 4 :]
                else {" ": "None"},
            ],
            [
                {get_theme_emoji("back"): f"em {event_id}"},
                {"🔄": f"eh {event_id} {date:%d.%m.%Y}"},
            ],
        ]
    )
    generated.format(
        f"{get_translate('text.event_history')}:",
        event_formats["a"],
        markup,
    )
    return generated


def confirm_changes_message(message: Message) -> None | int:
    """
    Генерация сообщения для подтверждения изменений текста события.

    Возвращает 1 если есть ошибка.
    """
    event_id, message_id, html_text = re_edit_message.findall(message.html_text)[0]
    event_id, message_id = int(event_id), int(message_id)
    generated = EventMessage(event_id)
    event = generated.event

    if not event:
        return 1  # Этого события нет

    if message.quote:
        html_text = f"<blockquote>{message.quote.html_text}</blockquote>\n{html_text}"

    markdown_text = html_to_markdown(html_text).strip()

    if not markdown_text:
        try:
            before_event_delete_message(event_id).edit(request.chat_id, message_id)
            delete_message_action(message)
            return 1
        except ApiTelegramException:
            pass
        delete_message_action(message)
        return 1

    # Уменьшится ли длинна события
    new_event_len, len_old_event = len(markdown_text), len(event.text)
    tag_max_len_exceeded = new_event_len > 3800

    # Вычисляем сколько символов добавил пользователь. Если символов стало меньше, то 0.
    tag_len_less = len_old_event > new_event_len
    added_length = 0 if tag_len_less else new_event_len - len_old_event

    tag_limit_exceeded = request.entity.limit.is_exceeded_for_events(
        date=event.date, symbol_count=added_length
    )

    if tag_max_len_exceeded or tag_limit_exceeded:
        if tag_max_len_exceeded:
            translate = get_translate("errors.message_is_too_long")
        else:
            translate = get_translate("errors.exceeded_limit")

        markup = generate_buttons(
            [
                [
                    {
                        f"{event_id} {markdown_text[:20]}".ljust(60, "⠀"): {
                            "switch_inline_query_current_chat": (
                                f"event({event_id}, {message_id}).text\n"
                                f"{markdown_text}"
                            )
                        }
                    },
                    {get_theme_emoji("del"): "md"},
                ]
            ]
        )
        return TextMessage(translate, markup).reply(message)

    text_diff = highlight_text_difference(
        html.escape(event.text), html.escape(markdown_text)
    )
    # Находим пересечения выделений изменений и html экранирования
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
    event.text = f"<i>{text_diff}</i>"
    markup = generate_buttons(
        [
            [
                {get_theme_emoji("back"): f"em {event.event_id}"},
                {
                    "📝": {
                        "switch_inline_query_current_chat": (
                            f"event({event_id}, {message_id}).text\n{markdown_text}"
                        )
                    }
                },
                {"💾": f"eet {event.event_id} {event.date}"},
            ]
        ]
    )
    generated.format(
        f"{get_translate('text.are_you_sure_edit')}:",
        event_formats["a"],
        markup,
    )
    try:
        generated.edit(request.chat_id, message_id)
    except ApiTelegramException as e:
        if "message is not modified" not in f"{e}":
            logging.error(f'confirm_changes_message ApiTelegramException "{e}"')
            return 1


def recurring_events_message(
    date: str, id_list: list[int] = (), page: int | str = 0
) -> EventsMessage:
    """
    :param date: дата у сообщения
    :param id_list: Список из event_id
    :param page: Номер страницы
    """
    WHERE = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
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
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )

    backopenmarkup = generate_buttons(
        [[{get_theme_emoji("back"): f"pd {date}"}, {"↖️": "None"}]]
    )
    generated = EventsMessage(date, markup=backopenmarkup, page=page)

    if id_list:
        generated.get_page_events(WHERE, params, id_list)
    else:
        generated.get_pages_data(WHERE, params, f"pr {date}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 1, f"se o {string_id} pr {date}")
    generated.format(
        title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})"
        + f'\n📅 {get_translate("text.recurring_events")}',
        args=event_formats["dt"],
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def event_status_message(event: Event, path: str = "0") -> EventMessage:
    if path == "0":
        sl = event.status.split(",")
        sl.extend([""] * (5 - len(sl)))
        buttons_data = get_translate("buttons.status page.0")
        markup = generate_buttons(
            [
                *[
                    [
                        {
                            title.ljust(
                                60, "⠀"
                            ): f"esp {page} {event.date} {event.event_id}"
                        }
                        for (title, page) in row
                    ]
                    for row in buttons_data
                ],
                [
                    {
                        i
                        if i
                        else " " * n: f"esr {i} {event.date} {event.event_id}"
                        if i
                        else "None"
                    }
                    for n, i in enumerate(sl)
                ]
                if event.status != "⬜"
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
                            row.ljust(60, "⠀"): (
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

    generated = EventMessage(event.event_id)
    generated.format(
        get_translate("select.status_to_event"), event_formats["dt"], markup
    )
    return generated


def edit_event_date_message(event_id: int, date: datetime) -> EventMessage | None:
    generated = EventMessage(event_id)
    event = generated.event
    if not event:
        return None

    generated.format(
        f"{get_translate('select.new_date')}:",
        event_formats["dt"],
        create_monthly_calendar_keyboard(
            (date.year, date.month), "eds", "em", f"{event_id}"
        ),
    )
    return generated


def edit_events_date_message(
    id_list: list[int], date: datetime | None = None
) -> EventsMessage:
    if date is None:
        date = request.entity.now_time()

    WHERE = """
user_id IS ?
AND group_id IS ?
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    generated = EventsMessage()
    generated.get_page_events(WHERE, params, id_list)
    generated.format(
        title=f"<b>{get_translate('select.what_do_with_events')}:</b>",
        args=event_formats["r"],
        if_empty=get_translate("errors.message_empty"),
    )
    generated.markup = create_monthly_calendar_keyboard(
        (date.year, date.month), "esds", "esm", encode_id(id_list)
    )
    return generated


def before_event_delete_message(event_id: int) -> EventMessage | None:
    """
    Генерирует сообщение с кнопками удаления,
    удаления в корзину (для премиум) и изменения даты.
    """
    generated = EventMessage(event_id)
    event = generated.event
    if not event:
        return None

    delete_permanently = get_translate("text.delete_permanently")
    trash_bin = get_translate("text.trash_bin")
    markup = generate_buttons(
        [
            [
                {f"❌ {delete_permanently}": f"ed {event.event_id} {event.date}"},
                {f"🗑 {trash_bin}": f"edb {event.event_id} {event.date}"}
                if request.entity.is_premium
                else {},
            ],
            [{get_theme_emoji("back"): f"em {event_id}"}],
        ]
    )
    generated.format(
        f"{get_translate('select.what_do_with_event')}:", event_formats["dt"], markup
    )
    return generated


def before_events_delete_message(id_list: list[int]) -> EventsMessage:
    """
    Генерирует сообщение с кнопками удаления,
    удаления в корзину (для премиум) и изменения даты.
    """
    WHERE = """
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    generated = EventsMessage()
    generated.get_page_events(WHERE, params, id_list)

    is_wastebasket_available = request.entity.is_premium
    string_id = encode_id(id_list)
    date = generated.event_list[0].date if generated.event_list else ""
    delete_permanently = get_translate("text.delete_permanently")
    trash_bin = get_translate("text.trash_bin")
    markup = [
        [
            {f"❌ {delete_permanently}": f"esd {string_id} {date}"},
            {f"🗑 {trash_bin}": f"esdb {string_id} {date}"}
            if is_wastebasket_available
            else {},
        ],
        [{get_theme_emoji("back"): f"esm {string_id}"}],
    ]
    generated.format(
        title=f"<b>{get_translate('select.what_do_with_events')}:</b>",
        args=event_formats["r"],
        if_empty=get_translate("errors.message_empty"),
    )
    generated.markup = generate_buttons(markup)
    return generated


def search_message(
    query: str, id_list: list[int] = (), page: int | str = 0
) -> EventsMessage:
    """
    :param query: поисковый запрос
    :param id_list: Список из event_id
    :param page: Номер страницы
    TODO шаблоны для поиска
    """
    query = query.replace("\n", " ").strip()
    translate_search = get_translate("messages.search")

    if query.isspace():
        generated = EventsMessage(markup=delmarkup())
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
    generated = EventsMessage(markup=markup, page=page)

    splitquery = " OR ".join(
        """
date LIKE '%' || ? || '%'
OR text LIKE '%' || ? || '%'
OR status LIKE '%' || ? || '%'
OR event_id LIKE '%' || ? || '%'
"""
        for _ in query.split()
    )
    WHERE = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
AND ({splitquery})
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
        *[y for x in query.split() for y in (x, x, x, x)],
    )

    if id_list:
        generated.get_page_events(WHERE, params, id_list)
    else:
        generated.get_pages_data(WHERE, params, "ps")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 2, f"se os {string_id} us")
    edit_button_data(generated.markup, 0, 3, f"ses s {string_id} us")
    generated.format(
        title=f"🔍 {translate_search} <u>{html.escape(query)}</u>:",
        args=event_formats["r"],
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def week_event_list_message(
    id_list: list[int] = (), page: int | str = 0
) -> EventsMessage:
    """
    :param id_list: Список из event_id
    :param page: Номер страницы
    """
    tz = f"'{request.entity.settings.timezone:+} hours'"
    WHERE = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
AND (
    (
        {sqlite_format_date('date')}
        BETWEEN DATE('now', {tz})
            AND DATE('now', '+7 day', {tz})
    )
    OR
    ( -- Каждый год
        (
            status LIKE '%🎉%' OR status LIKE '%🎊%' OR status LIKE '%📆%'
        )
        AND
        (
            strftime('%m-%d', {sqlite_format_date('date')})
            BETWEEN strftime('%m-%d', 'now', {tz})
                AND strftime('%m-%d', 'now', '+7 day', {tz})
        )
    )
    OR
    ( -- Каждый месяц
        status LIKE '%📅%'
        AND SUBSTR(date, 1, 2) 
        BETWEEN strftime('%d', 'now', {tz})
            AND strftime('%d', 'now', '+7 day', {tz})
    )
    OR status LIKE '%🗞%' -- Каждую неделю
    OR status LIKE '%📬%' -- Каждый день
)
    """
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )

    markup = generate_buttons(
        [[{get_theme_emoji("back"): "mnm"}, {"🔄": "mnw"}, {"↖️": "None"}]]
    )
    generated = EventsMessage(markup=markup, page=page)
    if id_list:
        generated.get_page_events(WHERE, params, id_list)
    else:
        generated.get_pages_data(WHERE, params, "pw")
    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 2, f"se o {string_id} mnw")
    generated.format(
        title=f"7️⃣ {get_translate('text.week_events')}",
        args=event_formats["r"],
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def trash_can_message(id_list: list[int] = (), page: int | str = 0) -> EventsMessage:
    """
    :param id_list: Список из event_id
    :param page: Номер страницы
    """
    WHERE = """
user_id IS ?
AND group_id IS ?
AND removal_time IS NOT NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    # Удаляем события старше 30 дней
    db.execute(
        """
-- Удаляем события старше 30 дней
DELETE FROM events
      WHERE removal_time IS NOT NULL AND 
            (julianday('now') - julianday(removal_time) > 30);
""",
        commit=True,
    )

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
    generated = EventsMessage(markup=markup, page=page)

    if id_list:
        generated.get_page_events(WHERE, params, id_list)
    else:
        generated.get_pages_data(WHERE, params, "pb")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 0, f"se b {string_id} mnb")
    edit_button_data(generated.markup, 0, 1, f"ses b {string_id} mnb")

    generated.format(
        title=f"🗑 {basket_translate} 🗑",
        args=event_formats["b"],
        if_empty=message_empty_translate,
    )
    return generated


def notification_message(
    n_date: datetime | None = None,
    id_list: list[int] = (),
    page: int | str = 0,
    from_command: bool = False,
) -> EventsMessage | None:
    if n_date is None:
        n_date = request.entity.now_time()

    dates = [n_date + timedelta(days=days) for days in (0, 1, 2, 3, 7)]
    weekdays = ["0" if (w := date.weekday()) == 6 else f"{w + 1}" for date in dates[:2]]
    WHERE = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
AND status NOT LIKE '%🔕%'
AND (
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
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )

    markup = generate_buttons(
        [
            [
                {get_theme_emoji("back"): "mnn" if from_command else "mnm"},
                {"🔄": f"mnn {n_date:%d.%m.%Y}"},
                {"↖️": "None"},
            ]
        ]
    )

    generated = EventsMessage(markup=markup, page=page)
    if id_list:
        generated.get_page_events(WHERE, params, id_list)
    else:
        generated.get_pages_data(WHERE, params, f"pn {n_date:%d.%m.%Y}")
        string_id = encode_id([event.event_id for event in generated.event_list])
        edit_button_data(
            generated.markup, 0, -1, f"se o {string_id} mnn {n_date:%d.%m.%Y}"
        )

    if generated.event_list or from_command:
        reminder_translate = get_translate("messages.reminder")
        generated.format(
            title=f"🔔 {reminder_translate} <b>{n_date:%d.%m.%Y}</b>",
            args=event_formats["r"],
            if_empty=get_translate("errors.message_empty"),
        )
        return generated
    return None


def send_notifications_messages() -> None:
    n_date = datetime.utcnow()
    with db.connection(), db.cursor():
        chat_ids, notification_types = db.execute(
            """
-- id людей через запятую, которым нужно сейчас прислать уведомление
SELECT GROUP_CONCAT(
    COALESCE(
        (
            SELECT chat_id
              FROM users
             WHERE users.user_id = tg_settings.user_id
        ),
        (
            SELECT chat_id
              FROM groups
             WHERE groups.group_id = tg_settings.group_id
        )
    ),
    ','
),
       GROUP_CONCAT(notifications, ',')
  FROM tg_settings
 WHERE notifications != 0
       AND (
           (
               CAST(SUBSTR(notifications_time, 1, 2) AS INT)
               - timezone + 24
           ) % 24
       ) = :hour
       AND CAST(SUBSTR(notifications_time, 4, 2) AS INT) = :minute;
""",
            params={
                "hour": n_date.hour,
                "minute": n_date.minute,
            },
        )[0]
        chat_id_list = zip(
            [int(x) for x in chat_ids.split(",")] if chat_ids else (),
            [int(x) for x in notification_types.split(",")]
            if notification_types
            else (),
        )  # [('id1,id2,id3',)] -> [id1, id2, id3]

    for chat_id, n_type in chat_id_list:
        try:
            request.entity = TelegramAccount(chat_id)
        except UserNotFound:
            continue

        if request.entity.user.user_status == -1:
            continue

        match n_type:
            case 2:
                generated = week_event_list_message()
            case _:
                generated = notification_message(from_command=True)

        if generated and generated.event_list:
            try:
                generated.send(request.entity.request_chat_id)
                status = "Ok"
            except ApiTelegramException:
                status = "Error"

            logging.info(
                f"notifications -> {request.entity.request_chat_id} -> {status}"
            )


def monthly_calendar_message(
    YY_MM: list | tuple[int, int] | None = None,
    command: str | None = None,
    back: str | None = None,
    custom_text: str | None = None,
) -> TextMessage:
    text = custom_text if custom_text else get_translate("select.date")
    markup = create_monthly_calendar_keyboard(YY_MM, command, back)
    return TextMessage(text, markup)


def limits_message(date: datetime | str | None = None) -> TextMessage:
    if date is None or date == "now":
        date = request.entity.now_time()

    if not is_valid_year(date.year):
        return TextMessage(get_translate("errors.error"))

    return TextMessage(
        get_limit_link(f"{date:%d.%m.%Y}"),
        generate_buttons([[{get_theme_emoji("back"): "lm"}]]),
    )


def group_message(group_id: str, message_id: int = None) -> TextMessage | None:
    try:
        if request.is_member:
            group = request.entity.group
        else:
            group = request.entity.get_group(group_id)
    except GroupNotFound:
        return None

    group_template = get_translate("messages.group")
    chat_id = f"chat_id: `<code>{group.chat_id}</code>`" if group.chat_id else ""
    text = group_template.format(group.group_id, html.escape(group.name)) + chat_id

    if request.is_user:
        startgroup_data = f"group-{group.owner_id}-{group.group_id}"
        startgroup_url = "https://t.me/{}?startgroup={}".format(
            bot.user.username, startgroup_data
        )

        leave_group = get_translate("text.leave_group")
        change_group_name = get_translate("text.change_group_name")
        delete_group = get_translate("text.delete_group")
        remove_bot_from_group = get_translate("text.remove_bot_from_group")
        markup = generate_buttons(
            [
                [{leave_group: f"grlv {group.group_id}"}]
                if not group.member_status == 2
                else [],
                [
                    {
                        change_group_name: {
                            "switch_inline_query_current_chat": (
                                f"group({group.group_id}, {message_id}).name\n"
                                f"{html.unescape(group.name)}"
                            )
                        }
                    }
                    if message_id
                    else {change_group_name: "None"},
                ]
                if group.member_status > 0
                else [],
                [
                    {delete_group: f"grd {group.group_id}"},
                    {remove_bot_from_group: f"grrgr {group.group_id}"}
                    if group.chat_id
                    else {
                        get_translate("text.add_bot_to_group"): {"url": startgroup_url}
                    },
                ]
                if group.member_status > 0
                else [],
                [{get_theme_emoji("back"): "mngrs"}],
            ]
        )
    else:
        text += f"\nowner_id: `<code>{group.owner_id}</code>`"
        markup = generate_buttons([[{get_theme_emoji("back"): "mnm"}]])

    return TextMessage(text, markup)


def groups_message(
    mode: Literal["al", "md", "ad"] = "al", page: int = 1
) -> TextMessage:
    match mode:
        case "al":
            raw_groups = request.entity.get_my_groups()
        case "md":
            raw_groups = request.entity.get_groups_where_i_moderator()
        case "ad":
            raw_groups = request.entity.get_groups_where_i_admin()
        case _:
            raise ValueError

    groups_chunk = list(chunks(raw_groups, 6))
    groups = groups_chunk[page - 1] if len(groups_chunk) > 0 else []
    prev_pages = len(groups_chunk[: page - 1])
    after_pages = len(groups_chunk[page:])
    create_group = get_translate("text.create_group")
    groups_message_template = get_translate("messages.groups")

    if groups:
        string_groups = "\n\n".join(
            f"""
{n + (6 * page - 6) + 1}) name: `<code>{html.escape(group.name)}</code>`
     id: `<code>{group.group_id}</code>`
     {f'chat_id: `<code>{group.chat_id}</code>`' if group.chat_id else ''}
""".strip()
            for n, group in enumerate(groups)
        )
        user_group_limits = group_limits[request.entity.user.user_status][
            "max_groups_participate" if mode == "al" else "max_groups_creator"
        ]
        text = groups_message_template.format(
            f"{len(raw_groups)}/{user_group_limits}", string_groups
        )
        markup = [
            [
                {("🔸" if mode == "al" else "") + "All": "mngrs al"},
                {("🔸" if mode == "md" else "") + "Moderator": "mngrs md"},
                {("🔸" if mode == "ad" else "") + "Admin": "mngrs ad"},
            ],
            *[[{f"{group.name}": f"mngr {group.group_id}"}] for group in groups],
            [
                {get_theme_emoji("back"): "mnm"},
                *(
                    [
                        {"<": f"mngrs {mode} {page - 1}"}
                        if prev_pages
                        else {" ": "None"},
                        {">": f"mngrs {mode} {page + 1}"}
                        if after_pages
                        else {" ": "None"},
                    ]
                    if len(groups_chunk) != 1
                    else []
                ),
                {f"👥 {create_group}": "grcr"},
            ],
        ]
    else:
        text = groups_message_template.format(0, "")
        markup = [
            [{f"👥 {create_group}": "grcr"}],
            [{get_theme_emoji("back"): "mnm"}],
        ]
    return TextMessage(text, generate_buttons(markup))


def account_message(message_id: int) -> TextMessage:
    text = get_translate("messages.account").format(
        request.entity.user_id,
        request.entity.request_chat_id,
        request.entity.user.username,
        parse_utc_datetime(request.entity.user.reg_date),
    )
    markup = generate_buttons(
        [
            [{f"{get_translate('text.get_premium')}🤩": "get_premium"}]
            if request.entity.user.user_status == 0
            else [],
            [
                {
                    f"{get_translate('text.edit_username')}👤": {
                        "switch_inline_query_current_chat": (
                            f"user({message_id}).name\n"
                            f"{html.unescape(request.entity.user.username)}"
                        )
                    }
                }
            ],
            [
                {
                    f"{get_translate('text.edit_password')}🤫🔑": {
                        "switch_inline_query_current_chat": (
                            "user().password\nold password: \nnew password: "
                        )
                    }
                }
            ],
            [
                {get_theme_emoji("back"): "mnm"},
                {"📊": "lm"},
                {f"{get_translate('text.logout')}🚪👈": "logout"},
            ],
        ]
    )
    return TextMessage(text, markup)


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

    try:
        events_list = request.entity.get_events(id_list, is_in_wastebasket)
    except EventNotFound:
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
    id_list: list[int], back_data: str, in_bin: bool = False, is_in_search: bool = False
) -> TextMessage | None:
    # Если событий нет
    if len(id_list) == 0:
        return None

    try:
        events_list = request.entity.get_events(id_list, in_bin)
    except EventNotFound:
        return None

    # Если событие одно
    if len(events_list) == 1:
        return events_message([events_list[0].event_id], in_bin)

    # Если событий несколько
    markup = []
    for n, event in enumerate(events_list):
        button_title = f"{event.event_id}.{event.status} {event.text}"
        button_title = button_title.ljust(60, "⠀")[:60]
        if in_bin or is_in_search:
            button_title = f"{event.date}.{button_title}"[:60]

        if in_bin:
            button_data = f"sbon {n} 0 {event.event_id}"
        else:
            button_data = f"son {n} 0 {event.event_id}"

        markup.append([{button_title: button_data}])

    markup.append(
        [
            {get_theme_emoji("back"): back_data},
            {"☑️": "sbal" if in_bin else "sal"},
            {"↗️": "bsm _" if in_bin else "esm _"},
        ]
    )
    generated = TextMessage(get_translate("select.events"), generate_buttons(markup))
    return generated
