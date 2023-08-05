import re
from datetime import timedelta, datetime

from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

import logging
from db.db import SQL
from lang import get_translate
from utils import remove_html_escaping
from db.sql_utils import sqlite_format_date, sqlite_format_date2
from time_utils import convert_date_format, now_time, now_time_strftime
from user_settings import UserSettings
from messages.message_generator import MessageGenerator
from buttons_utils import (
    delmarkup,
    delopenmarkup,
    generate_buttons,
    edit_button_attrs,
    backopenmarkup,
)


backslash_n = "\n"  # Для использования внутри f строк


def search(
    settings: UserSettings,
    chat_id: int,
    query: str,
    id_list: list | tuple[str] = tuple(),
    page: int | str = 1,
) -> MessageGenerator:
    """
    :param settings: settings
    :param chat_id: chat_id
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
    if not re.match(r"\S", query):
        generated = MessageGenerator(settings, reply_markup=delmarkup)
        generated.format(
            title=f"🔍 {get_translate('search', settings.lang)} {query}:\n",
            if_empty=get_translate("request_empty", settings.lang),
        )
        return generated

    # re_day = re.compile(r"[#\b ]day=(\d{1,2})[\b]?")
    # re_month = re.compile(r"[#\b ]month=(\d{1,2})[\b]?")
    # re_year = re.compile(r"[#\b ]year=(\d{4})[\b]?")
    # re_id = re.compile(r"[#\b ]id=(\d{,6})[\b]?")
    # re_status = re.compile(r"[#\b ]status=(\S+)[\b]?")

    querylst = query.replace("\n", " ").split()
    splitquery = " OR ".join(
        f"date LIKE '%{x}%' OR text LIKE '%{x}%' OR status LIKE '%{x}%' OR event_id LIKE '%{x}%'"
        for x in querylst
    )
    WHERE = f"(user_id={chat_id} AND removal_time=0) AND ({splitquery})"

    generated = MessageGenerator(settings, reply_markup=delopenmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction=settings.direction)
    generated.format(
        title=f"🔍 {get_translate('search', settings.lang)} {query}:\n"
        f"{'<b>' + get_translate('page', settings.lang) + f' {page}</b>{backslash_n}' if int(page) > 1 else ''}",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({reldate})\n{markdown_text}\n",
        if_empty=get_translate("nothing_found", settings.lang),
    )

    return generated


def week_event_list(
    settings: UserSettings,
    chat_id: int,
    id_list: list | tuple[str] = tuple(),
    page: int | str = 1,
) -> MessageGenerator:
    """
    :param settings: settings
    :param chat_id: chat_id
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с событиями в эту неделю:
        week_event_list(settings=settings, chat_id=chat_id)
    Изменить страницу:
        week_event_list(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"""
    (user_id={chat_id} AND removal_time=0) AND (
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
            BETWEEN strftime('%m-%d', 'now', '{settings.timezone:+} hours')
                AND strftime('%m-%d', 'now', '+7 day', '{settings.timezone:+} hours')
        )
        OR status LIKE '%🗞%' -- Каждую неделю
        OR status LIKE '%📬%' -- Каждый день
    )
    """

    generated = MessageGenerator(settings, reply_markup=delmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction="ASC")
    generated.format(
        title=f"📆 {get_translate('week_events', settings.lang)} 📆\n"
        f"{'<b>' + get_translate('page', settings.lang) + f' {page}</b>{backslash_n}' if int(page) > 1 else ''}",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
        if_empty=get_translate("nothing_found", settings.lang),
    )
    return generated


def deleted(
    settings: UserSettings,
    chat_id: int,
    id_list: list | tuple[str] = tuple(),
    page: int | str = 1,
) -> MessageGenerator:
    """
    :param settings: settings
    :param chat_id: chat_id
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с корзиной:
        deleted(settings=settings, chat_id=chat_id)
    Изменить страницу:
        deleted(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"user_id={chat_id} AND removal_time!=0"
    # Удаляем события старше 30 дней
    SQL(
        """
DELETE FROM events
      WHERE removal_time != 0 AND 
            (julianday('now') - julianday(removal_time) > 30);
""",
        commit=True,
    )

    delete_permanently_translate = get_translate("delete_permanently", settings.lang)
    recover_translate = get_translate("recover", settings.lang)
    clean_bin_translate = get_translate("clean_bin", settings.lang)
    basket_translate = get_translate("basket", settings.lang)
    page_translate = get_translate("page", settings.lang)
    message_empty_translate = get_translate("message_empty", settings.lang)

    generated = MessageGenerator(
        settings,
        reply_markup=generate_buttons(
            [
                {
                    "✖": "message_del",
                    f"❌ {delete_permanently_translate}": "select event delete bin",
                },
                {
                    "🔄": "update",
                    f"↩️ {recover_translate}": "select event recover bin",
                },
                {f"🧹 {clean_bin_translate}": "clean_bin"},
            ]
        ),
    )

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction=settings.direction)

    generated.format(
        title=f"🗑 {basket_translate} 🗑\n"
        f"{'<b>' + page_translate + f' {page}</b>{backslash_n}' if int(page) > 1 else ''}",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({days_before_delete})\n{markdown_text}\n",
        if_empty=message_empty_translate,
    )
    return generated


def daily_message(
    settings: UserSettings,
    chat_id: int,
    date: str,
    id_list: list | tuple[str] = tuple(),
    page: int | str = 1,
    message_id: int = None,
) -> MessageGenerator:
    """
    :param settings: settings
    :param chat_id: chat_id
    :param date: дата у сообщения
    :param id_list: Список из event_id
    :param page: Номер страницы
    :param message_id: Используется когда в сообщении одно событие для генерации кнопки для изменения события

    Вызвать сообщение с сегодняшним днём:
        today_message(settings=settings, chat_id=chat_id, date=now_time_strftime(settings.timezone))
    Изменить страницу:
        today_message(settings=settings, chat_id=chat_id, date=date, id_list=id_list, page=page)
    """
    WHERE = f"user_id = {chat_id} AND date = '{date}' AND removal_time = 0"

    new_date = convert_date_format(date)
    if 1980 < (new_date - timedelta(days=1)).year < 3000:
        yesterday = (new_date - timedelta(days=1)).strftime("%d.%m.%Y")
    else:
        yesterday = "None"

    if 1980 < (new_date + timedelta(days=1)).year < 3000:
        tomorrow = (new_date + timedelta(days=1)).strftime("%d.%m.%Y")
    else:
        tomorrow = "None"

    markup = generate_buttons(
        [
            {
                "➕": "event_add",
                "📝": "select event edit",
                "🚩": "select event status",
                "🗑": "select event delete",
            },
            {"🔙": "back", "<": yesterday, ">": tomorrow, "🔄": "update"},
        ]
    )
    generated = MessageGenerator(settings, date=date, reply_markup=markup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction=settings.direction)

    # Изменяем уже существующий `generated`, если в сообщение событие только одно.
    if len(generated.event_list) == 1 and message_id:
        event = generated.event_list[0]
        edit_button_attrs(
            markup=generated.reply_markup,
            row=0,
            column=1,
            old="callback_data",
            new="switch_inline_query_current_chat",
            val=f"event({event.date}, {event.event_id}, {message_id}).edit\n"
            f"{remove_html_escaping(event.text)}",
        )

    generated.format(
        title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n"
        f"{'<b>' + get_translate('page', settings.lang) + f' {page}</b>{backslash_n}' if int(page) > 1 else ''}",
        args="<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n",
        if_empty=get_translate("nodata", settings.lang),
    )

    # Добавить дополнительную кнопку для дней в которых есть праздники
    daylist = [
        x[0]
        for x in SQL(
            f"""
-- Кнопка повторяющихся событий
SELECT DISTINCT date
  FROM events
 WHERE user_id = :user_id AND 
       removal_time = 0 AND
(
    ( -- Каждый год
        (
            status LIKE '%🎉%'
            OR
            status LIKE '%🎊%'
            OR
            status LIKE '%📆%'
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
        CAST(strftime('%w', '{sqlite_format_date2(date)}') as TEXT)
    )
    OR
    ( -- Каждый день
        status LIKE '%📬%'
    )
);
""",
            params={"user_id": chat_id, "y_date": f"{date[:-5]}.____", "m_date": f"{date[:2]}.__.____"}
        )
        if x[0] != date
    ]
    if daylist:
        generated.reply_markup.row(InlineKeyboardButton("📅", callback_data="recurring"))
    return generated


def notifications(
    user_id_list: list | tuple[int | str, ...] = None,
    id_list: list | tuple[str] = tuple(),
    page: int | str = 1,
    message_id: int = -1,
    markup: InlineKeyboardMarkup = None,
    from_command: bool = False,
) -> None:
    """
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
        user_id_list = [
            int(user_id)
            for user in SQL(
                f"""
SELECT GROUP_CONCAT(user_id, ',') AS user_id_list
FROM settings
WHERE notifications = 1 AND user_status != -1
AND ((CAST(SUBSTR(notifications_time, 1, 2) AS INT) - timezone + 24) % 24) = {n_time.hour}
AND CAST(SUBSTR(notifications_time, 4, 2) AS INT) = {n_time.minute};
"""
            )
            if user[0]
            for user_id in user[0].split(",")
        ]  # [('id1,id2,id3',)] -> [id1, id2, id3]

    for user_id in user_id_list:
        settings = UserSettings(user_id)

        if settings.notifications or from_command:
            _now = datetime.utcnow()
            dates = [
                _now + timedelta(days=days, hours=settings.timezone)
                for days in (0, 1, 2, 3, 7)
            ]
            strdates = [date.strftime("%d.%m.%Y") for date in dates]
            weekdays = [
                "0" if (w := date.weekday()) == 6 else str(w + 1) for date in dates[1:]
            ]
            del _now, dates

            WHERE = f"""
user_id={user_id} AND removal_time=0
AND
(
    ( -- На сегодняшние даты
        (
            status LIKE '%🔔%'
            OR
            status LIKE '%🔕%'
        )
        AND date='{strdates[0]}'
    ) 
    OR
    ( -- Совпадения сегодня и +1, +2, +3 и +7 дней
        status LIKE '%🟥%'
        AND date IN ({", ".join(f"'{date}'" for date in strdates)})
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
        status LIKE '%📅%'
        AND SUBSTR(date, 1, 2) IN ({", ".join(f"'{date[:2]}'" for date in strdates)})
    )
    OR
    ( -- Каждую неделю
        status LIKE '%🗞%'
        AND
        strftime('%w', {sqlite_format_date('date')}) IN ({", ".join(f"'{w}'" for w in weekdays)})
    )
    OR
    ( -- Каждый день
        status LIKE '%📬%'
    )
)
"""

            generated = MessageGenerator(settings, reply_markup=delmarkup)

            if id_list:
                generated.get_events(WHERE=WHERE, values=id_list)
            else:
                generated.get_data(WHERE=WHERE, direction="ASC")

            if len(generated.event_list) or from_command:
                # Если в generated.event_list есть события
                # или
                # Если уведомления вызывали командой (сообщение на команду приходит даже если оно пустое)
                reminder_translate = get_translate("reminder", settings.lang)
                page_translate = get_translate("page", settings.lang)

                generated.format(
                    title=(
                        f"🔔 {reminder_translate} 🔔\n"
                        f"{'<b>' + page_translate + f' {page}</b>{backslash_n}' if int(page) > 1 else ''}"
                    ),
                    args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
                    "{weekday}</i></u> ({reldate})\n{markdown_text}\n",
                    if_empty=get_translate("message_empty", settings.lang),
                )

                logging.info(
                    f"[message_generators.py -> notifications] -> {user_id} -> "
                )

                try:
                    if id_list:
                        generated.edit(
                            chat_id=user_id, message_id=message_id, markup=markup
                        )
                    else:
                        generated.send(chat_id=user_id)
                    if not from_command:
                        SQL(
                            """
UPDATE events
   SET status = REPLACE(status, '🔔', '🔕') 
 WHERE status LIKE '%🔔%' AND 
       date = ?;
""",
                            params=(now_time_strftime(settings.timezone),),
                            commit=True,
                        )
                    logging.info("Ok")
                except ApiTelegramException:
                    logging.info("Error")


def recurring(
    settings: UserSettings,
    date: str,
    chat_id: int,
    id_list: list | tuple[str] = tuple(),
    page: int | str = 1,
):
    """
    :param settings: settings
    :param date: дата у сообщения
    :param chat_id: chat_id
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с повторяющимися событиями:
        recurring(settings=settings, date=date, chat_id=chat_id)
    Изменить страницу:
        recurring(settings=settings, date=date, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"""
user_id = {chat_id} AND removal_time = 0
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
    generated = MessageGenerator(
        settings=settings, date=date, reply_markup=backopenmarkup
    )

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction=settings.direction, prefix="|!")

    generated.format(
        title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n"
        f"{'<b>' + get_translate('page', settings.lang) + f' {page}</b>{backslash_n}' if int(page) > 1 else ''}",
        args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  "
        "{weekday}</i></u> ({reldate})\n{markdown_text}\n",
        if_empty=get_translate("nothing_found", settings.lang),
    )
    return generated


def settings_message(settings: UserSettings) -> MessageGenerator:
    """
    Ставит настройки для пользователя chat_id
    """
    not_lang = "ru" if settings.lang == "en" else "en"
    not_sub_urls = 1 if settings.sub_urls == 0 else 0
    not_direction_smile = {"DESC": "⬆️", "ASC": "⬇️"}[settings.direction]
    not_direction_sql = {"DESC": "ASC", "ASC": "DESC"}[settings.direction]
    not_notifications_ = ("🔕", 0) if settings.notifications else ("🔔", 1)
    n_hours, n_minutes = [int(i) for i in settings.notifications_time.split(":")]

    utz = settings.timezone
    str_utz = (
        f"""{utz} {"🌍" if -2 < int(utz) < 5 else ("🌏" if 4 < int(utz) < 12 else "🌎")}"""
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
        notifications_time["-1h"] = "settings notifications_time {}".format(
            f"{n_hours-1:0>2}:{n_minutes:0>2}"
            if n_hours > 0 else
            f"23:{n_minutes:0>2}"
        )
        notifications_time["-10m"] = "settings notifications_time {}".format(
            f"{n_hours:0>2}:{n_minutes-10:0>2}"
            if n_minutes > 0 else
            f"{n_hours-1:0>2}:50"
        )
        notifications_time[
            f"{n_hours:0>2}:{n_minutes:0>2} ⏰"
        ] = "settings notifications_time {}".format("08:00")
        notifications_time["+10m"] = "settings notifications_time {}".format(
            f"{n_hours:0>2}:{n_minutes+10:0>2}"
            if n_minutes < 50 else
            f"{n_hours+1:0>2}:00"
        )
        notifications_time["+1h"] = "settings notifications_time {}".format(
            f"{n_hours+1:0>2}:{n_minutes:0>2}"
            if n_hours < 23 else
            f"00:{n_minutes:0>2}"
        )

    text = get_translate("settings", settings.lang).format(
        settings.lang,
        bool(settings.sub_urls),
        settings.city,
        str_utz,
        now_time(settings.timezone).strftime("%H:%M  %d.%m.%Y"),
        {"DESC": "⬇️", "ASC": "⬆️"}[settings.direction],
        "🔔" if settings.notifications else "🔕",
        f"{n_hours:0>2}:{n_minutes:0>2}" if settings.notifications else "",
    )
    markup = generate_buttons(
        [
            {
                f"🗣 {settings.lang}": f"settings lang {not_lang}",
                f"🔗 {bool(settings.sub_urls)}": f"settings sub_urls {not_sub_urls}",
                f"{not_direction_smile}": f"settings direction {not_direction_sql}",
                f"{not_notifications_[0]}": f"settings notifications {not_notifications_[1]}",
            },
            time_zone_dict,
            notifications_time,
            {"✖": "message_del"},
        ]
    )

    generated = MessageGenerator(settings, reply_markup=markup)
    generated.format(title="", args="", ending=text, if_empty="")
    return generated
