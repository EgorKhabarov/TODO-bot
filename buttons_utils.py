from calendar import monthcalendar

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from lang import get_translate
from sql_utils import sqlite_format_date
from time_utils import new_time_calendar, year_info, now_time
from todoapi.types import db


def generate_buttons(buttons_data: list[dict]) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры из списка словарей

    Два ряда по 2 кнопке c callback_data в каждом ряду
    markup = generate_buttons([
        {"Кнопка 1": "button data 1", Кнопка 2": "button data 2"}
        {"Кнопка 3": "button data 3", Кнопка 4": "button data 4"}])

    Пример с другими аргументами
    markup = generate_buttons([{"Ссылка": {"url": "https://example.com"}}])

    Поддерживаются:
    url, callback_data, switch_inline_query, switch_inline_query_current_chat

    Не поддерживается:
    web_app, callback_game, pay, login_url
    """
    keyboard = [
        [
            InlineKeyboardButton(text=text, callback_data=data)
            if isinstance(data, str)
            else InlineKeyboardButton(
                text=text,
                url=data.get("url"),
                callback_data=data.get("callback_data"),
                switch_inline_query=data.get("switch_inline_query"),
                switch_inline_query_current_chat=data.get(
                    "switch_inline_query_current_chat"
                ),
            )
            for text, data in row.items()
        ]
        for row in buttons_data
    ]
    return InlineKeyboardMarkup(keyboard=keyboard)


def create_monthly_calendar_keyboard(
    chat_id: str | int,
    user_timezone: int,
    lang: str,
    YY_MM: list | tuple[int, int] = None,
) -> InlineKeyboardMarkup:
    """
    Создаёт календарь на месяц и возвращает inline клавиатуру
    param YY_MM: Необязательный аргумент. Если None, то подставит текущую дату.
    """
    if YY_MM:
        YY, MM = YY_MM
    else:
        YY, MM = new_time_calendar(user_timezone)

    markup = InlineKeyboardMarkup()
    #  December (12.2022)
    # Пн Вт Ср Чт Пт Сб Вс
    title = (
        f"{get_translate('months_name', lang)[MM - 1]} "
        f"({MM}.{YY}) ({year_info(YY, lang)})"
    )
    markup.row(
        InlineKeyboardButton(
            text=title, callback_data=f"generate calendar months  {YY}"
        )
    )
    markup.row(
        *[
            InlineKeyboardButton(text=week_day, callback_data="None")
            for week_day in get_translate("week_days_list", lang)
        ]
    )

    # Дни в которые есть события
    has_events = {
        x[0]: x[1]
        for x in db.execute(
            """
SELECT CAST (SUBSTR(date, 1, 2) AS INT) AS day_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id = ? AND 
       removal_time = 0 AND 
       date LIKE ?
 GROUP BY day_number;
    """,
            params=(chat_id, f"__.{MM:0>2}.{YY}"),
        )
    }

    # Дни рождения, праздники и каждый год или месяц
    every_year_or_month = [
        x[0]
        for x in db.execute(
            """
SELECT DISTINCT CAST (SUBSTR(date, 1, 2) AS INT) 
  FROM events
 WHERE user_id = ? AND 
       removal_time = 0 AND 
       ( ( (status LIKE '%🎉%' OR 
            status LIKE '%🎊%' OR 
            status LIKE '%📆%') AND 
           SUBSTR(date, 4, 2) = ?) OR 
         status LIKE '%📅%');
""",
            params=(chat_id, f"{MM:0>2}"),
        )
    ]

    # Каждую неделю
    every_week = [
        6 if x[0] == -1 else x[0]
        for x in db.execute(
            f"""
SELECT DISTINCT CAST (strftime('%w', {sqlite_format_date('date')}) - 1 AS INT) 
  FROM events
 WHERE user_id = ? AND 
       removal_time = 0 AND 
       status LIKE '%🗞%';
""",
            params=(chat_id,),
        )
    ]

    # получаем сегодняшнее число
    today = now_time(user_timezone).day
    # получаем список дней
    for weekcalendar in monthcalendar(YY, MM):
        weekbuttons = []
        for wd, day in enumerate(weekcalendar):
            if day == 0:
                weekbuttons.append(InlineKeyboardButton("  ", callback_data="None"))
            else:
                tag_today = "#" if day == today else ""
                x = has_events.get(day)
                tag_event = (
                    "".join(
                        calendar_event_count_template[int(ch)] for ch in str(x)
                    ) if x < 10 else "*"
                ) if x else ""
                tag_birthday = (
                    "!" if (day in every_year_or_month or wd in every_week) else ""
                )
                weekbuttons.append(
                    InlineKeyboardButton(
                        f"{tag_today}{day}{tag_event}{tag_birthday}",
                        callback_data=f"{day:0>2}.{MM:0>2}.{YY}",
                    )
                )
        markup.row(*weekbuttons)

    markup.row(
        *[
            InlineKeyboardButton(
                f"{text}", callback_data=f"generate calendar days {data}"
            )
            for text, data in {
                "<<": f"{YY - 1} {MM}",
                "<": f"{YY - 1} {12}" if MM == 1 else f"{YY} {MM - 1}",
                "⟳": "now",
                ">": f"{YY + 1} {1}" if MM == 12 else f"{YY} {MM + 1}",
                ">>": f"{YY + 1} {MM}",
            }.items()
        ]
    )
    return markup


def create_yearly_calendar_keyboard(
    user_timezone: int, lang: str, chat_id, YY
) -> InlineKeyboardMarkup:
    """
    Создаёт календарь из месяцев на определённый год и возвращает inline клавиатуру
    """
    # В этом году
    month_list = {
        x[0]: x[1]
        for x in db.execute(
            """
SELECT CAST (SUBSTR(date, 4, 2) AS INT) AS month_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id = ? AND 
       date LIKE ? AND
       removal_time = 0
 GROUP BY month_number;
""",
            params=(chat_id, f"__.__.{YY}"),
        )
    }

    # Повторение каждый год
    every_year = [
        x[0]
        for x in db.execute(
            """
SELECT DISTINCT CAST (SUBSTR(date, 4, 2) AS INT) 
  FROM events
 WHERE user_id = ? AND 
       removal_time = 0 AND 
       (status LIKE '%🎉%' OR 
        status LIKE '%🎊%' OR 
        status LIKE '%📆%');
""",
            params=(chat_id,),
        )
    ]

    # Повторение каждый месяц
    every_month = [
        x[0]
        for x in db.execute(
            """
SELECT date
  FROM events
 WHERE user_id = ? AND 
       removal_time = 0 AND 
       status LIKE '%📅%'
 LIMIT 1;
""",
            params=(chat_id,),
        )
    ]

    now_month = now_time(user_timezone).month
    months = get_translate("months_list", lang)

    month_buttons = []
    for row in months:
        month_buttons.append({})
        for nameM, numm in row:
            tag_today = "#" if numm == now_month else ""
            x = month_list.get(numm)
            tag_event = (
                "".join(
                    calendar_event_count_template[int(ch)] for ch in str(x)
                ) if x < 1000 else "*"
            ) if x else ""
            tag_birthday = "!" if (numm in every_year or every_month) else ""
            month_buttons[-1][
                f"{tag_today}{nameM}{tag_event}{tag_birthday}"
            ] = f"generate calendar days {YY} {numm}"

    return generate_buttons(
        [
            {f"{YY} ({year_info(YY, lang)})": "None"},
            *month_buttons,
            {
                text: f"generate calendar months {year}"
                for text, year in {"<<": YY - 1, "⟳": "now", ">>": YY + 1}.items()
            },
        ]
    )


def edit_button_attrs(
    markup: InlineKeyboardMarkup, row: int, column: int, old: str, new: str, val: str
) -> None:
    button = markup.keyboard[row][column]
    button.__setattr__(old, None)
    button.__setattr__(new, val)


calendar_event_count_template = ("⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹")
backmarkup = generate_buttons([{"🔙": "back"}])
delmarkup = generate_buttons([{"✖": "message_del"}])
delopenmarkup = generate_buttons([{"✖": "message_del", "↖️": "select event open"}])
backopenmarkup = generate_buttons([{"🔙": "back", "↖️": "select event open"}])
