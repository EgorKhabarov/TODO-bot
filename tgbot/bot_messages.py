import re
import json
import html
import arrow
from arrow import Arrow
from typing import Literal

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

# noinspection PyPackageRequirements
from telebot import formatting

# noinspection PyPackageRequirements
from telebot.types import InlineKeyboardButton, Message

import config
from tgbot.bot import bot
from tgbot.request import request
from tgbot.limits import get_limit_link
from tgbot.time_utils import parse_utc_datetime
from tgbot.bot_actions import delete_message_action
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.types import TelegramAccount, TelegramSettings
from tgbot.message_generator import (
    TextMessage,
    EventMessage,
    EventsMessage,
    event_formats,
)
from tgbot.buttons_utils import (
    delmarkup,
    encode_id,
    create_monthly_calendar_keyboard,
    create_select_status_keyboard,
    create_time_hour_keyboard,
    create_time_minute_keyboard,
)
from tgbot.utils import (
    Cycle,
    re_edit_message,
    html_to_markdown,
    extract_search_query,
    extract_search_filters,
    highlight_text_difference,
    generate_search_sql_condition,
)
from todoapi.logger import logger
from todoapi.types import db, group_limits
from todoapi.utils import is_valid_year, chunks
from todoapi.exceptions import EventNotFound, GroupNotFound, UserNotFound
from telegram_utils.buttons_generator import generate_buttons, edit_button_data


def start_message() -> TextMessage:
    text = get_translate("messages.start")
    markup = generate_buttons([[{"/menu": "mnm"}], [{"/calendar": "mnc ('now',)"}]])
    return TextMessage(text, markup)


def menu_message() -> TextMessage:
    """
    Generates a menu message
    """
    (
        translate_menu,
        translate_help,
        translate_calendar,
        translate_account,
        translate_groups,
        translate_seven_days,
        translate_notifications,
        translate_search,
        translate_settings,
        translate_wastebasket,
        translate_group,
    ) = get_translate("messages.menu")

    text = translate_menu
    markup = [
        [
            {f"📚 {translate_help}": "mnh"},
            {f"📆 {translate_calendar}": "mnc ('now',)"},
        ],
        (
            [
                {f"👤 {translate_account}": "mna"},
                {f"👥 {translate_groups}": "mngrs"},
            ]
            if request.is_user
            else []
        ),
        [
            {f"📆 {translate_seven_days}": "pw"},
            {f"🔔 {translate_notifications}": "mnn"},
        ],
        [
            {f"⚙️ {translate_settings}": "mns"},
            (
                {f"🗑 {translate_wastebasket}": "mnb"}
                if (request.is_user and request.entity.is_premium) or request.is_member
                else {}
            ),
        ],
        [
            {f"🔍 {translate_search}": "mnsr"},
            {f"👥 {translate_group}": "mngr self"} if request.is_member else {},
        ],
    ]
    return TextMessage(text, generate_buttons(markup))


def settings_message(
    lang: str = ...,
    sub_urls: bool = ...,
    city: str = ...,
    timezone: int = ...,
    notifications: int = ...,
    notifications_time: str = ...,
    theme: int = ...,
) -> TextMessage:
    """
    Sets settings for user chat_id
    """

    def format_call_data(
        lang_: str | None = None,
        sub_urls_: bool | None = None,
        timezone_: int | None = None,
        notifications_: int | None = None,
        notifications_time_: str | None = None,
        theme_: int | None = None,
        prefix: str = "stu",
    ) -> str:
        t = (
            settings.lang if lang_ is None else lang_,
            int(settings.sub_urls if sub_urls_ is None else sub_urls_),
            settings.timezone if timezone_ is None else timezone_,
            int(settings.notifications if notifications_ is None else notifications_),
            (
                settings.notifications_time
                if notifications_time_ is None
                else notifications_time_
            ),
            settings.theme if theme_ is None else theme_,
        )
        return f"{prefix} {t}"

    entity_settings = request.entity.settings
    settings = TelegramSettings(
        lang=entity_settings.lang if lang is ... else lang,
        sub_urls=entity_settings.sub_urls if sub_urls is ... else sub_urls,
        city=entity_settings.city if city is ... else city,
        timezone=entity_settings.timezone if timezone is ... else timezone,
        notifications=(
            entity_settings.notifications if notifications is ... else notifications
        ),
        notifications_time=(
            entity_settings.notifications_time
            if notifications_time is ...
            else notifications_time
        ),
        theme=entity_settings.theme if theme is ... else theme,
    )

    languages = ("en", "ru")
    notifications_types = (0, 1, 2)
    notifications_emoji = ("🔕", "🔔", "📆")
    theme_ids = (0, 1)
    theme_emojis = ("⬜", "⬛️")
    sub_urls = (0, 1)

    old_sub_urls = get_translate(f"text.bool.{'yes' if settings.sub_urls else 'no'}")
    old_notification_type = notifications_emoji[settings.notifications]
    old_theme_emoji = theme_emojis[settings.theme]

    new_lang = next(Cycle(languages, languages.index(settings.lang)))
    new_sub_urls = next(Cycle(sub_urls, int(bool(settings.sub_urls))))
    new_sub_urls_string = get_translate(
        f"text.bool.{'yes' if not settings.sub_urls else 'no'}"
    )
    new_notifications_type = next(Cycle(notifications_types, settings.notifications))
    new_notifications_emoji = next(Cycle(notifications_emoji, settings.notifications))
    new_theme_id = next(Cycle(theme_ids, settings.theme))
    new_theme_emoji = next(Cycle(theme_emojis, settings.theme))

    if -2 < int(settings.timezone) < 5:
        str_timezone = f"{settings.timezone} 🌍"
    elif 4 < int(settings.timezone) < 12:
        str_timezone = f"{settings.timezone} 🌏"
    else:
        str_timezone = f"{settings.timezone} 🌎"

    text = get_translate("messages.settings").format(
        lang=f"{settings.lang} {get_translate('text.lang_flag')}",
        sub_urls=old_sub_urls,
        city=html.escape(settings.city),
        timezone=str_timezone,
        timezone_question=f"{request.entity.now_time():%Y.%m.%d  <u>%H:%M</u>}",
        notification_type=old_notification_type,
        notification_time=settings.notifications_time if settings.notifications else "",
        theme=old_theme_emoji,
    )

    blank_timezone = {" ": "None"}
    timezone_row = [
        (
            {"-3": format_call_data(timezone_=settings.timezone - 3)}
            if settings.timezone > -10
            else blank_timezone
        ),
        (
            {"-1": format_call_data(timezone_=settings.timezone - 1)}
            if settings.timezone > -12
            else blank_timezone
        ),
        {str_timezone: format_call_data(timezone_=0)},
        (
            {"+1": format_call_data(timezone_=settings.timezone + 1)}
            if settings.timezone < 12
            else blank_timezone
        ),
        (
            {"+3": format_call_data(timezone_=settings.timezone + 3)}
            if settings.timezone < 10
            else blank_timezone
        ),
    ]

    if settings.notifications:
        n_hours, n_minutes = [int(i) for i in settings.notifications_time.split(":")]
        now = arrow.get(2000, 6, 5, n_hours, n_minutes)
        notifications_time_row = [
            {
                "-1h": format_call_data(
                    notifications_time_=f"{now.shift(hours=1):HH:mm}"
                )
            },
            {
                "-10m": format_call_data(
                    notifications_time_=f"{now.shift(minutes=10):HH:mm}"
                )
            },
            {
                settings.notifications_time: format_call_data(
                    notifications_time_="08:00"
                )
            },
            {
                "+10m": format_call_data(
                    notifications_time_=f"{now.shift(minutes=10):HH:mm}"
                )
            },
            {
                "+1h": format_call_data(
                    notifications_time_=f"{now.shift(hours=1):HH:mm}"
                )
            },
        ]
    else:
        notifications_time_row = []

    markup = generate_buttons(
        [
            [
                {f"🗣 {new_lang}": format_call_data(lang_=new_lang)},
                {f"🔗 {new_sub_urls_string}": format_call_data(sub_urls_=new_sub_urls)},
                {
                    new_notifications_emoji: format_call_data(
                        notifications_=new_notifications_type
                    )
                },
                {new_theme_emoji: format_call_data(theme_=new_theme_id)},
            ],
            timezone_row,
            notifications_time_row,
            [{get_translate("text.restore_to_default"): "std"}],
            [{get_theme_emoji("back"): "mnm"}, {"💾": format_call_data(prefix="sts")}],
        ]
    )
    return TextMessage(text, markup)


def help_message(path: str = "page 1") -> TextMessage:
    """
    Help message
    """
    translate = get_translate(f"messages.help.{path}")
    title = get_translate("messages.help.title")

    if path.startswith("page"):
        text, keyboard = translate
        # Changing the last button
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


def daily_message(date: Arrow, id_list: list[int] = (), page: int = 0) -> EventsMessage:
    """
    Generates a message for one day

    :param date: Message date
    :param id_list: List of event_id
    :param page: Page number
    """
    sql_where = """
user_id IS ?
AND group_id IS ?
AND DATE(datetime, ? || ' HOURS') = ?
AND removal_time IS NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
        request.entity.settings.timezone,
        f"{date:YYYY-MM-DD}",
    )

    y = date.shift(days=-1)
    t = date.shift(days=+1)
    yesterday = f"dl {y:YYYY-MM-DD}" if is_valid_year(y.year) else "None"
    tomorrow = f"dl {t:YYYY-MM-DD}" if is_valid_year(t.year) else "None"

    markup = generate_buttons(
        [
            [
                {get_theme_emoji("add"): f"ea {date:YYYY-MM-DD}"},
                {"🔼": "None"},
                {"↕️": "None"},
                {"Menu": "mnm"},
            ],
            [
                {get_theme_emoji("back"): f"mnc (({date:YYYY},{int(date.month)}),)"},
                {"<": yesterday},
                {">": tomorrow},
                {"🔄": f"dl {date:YYYY-MM-DD}"},
            ],
        ]
    )
    generated = EventsMessage(date, markup=markup, page=page)

    if id_list:
        generated.get_page_events(sql_where, params, id_list)
    else:
        generated.get_pages_data(sql_where, params, f"pd {date:YYYY-MM-DD}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 1, f"se _ {string_id} pd {date:YYYY-MM-DD}")
    edit_button_data(generated.markup, 0, 2, f"ses _ {string_id} pd {date:YYYY-MM-DD}")

    generated.format(
        title="{date} <u><i>{strdate} {weekday}</i></u> ({reldate})",
        args=event_formats["dl"],
        if_empty=get_translate("errors.nodata"),
    )

    # Add a button for days that have holidays
    daylist = [
        x[0]
        for x in db.execute(
            f"""
-- If found, then add a repeating events button
SELECT DISTINCT DATE(datetime, :timezone || ' HOURS')
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND DATE(datetime, :timezone || ' HOURS') != :datetime
       AND (
    ( -- Every year
        repetition = 'repeat every year'
        AND DATE(datetime, :timezone || ' HOURS') LIKE :y_date
    )
    OR
    ( -- Every month
        repetition = 'repeat every month'
        AND DATE(datetime, :timezone || ' HOURS') LIKE :m_date
    )
    OR
    ( -- Every week
        repetition = 'repeat every week'
        AND STRFTIME('%w', datetime, :timezone || ' HOURS') = STRFTIME('%w', :datetime, :timezone || ' HOURS')
    )
    OR
    ( -- Every weekdays
        repetition = 'repeat every weekdays'
        AND STRFTIME('%w', :datetime, :timezone || ' HOURS') BETWEEN '1' AND '5'
        -- AND STRFTIME('%w', datetime, :timezone || ' HOURS') BETWEEN '1' AND '5'
    )
    OR
    repetition = 'repeat every day' -- Every day
)
LIMIT 1;
""",
            params={
                "timezone": request.entity.settings.timezone,
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
                "datetime": f"{date:YYYY-MM-DD}",
                "y_date": f"____-{date:MM-DD}",
                "m_date": f"____-__-{date:DD}",
            },
        )
    ]

    if daylist:
        generated.markup.row(
            InlineKeyboardButton("📅", callback_data=f"pr {date:YYYY-MM-DD}")
        )

    return generated


def event_message(
    event_id: int, in_wastebasket: bool = False, message_id: int = None
) -> EventMessage | None:
    """
    Message to interact with one event
    """
    generated = EventMessage(event_id, in_wastebasket)
    event = generated.event
    if not event:
        return None

    if not in_wastebasket:
        markup = [
            [
                (
                    {
                        "📝": {
                            "switch_inline_query_current_chat": (
                                f"event({event_id}, {message_id}).text\n"
                                f"{html.unescape(event.text)}"
                            )
                        }
                    }
                    if message_id
                    else {"📝": "None"}
                ),
                {
                    "🏷": f"es {event.string_statuses} folders {event_id} {event.datetime:YYYY-MM-DD}"
                },
                {"🗑": f"ebd {event_id} {event.date}"},
            ],
            [
                {"📋": f"esh {event_id} {event.date}"},
                {"🔁": f"erm {event_id} {event.date}"},  # {"*️⃣": "None"},
                {"📅": f"esdt {event_id} {event.date}"},
            ],
            [
                {"ℹ️": f"eab {event_id} {event.date}"},
                {"🗄": f"eh {event_id} {event.date}"},
                {"🕛": f"eth {event_id} {event.date}"},  # {"🖼": "None"},
            ],
            [
                {get_theme_emoji("back"): f"dl {event.date}"},
                {" ": "None"},  # 🔔
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
    Message to interact with events
    """
    generated = EventsMessage()
    sql_where = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS {'NOT' if is_in_wastebasket else ''} NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    generated.get_page_events(sql_where, params, id_list)
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

    (
        title,
        text_event_id,
        text_length,
        time_added,
        time_last_changes,
        text_reference_event_id,
    ) = get_translate("text.event_about_info")

    if event.reference_event_id:
        text_reference_event_id = (
            f"{event.reference_event_id} - {text_reference_event_id}"
        )
    else:
        text_reference_event_id = ""

    text = f"""
{event.event_id} - {text_event_id}
{len(event.text)} - {text_length}
{parse_utc_datetime(event.adding_time)} - {time_added}
{parse_utc_datetime(event.recent_changes_time)} - {time_last_changes}
{text_reference_event_id}
""".strip()
    event.text = formatting.hpre(text, language="language-event-metadata")
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


def event_history_message(
    event_id: int, date: Arrow, page: int = 1
) -> EventMessage | None:
    generated = EventMessage(event_id)
    event = generated.event
    if not event:
        return None

    (
        translate_event_history,
        translate_no_event_history,
        history_action_dict,
    ) = get_translate("text.event_history")

    if event.history:

        def text_limiter(text: str, length: int = 50) -> str:
            if len(text) > length:
                text = text[:length] + chr(8230)
            return text

        def prepare_value(action, val):
            if action == "statuses":
                return ",".join(map(str, val))

            if action == "datetime":
                a = arrow.get(val)
                result = a.shift(
                    hours=request.entity.settings.timezone
                ).replace(year=a.year, month=a.month, day=a.day)
                return f"{result:YYYY-MM-DD HH:mm:ss}"

            return val

        event.text = (
            "\n"
            + "\n\n".join(
                f"""
[<u>{parse_utc_datetime(time)}] <b>{history_action_dict.get(action, "?")}</b></u>
{formatting.hpre(text_limiter(f"{prepare_value(action, old_val)}".strip()), language="language-old")}
{formatting.hpre(text_limiter(f"{prepare_value(action, new_val)}".strip()), language="language-new")}
""".strip()
                for action, (old_val, new_val), time in (
                    event.history[::-1][(page - 1) * 4 : (page - 1) * 4 + 4]
                )
            ).strip()
        )
    else:
        event.text = translate_no_event_history

    markup = generate_buttons(
        [
            (
                [
                    (
                        {"<": f"eh {event_id} {date:YYYY-MM-DD} {page - 1}"}
                        if page > 1 and event.history[::-1][: (page - 1) * 4]
                        else {" ": "None"}
                    ),
                    (
                        {">": f"eh {event_id} {date:YYYY-MM-DD} {page + 1}"}
                        if event.history[::-1][(page - 1) * 4 + 4 :]
                        else {" ": "None"}
                    ),
                ]
                if event.history
                else []
            ),
            [
                {get_theme_emoji("back"): f"em {event_id}"},
                {"🧹": f"ehc {event_id} {date:YYYY-MM-DD}"},
                {"🔄": f"eh {event_id} {date:YYYY-MM-DD}"},
            ],
        ]
    )
    generated.format(
        f"{translate_event_history}:",
        event_formats["a"],
        markup,
    )
    return generated


def confirm_changes_message(message: Message) -> None | int:
    """
    Generate a message to confirm changes to the event text.

    Returns 1 if there is an error.
    """
    event_id, message_id, html_text = re_edit_message.findall(message.html_text)[0]
    event_id, message_id = int(event_id), int(message_id)
    generated = EventMessage(event_id)
    event = generated.event

    if not event:
        return 1  # This event does not exist

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

    # is the event length decrease
    new_event_len, len_old_event = len(markdown_text), len(event.text)
    tag_max_len_exceeded = new_event_len > 3800

    # Calculate how many characters the user added.
    # If there are fewer characters, then 0.
    tag_len_less = len_old_event > new_event_len
    added_length = 0 if tag_len_less else new_event_len - len_old_event

    tag_limit_exceeded = request.entity.limit.is_exceeded_for_events(
        date=event.datetime, symbol_count=added_length
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

        TextMessage(translate, markup).send(reply_to_message_id=message_id)
        return

    text_diff = highlight_text_difference(
        html.escape(event.text), html.escape(markdown_text)
    )
    # Finding the intersections of change highlighting and html escaping
    # In case there is html escaped text in the database
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
            logger.error(f'confirm_changes_message ApiTelegramException "{e}"')
            return 1


def recurring_events_message(
    date: Arrow, id_list: list[int] = (), page: int = 0
) -> EventsMessage:
    """
    :param date: message date
    :param id_list: List of event_id
    :param page: Page number
    """
    sql_where = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
AND (
    ( -- Every year
        repetition = 'repeat every year'
        AND DATE(datetime) LIKE ?
    )
    OR
    ( -- Every month
        repetition = 'repeat every month'
        AND DATE(datetime) LIKE ?
    )
    OR
    ( -- Every week
        repetition = 'repeat every week'
        AND STRFTIME('%w', datetime) = STRFTIME('%w', ?)
    )
    OR
    ( -- Every weekdays
        repetition = 'repeat every weekdays'
        AND STRFTIME('%w', ?) BETWEEN '1' AND '5'
        -- AND STRFTIME('%w', datetime) BETWEEN '1' AND '5'
    )
    OR
    ( -- Every day
        repetition = 'repeat every day'
    )
)
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
        f"____-{date:MM-DD}",
        f"____-__-{date:DD}",
        f"{date:YYYY-MM-DD}",
        f"{date:YYYY-MM-DD}",
    )

    back_open_markup = generate_buttons(
        [[{get_theme_emoji("back"): f"pd {date:YYYY-MM-DD}"}, {"↖️": "None"}]]
    )
    generated = EventsMessage(date, markup=back_open_markup, page=page)

    if id_list:
        generated.get_page_events(sql_where, params, id_list)
    else:
        generated.get_pages_data(sql_where, params, f"pr {date:YYYY-MM-DD}")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 1, f"se o {string_id} pr {date:YYYY-MM-DD}")
    generated.format(
        title="{date} <u><i>{strdate} {weekday}</i></u> ({reldate})"
        + f'\n📅 {get_translate("text.recurring_events")}',
        args=event_formats["dt"],
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def event_status_message(
    statuses: str, folder_path: str, event_id: int, date: Arrow
) -> EventMessage:
    statuses_list = statuses.split(",")
    markup = create_select_status_keyboard(
        prefix="es",
        status_list=statuses_list,
        folder_path=folder_path,
        save="ess",
        back="em",
        arguments=f"{event_id} {date:YYYY-MM-DD}",
    )
    generated = EventMessage(event_id)
    generated.event._status = json.dumps(statuses_list[-5:], ensure_ascii=False)
    generated.format(
        get_translate("select.status_to_event"), event_formats["dt"], markup
    )
    return generated


def event_repetition_menu_message(event_id: int, date: Arrow) -> TextMessage | None:
    generated = EventMessage(event_id)
    event = generated.event
    if not event:
        return None

    (
        repeat_never,
        repeat_every_day,
        repeat_every_week,
        repeat_every_month,
        repeat_every_year,
        repeat_every_weekdays,
        # other,
    ) = get_translate("text.repetition_menu")

    markup = [
        [{repeat_never: f"ers {event_id} {date.date()} nv"}],
        [{repeat_every_day: f"ers {event_id} {date.date()} ed"}],
        [{repeat_every_week: f"ers {event_id} {date.date()} ewk"}],
        [{repeat_every_month: f"ers {event_id} {date.date()} em"}],
        [{repeat_every_year: f"ers {event_id} {date.date()} ey"}],
        [{repeat_every_weekdays: f"ers {event_id} {date.date()} ewd"}],
        # [{other: "None"}],
        [{get_theme_emoji("back"): f"em {event_id}"}],
    ]

    generated.format(
        f"Repetition menu",
        event_formats["a"],
        generate_buttons(markup),
    )
    return generated


def edit_event_time_hour_message(event_id: int, date: Arrow) -> TextMessage | None:
    generated = EventMessage(event_id)
    event = generated.event

    if not event:
        return None

    generated.format(
        f"Select hour for event:",
        event_formats["a"],
        create_time_hour_keyboard(
            f"etm {event_id} {date.date()}",
            f"em {event_id}",
            f"etm {event_id} {date.date()} None",
        ),
    )
    return generated


def edit_event_time_minute_message(
    event_id: int, date: Arrow, hour: int | None
) -> TextMessage | None:
    generated = EventMessage(event_id)
    event = generated.event

    if not event:
        return None

    generated.format(
        f"Select minute for event:",
        event_formats["a"],
        create_time_minute_keyboard(
            f"etset {event_id} {date.date()} {hour}",
            f"eth {event_id} {date.date()}",
            f"etset {event_id} {date.date()} {hour} None",
        ),
    )
    return generated


def edit_event_date_message(event_id: int, date: Arrow) -> EventMessage | None:
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
    id_list: list[int], date: Arrow | None = None
) -> EventsMessage:
    if date is None:
        date = request.entity.now_time()

    sql_where = """
user_id IS ?
AND group_id IS ?
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    generated = EventsMessage()
    generated.get_page_events(sql_where, params, id_list)
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
    Generates a message with delete buttons,
    deleting to bin (for premium) and changing the date.
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
                (
                    {f"🗑 {trash_bin}": f"edb {event.event_id} {event.date}"}
                    if request.entity.is_premium
                    else {}
                ),
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
    Generates a message with delete buttons,
    deleting to bin (for premium) and changing the date.
    """
    sql_where = """
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    generated = EventsMessage()
    generated.get_page_events(sql_where, params, id_list)

    is_wastebasket_available = request.entity.is_premium
    string_id = encode_id(id_list)
    date = generated.event_list[0].date if generated.event_list else ""
    delete_permanently = get_translate("text.delete_permanently")
    trash_bin = get_translate("text.trash_bin")
    markup = [
        [
            {f"❌ {delete_permanently}": f"esd {string_id} {date}"},
            (
                {f"🗑 {trash_bin}": f"esdb {string_id} {date}"}
                if is_wastebasket_available
                else {}
            ),
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


def search_results_message(
    query: str,
    filters: list[list[str]] = (),
    id_list: list[int] = (),
    page: int = 0,
    is_placeholder: bool = False,
) -> EventsMessage | TextMessage:
    """
    :param query: Search query
    :param filters:
    :param id_list: List of event_id
    :param page: Page number
    :param is_placeholder: Is a placeholder?
    """
    translate_search = get_translate("messages.search")
    nothing_found = get_translate("errors.nothing_found")

    if is_placeholder:
        text = f"🔍 {translate_search}\n\n{query.strip()}"
        markup = generate_buttons([[{get_theme_emoji("back"): "mnm"}]])
        return TextMessage(text, markup)

    query = query.replace("\n", " ").strip()

    if not query.strip() or query.isspace():
        generated = EventsMessage(markup=delmarkup())
        generated.format(
            title=f"🔍 {translate_search} ...:\n",
            if_empty=get_translate("errors.request_empty"),
        )
        return generated

    markup = generate_buttons(
        [
            [
                {get_theme_emoji("back"): "mnm"},
                {"↖️": "None"},
                {"↕️": "None"},
                {"🔄": "us"},
                {"💾": "sfe"} if request.entity.is_premium else {},
                {"⚙️": "sfs"},
            ]
        ]
    )
    generated = EventsMessage(markup=markup, page=int(page), page_indent=1)
    sql_where, params = generate_search_sql_condition(query, filters)

    if id_list:
        generated.get_page_events(sql_where, params, id_list)
    else:
        generated.get_pages_data(sql_where, params, "ps")

    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 1, f"se os {string_id} us")
    edit_button_data(generated.markup, 0, 2, f"ses s {string_id} us")

    string_filters = [
        f"{args[0]}: {html.escape(' '.join(args[1:]))}" for args in filters if args
    ]
    all_string_filters = "\n".join(string_filters)
    generated.format(
        title=f"🔍 {translate_search} <u>{html.escape(query)}</u>:\n{all_string_filters}",
        args=event_formats["r"],
        if_empty=nothing_found,
    )
    return generated


def search_filters_message(message: Message, call_data: str = "") -> TextMessage:
    query = extract_search_query(message.html_text)
    filters = extract_search_filters(message.html_text)
    if call_data.startswith("rm "):
        rmn = int(call_data.removeprefix("rm "))
        filters = [f for n, f in enumerate(filters) if rmn != n]
    string_filters = [
        f"{args[0]}: {html.escape(args[1])}" for args in filters if len(args) == 2
    ]
    translate_search = get_translate("messages.search")
    all_string_filters = "\n".join(string_filters)
    if all_string_filters:
        all_string_filters = f"\n{all_string_filters}"

    if query.isspace():
        markup = generate_buttons([[{get_theme_emoji("back"): "mnm"}]])
        generated = EventsMessage(markup=markup)
        generated.format(
            title=f"🔍 {translate_search} ...:\n",
            if_empty=get_translate("errors.request_empty"),
        )
        return generated

    raw_clue_1, raw_clue_2 = get_translate("text.search_filters_clue")
    clue_1 = (
        "\n" + raw_clue_1.format(get_theme_emoji("add")) if len(filters) < 6 else ""
    )
    clue_2 = "\n" + raw_clue_2 if len(filters) > 0 else ""
    text = f"""
🔍⚙️ {translate_search} <u>{html.escape(query)}</u>:{all_string_filters}
{clue_1}{clue_2}
"""
    markup = [
        *[
            [{f"{n + 1}) " + html.unescape(string_filter): f"sfs rm {n}"}]
            for n, string_filter in enumerate(string_filters)
        ],
        [
            {get_theme_emoji("back"): "us"},
            {get_theme_emoji("add"): "sf"} if len(filters) < 6 else {},
        ],
    ]
    return TextMessage(text, generate_buttons(markup))


def search_filter_message(message: Message, call_data: str) -> TextMessage:
    query = extract_search_query(message.html_text)
    filters = extract_search_filters(message.html_text)
    string_filters = [
        f"{args[0]}: {html.escape(' '.join(args[1:]))}" for args in filters if args
    ]
    translate_search = get_translate("messages.search")
    all_string_filters = "\n".join(string_filters)
    if all_string_filters:
        all_string_filters = "\n" + all_string_filters

    if query.isspace():
        markup = generate_buttons([[{get_theme_emoji("back"): "mnm"}]])
        generated = EventsMessage(markup=markup)
        generated.format(
            title=f"🔍 {translate_search} ...:\n",
            if_empty=get_translate("errors.request_empty"),
        )
        return generated

    search_filters: dict = get_translate("text.search_filters")
    clue_1, clue_2, clue_3 = get_translate("text.search_filter_clue")

    text = f"🔍⚙️ {translate_search} <u>{html.escape(query)}</u>:{all_string_filters}"
    markup = [
        # data before
        [{f"📆 {search_filters['db'][0]:{config.ts}<80}": "sf add db"}],
        # data during
        [{f"📆 {search_filters['dd'][0]:{config.ts}<80}": "sf add dd"}],
        # data after
        [{f"📆 {search_filters['da'][0]:{config.ts}<80}": "sf add da"}],
        # tag complete match
        [{f"🏷 {search_filters['tc'][0]:{config.ts}<80}": "sf edit tc ⬜ folders"}],
        # tag approximate match
        [{f"🏷 {search_filters['ta'][0]:{config.ts}<80}": "sf edit ta ⬜ folders"}],
        # tag not match
        [{f"🏷 {search_filters['tn'][0]:{config.ts}<80}": "sf edit tn ⬜ folders"}],
        [{get_theme_emoji("back"): "sfs"}],
    ]

    if call_data in ("add db", "add dd", "add da"):
        filter_type = call_data.split()[1]
        custom_text = f"{text}\n\n{clue_2}:\n{search_filters[filter_type][0]}:"
        return monthly_calendar_message(None, f"sf {call_data}", "sf", custom_text)

    elif call_data.startswith(("add db ", "add dd ", "add da ")):
        filter_type, date = call_data.split()[1:]
        description, sign = search_filters[filter_type]
        text = message.text.split("\n\n", maxsplit=1)[0]
        message.text = f"{text}\n{description}: {sign}{date}\n\n{clue_1}"
        return search_filters_message(message)

    elif call_data.startswith(("edit tc", "edit ta", "edit tn")):
        filter_type, statuses, folder = call_data.split()[1:]
        description, sign = search_filters[filter_type]
        text = message.text.split("\n\n", maxsplit=1)[0]
        message.text = f"{text}\n\n{clue_3}\n{description}: {sign}{statuses}"
        markup = create_select_status_keyboard(
            prefix=f"sf edit {filter_type}",
            status_list=statuses.split(","),
            folder_path=folder,
            save=f"sf add {filter_type}",
            back="sf",
        )
        return TextMessage(message.html_text, markup)

    elif call_data.startswith(("add tc", "add ta", "add tn")):
        filter_type, statuses = call_data.split()[1:]
        description, sign = search_filters[filter_type]
        text = message.text.split("\n\n", maxsplit=1)[0]
        message.text = f"{text}\n{description}: {sign}{statuses}\n\n{clue_1}:\n{search_filters[filter_type][0]}:"
        return search_filters_message(message)

    return TextMessage(f"{text}\n\n{clue_1}", generate_buttons(markup))


def week_event_list_message(id_list: list[int] = (), page: int = 0) -> EventsMessage:
    """
    :param id_list: List of event_id
    :param page: Page number
    """
    tz = request.entity.settings.timezone
    sql_where = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
AND (
    (
        DATE(datetime) BETWEEN DATE('now', '{tz} HOURS')
                           AND DATE('now', '+7 day', '{tz} HOURS')
    )
    OR ( -- Every year
        repetition = 'repeat every year'
        AND STRFTIME('%Y-', 'now', '{tz} HOURS') || STRFTIME('%m-%d', datetime)
            BETWEEN STRFTIME('%Y-%m-%d', 'now', '{tz} HOURS')
                AND STRFTIME('%Y-%m-%d', 'now', '+7 day', '{tz} HOURS')
    )
    OR ( -- Every month
        repetition = 'repeat every month'
        AND STRFTIME('%Y-%m-', 'now', '{tz} HOURS') || STRFTIME('%d', datetime)
            BETWEEN STRFTIME('%Y-%m-%d', 'now', '{tz} HOURS')
                AND STRFTIME('%Y-%m-%d', 'now', '+7 day', '{tz} HOURS')
    )
    OR ( -- Every weekdays
        repetition = 'repeat every weekdays'
        -- AND STRFTIME('%w', datetime) BETWEEN '1' AND '5'
    )
    OR repetition = 'repeat every week' -- Every week
    OR repetition = 'repeat every day' -- Every day
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
        generated.get_page_events(sql_where, params, id_list)
    else:
        generated.get_pages_data(sql_where, params, "pw")
    string_id = encode_id([event.event_id for event in generated.event_list])
    edit_button_data(generated.markup, 0, 2, f"se o {string_id} mnw")
    generated.format(
        title=f"7️⃣ {get_translate('text.week_events')}",
        args=event_formats["r"],
        if_empty=get_translate("errors.nothing_found"),
    )
    return generated


def trash_can_message(id_list: list[int] = (), page: int = 0) -> EventsMessage:
    """
    :param id_list: List of event_id
    :param page: Page number
    """
    sql_where = """
user_id IS ?
AND group_id IS ?
AND removal_time IS NOT NULL
"""
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
    )
    db.execute(
        """
-- Deleting events older than 30 days
DELETE FROM events
      WHERE removal_time IS NOT NULL
            AND (JULIANDAY('now') - JULIANDAY(removal_time) > 30);
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
        generated.get_page_events(sql_where, params, id_list)
    else:
        generated.get_pages_data(sql_where, params, "pb")

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
    n_date: Arrow | None = None,
    id_list: list[int] = (),
    page: int = 0,
    from_command: bool = False,
) -> EventsMessage | None:
    if n_date is None:
        n_date = request.entity.now_time()

    dates = [n_date.shift(days=days) for days in (0, 1, 2, 3, 7)]
    weekdays = ["0" if (w := date.weekday()) == 6 else f"{w + 1}" for date in dates[:2]]
    sql_where = f"""
user_id IS ?
AND group_id IS ?
AND removal_time IS NULL
AND (
    ( -- For today and +1 day
        datetime IN ('{dates[0]:YYYY-MM-DD}', '{dates[1]:YYYY-MM-DD}')
    )
    OR ( -- Matches on +2, +3 and +7 days
        repetition = 'repeat every week'
        AND DATE(datetime) IN ({", ".join(f"'{date:YYYY-MM-DD}'" for date in dates[2:])})
    )
    OR ( -- Every year
        repetition = 'repeat every year'
        AND STRFTIME('%m-%d', datetime) IN ({", ".join(f"'{date:MM-DD}'" for date in dates)})
    )
    OR ( -- Every month
        STRFTIME('%d', datetime) IN ({", ".join(f"'{date:DD}'" for date in dates)})
        AND repetition = 'repeat every month'
    )
    OR ( -- Every week
        repetition = 'repeat every week'
        AND STRFTIME('%w', datetime) IN ({", ".join(f"'{w}'" for w in weekdays)})
    )
    OR ( -- Every weekdays
        repetition = 'repeat every weekdays'
        AND STRFTIME('%w', ?) BETWEEN '1' AND '5'
        -- AND STRFTIME('%w', datetime) BETWEEN '1' AND '5'
    )
    OR ( -- Every day
        repetition = 'repeat every day'
    )
)
    """
    params = (
        request.entity.safe_user_id,
        request.entity.group_id,
        f"{n_date:YYYY-MM-DD}",
    )

    markup = generate_buttons(
        [
            [
                {get_theme_emoji("back"): "mnm"},
                {"📆": f"mnnc {n_date:YYYY-MM-DD}"} if from_command else {},
                {"🔄": f"mnn {n_date:YYYY-MM-DD}"},
                {"↖️": "None"},
            ]
        ]
    )

    generated = EventsMessage(markup=markup, page=page)
    if id_list:
        generated.get_page_events(sql_where, params, id_list)
    else:
        generated.get_pages_data(sql_where, params, f"pn {n_date:YYYY-MM-DD}")
        string_id = encode_id([event.event_id for event in generated.event_list])
        edit_button_data(
            generated.markup, 0, -1, f"se o {string_id} mnn {n_date:YYYY-MM-DD}"
        )

    if generated.event_list or from_command:
        reminder_translate = get_translate("messages.reminder")
        generated.format(
            title=f"🔔 {reminder_translate} <b>{n_date:YYYY-MM-DD}</b>",
            args=event_formats["r"],
            if_empty=get_translate("errors.message_empty"),
        )
        return generated
    return None


def send_notifications_messages() -> None:
    n_date = arrow.utcnow()
    with db.connection(), db.cursor():
        result = db.execute(
            """
-- send_notifications_messages
SELECT CAST(
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
           ) AS INT
       ),
       CAST(notifications AS INT),
       CASE
           WHEN tg_settings.user_id THEN 'user'
           WHEN tg_settings.group_id THEN (
               SELECT 'group:'
                      || (
                          SELECT chat_id
                            FROM users
                           WHERE user_id = owner_id
                      )
                 FROM groups
                WHERE groups.group_id = tg_settings.group_id
           )
           ELSE NULL
       END
  FROM tg_settings
 WHERE notifications != 0
       AND (STRFTIME('%H', notifications_time) - timezone + 24) % 24 = :hour
       AND STRFTIME('%M', notifications_time) = :minute;
""",
            params={
                "hour": n_date.hour,
                "minute": n_date.minute,
            },
        )

    for chat_id, n_type, a_type in result:
        try:
            if a_type.startswith("user"):
                request.entity = TelegramAccount(chat_id)
            elif a_type.startswith("group:"):
                owner_id = a_type.split(":")[1]
                request.entity = TelegramAccount(owner_id, chat_id)
        except (UserNotFound, GroupNotFound):
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

            logger.info(
                f"notifications -> {request.entity.request_chat_id} -> {status}"
            )


def monthly_calendar_message(
    yy_mm: list | tuple[int, int] = None,
    command: str = None,
    back: str = None,
    custom_text: str = None,
    arguments: str = None,
) -> TextMessage:
    text = custom_text if custom_text else get_translate("select.date")
    markup = create_monthly_calendar_keyboard(yy_mm, command, back, arguments)
    return TextMessage(text, markup)


def limits_message(date: Arrow = None) -> TextMessage:
    if date is None:
        date = request.entity.now_time()

    if not is_valid_year(date.year):
        return TextMessage(get_translate("errors.error"))

    return TextMessage(
        get_limit_link(f"{date:YYYY-MM-DD}"),
        generate_buttons([[{get_theme_emoji("back"): "lm"}]]),
    )


def group_message(
    group_id: str, message_id: int = None, mode: str = "al"
) -> TextMessage | None:
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
        change_group_name = "✏️ " + get_translate("text.change_group_name")
        delete_group = "🗑👥 " + get_translate("text.delete_group")
        remove_bot_from_group = "🚪👈 " + get_translate("text.remove_bot_from_group")
        export_group = "💾 " + get_translate("text.export_group")

        if group.member_status == 2:
            markup = generate_buttons(
                [
                    [
                        (
                            {
                                change_group_name: {
                                    "switch_inline_query_current_chat": (
                                        f"group({group.group_id}, {message_id}).name\n"
                                        f"{html.unescape(group.name)}"
                                    )
                                }
                            }
                            if message_id
                            else {change_group_name: "None"}
                        ),
                    ],
                    [
                        {delete_group: f"grdb {group.group_id} {mode}"},
                        (
                            {remove_bot_from_group: f"grrgr {group.group_id} {mode}"}
                            if group.chat_id
                            else {
                                get_translate("text.add_bot_to_group"): {
                                    "url": startgroup_url
                                }
                            }
                        ),
                    ],
                    [
                        {get_theme_emoji("back"): f"mngrs {mode}"},
                        {export_group: f"gre {group.group_id} csv"},
                    ],
                ]
            )
        elif group.member_status == 1:
            markup = generate_buttons(
                [
                    [
                        {export_group: f"gre {group.group_id} csv"},
                        (
                            {
                                change_group_name: {
                                    "switch_inline_query_current_chat": (
                                        f"group({group.group_id}, {message_id}).name\n"
                                        f"{html.unescape(group.name)}"
                                    )
                                }
                            }
                            if message_id
                            else {change_group_name: "None"}
                        ),
                    ],
                    [
                        (
                            {remove_bot_from_group: f"grrgr {group.group_id} {mode}"}
                            if group.chat_id
                            else {
                                get_translate("text.add_bot_to_group"): {
                                    "url": startgroup_url
                                }
                            }
                        ),
                    ],
                    [
                        {get_theme_emoji("back"): f"mngrs {mode}"},
                        {leave_group: f"grlv {group.group_id} {mode}"},
                    ],
                ]
            )
        else:
            markup = generate_buttons(
                [
                    [
                        {get_theme_emoji("back"): f"mngrs {mode}"},
                        {leave_group: f"grlv {group.group_id} {mode}"},
                    ],
                ]
            )
    else:
        text += f"\nowner_id: `<code>{group.owner_id}</code>`"
        markup = generate_buttons([[{get_theme_emoji("back"): "mnm"}]])

    return TextMessage(text, markup)


def delete_group_message(
    group_id: str, message_id: int = None, mode: str = "al"
) -> TextMessage | None:
    try:
        if request.is_member:
            group = request.entity.group
        else:
            group = request.entity.get_group(group_id)
    except GroupNotFound:
        return None

    message = group_message(group_id, message_id, mode)

    if request.is_user and group.member_status == 2:
        delete_group = "🗑👥 " + get_translate("text.delete_group")

        message.markup = generate_buttons(
            [
                [
                    {get_theme_emoji("back"): f"mngr {group_id} {mode}"},
                    {delete_group: f"grd {group.group_id} {mode}"},
                ]
            ]
        )
    else:
        pass

    return message


def groups_message(
    mode: Literal["al", "me", "md", "ad"] | str = "al", page: int = 1
) -> TextMessage:
    match mode:
        case "al":
            raw_groups = request.entity.get_my_groups()
        case "me":
            raw_groups = request.entity.get_groups_where_i_member()
        case "md":
            raw_groups = request.entity.get_groups_where_i_moderator()
        case "ad":
            raw_groups = request.entity.get_groups_where_i_admin()
        case _:
            raise ValueError

    groups_chunk = list(chunks(raw_groups, 6))
    groups = groups_chunk[page - 1] if len(groups_chunk) > 0 else []
    prev_pages, after_pages = len(groups_chunk[: page - 1]), len(groups_chunk[page:])
    create_group, groups_message_template, group_template, buttons = get_translate(
        "messages.groups"
    )
    btn_all, btn_member, btn_moderator, btn_admin = buttons

    if groups or mode:
        string_groups = "\n\n".join(
            group_template.format(
                page=n + (6 * page - 6) + 1,
                name=html.escape(group.name),
                group_id=group.group_id,
                status=get_translate(f"text.status.{group.member_status}").capitalize(),
                entry_date=parse_utc_datetime(group.entry_date),
                chat_id=group.chat_id if group.chat_id else "-",
            ).strip()
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
                {("🔸" if mode == "al" else "") + btn_all: "mngrs al"},
                {("🔸" if mode == "me" else "") + btn_member: "mngrs me"},
                {("🔸" if mode == "md" else "") + btn_moderator: "mngrs md"},
                {("🔸" if mode == "ad" else "") + btn_admin: "mngrs ad"},
            ],
            *[[{f"{group.name}": f"mngr {group.group_id} {mode}"}] for group in groups],
            [
                {get_theme_emoji("back"): "mnm"},
                *(
                    [
                        (
                            {"<": f"mngrs {mode} {page - 1}"}
                            if prev_pages
                            else {" ": "None"}
                        ),
                        (
                            {">": f"mngrs {mode} {page + 1}"}
                            if after_pages
                            else {" ": "None"}
                        ),
                    ]
                    if len(groups_chunk) != 1 and groups
                    else []
                ),
                {f"👥 {create_group}": "grcr"},
            ],
        ]
    else:
        text = groups_message_template.format(0, "")
        markup = [[{get_theme_emoji("back"): "mnm"}, {f"👥 {create_group}": "grcr"}]]
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
            (
                [{f"{get_translate('text.get_premium')}🤩": "get_premium"}]
                if request.entity.user.user_status == 0
                else []
            ),
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
    if len(id_list) == 0:
        return None

    try:
        events_list = request.entity.get_events(id_list, is_in_wastebasket)
    except EventNotFound:
        return None

    if len(events_list) == 1:
        event = events_list[0]
        if is_open:
            generated = daily_message(event.datetime)
        else:
            generated = event_message(event.event_id, is_in_wastebasket, message_id)

        return generated

    markup = []
    for event in events_list:
        date = event.datetime.shift(hours=request.entity.settings.timezone)
        button_title = f"{date:HH:mm}.{event.string_statuses}.{event.string_repetition} {event.text}"
        button_title = button_title.ljust(60, "⠀")[:60]

        if is_in_wastebasket or is_in_search or is_open:
            button_title = f"{date:YYYY.MM.DD} {button_title}"[:60]

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
    if len(id_list) == 0:
        return None

    try:
        events_list = request.entity.get_events(id_list, in_bin)
    except EventNotFound:
        return None

    if len(events_list) == 1:
        return events_message([events_list[0].event_id], in_bin)

    markup = []
    for n, event in enumerate(events_list):
        date = event.datetime.shift(hours=request.entity.settings.timezone)
        button_title = f"{date:HH:mm}.{event.string_statuses}.{event.string_repetition} {event.text}"
        button_title = button_title.ljust(60, "⠀")[:60]

        if in_bin or is_in_search:
            button_title = f"{date:YYYY.MM.DD} {button_title}"[:60]

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
