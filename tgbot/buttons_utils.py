from calendar import monthcalendar

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from tgbot.queries import queries
from tgbot.request import request
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.time_utils import new_time_calendar, year_info, now_time, get_week_number
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
    YY_MM: list | tuple[int, int] = None,
    command: str | None = None,
    back: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Создаёт календарь на месяц и возвращает inline клавиатуру
    param YY_MM: Необязательный аргумент. Если None, то подставит текущую дату.
    """
    settings, chat_id = request.user.settings, request.chat_id
    command = f"'{command.strip()}'" if command else None
    back = f"'{back.strip()}'" if back else None

    if YY_MM:
        YY, MM = YY_MM
    else:
        YY, MM = new_time_calendar()

    row_calendar = monthcalendar(YY, MM)
    markup = InlineKeyboardMarkup()
    #  December (12.2022)
    # Пн Вт Ср Чт Пт Сб Вс
    title = (
        f"{get_translate('months_name')[MM - 1]} "
        f"({MM}.{YY}) "
        f"({year_info(YY)}) "
        f"({get_week_number(YY, MM, 1)}-"
        f"{get_week_number(YY, MM, max(row_calendar[-1]))})"
    )
    markup.row(
        InlineKeyboardButton(
            text=title, callback_data=f"calendar_y ({command},{back},{YY})"
        )
    )
    markup.row(
        *[
            InlineKeyboardButton(text=week_day, callback_data="None")
            for week_day in get_translate("week_days_list")
        ]
    )

    # Дни в которые есть события
    has_events = {
        x[0]: x[1]
        for x in db.execute(
            queries["select day_number_with_events"],
            params=(chat_id, f"__.{MM:0>2}.{YY}"),
        )
    }

    # Дни рождения, праздники и каждый год или месяц
    every_year_or_month = [
        x[0]
        for x in db.execute(
            queries["select day_number_with_birthdays"],
            params=(chat_id, f"{MM:0>2}"),
        )
    ]

    # Каждую неделю
    every_week = [
        6 if x[0] == -1 else x[0]
        for x in db.execute(
            queries["select week_day_number_with_event_every_week"],
            params=(chat_id,),
        )
    ]

    # получаем сегодняшнее число
    today = now_time().day
    # получаем список дней
    for weekcalendar in row_calendar:
        weekbuttons = []
        for wd, day in enumerate(weekcalendar):
            if day == 0:
                weekbuttons.append(InlineKeyboardButton("  ", callback_data="None"))
            else:
                tag_today = "#" if day == today else ""
                x = has_events.get(day)
                tag_event = (number_to_power(x) if x < 10 else "*") if x else ""
                tag_birthday = (
                    "!" if (day in every_year_or_month or wd in every_week) else ""
                )
                weekbuttons.append(
                    InlineKeyboardButton(
                        f"{tag_today}{day}{tag_event}{tag_birthday}",
                        callback_data=f"{command[1:-1] if command else ''} {day:0>2}.{MM:0>2}.{YY}".strip(),
                    )
                )
        markup.row(*weekbuttons)

    markup.row(
        *[
            InlineKeyboardButton(
                f"{text}", callback_data=f"calendar_m ({command},{back},{data})"
            )
            for text, data in {
                "<<": f"({YY - 1},{MM})",
                "<": f"({YY - 1},12)" if MM == 1 else f"({YY},{MM - 1})",
                "⟳": "'now'",
                ">": f"({YY + 1},1)" if MM == 12 else f"({YY},{MM + 1})",
                ">>": f"({YY + 1},{MM})",
            }.items()
        ]
    )

    if back:
        markup.row(
            InlineKeyboardButton(get_theme_emoji("back"), callback_data=back[1:-1])
        )

    return markup


def create_yearly_calendar_keyboard(
    YY: int,
    command: str | None = None,
    back: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Создаёт календарь из месяцев на определённый год и возвращает inline клавиатуру
    """
    chat_id = request.chat_id
    command = f"'{command.strip()}'" if command else None
    back = f"'{back.strip()}'" if back else None

    # В этом году
    month_list = {
        x[0]: x[1]
        for x in db.execute(
            queries["select month_number_with_events"],
            params=(chat_id, f"__.__.{YY}"),
        )
    }

    # Повторение каждый год
    every_year = [
        x[0]
        for x in db.execute(
            queries["select month_number_with_birthdays"],
            params=(chat_id,),
        )
    ]

    # Повторение каждый месяц
    every_month = [
        x[0]
        for x in db.execute(
            queries["select having_event_every_month"],
            params=(chat_id,),
        )
    ]

    now_month = now_time().month
    months = get_translate("months_list")

    month_buttons = []
    for row in months:
        month_buttons.append({})
        for nameM, numm in row:
            tag_today = "#" if numm == now_month else ""
            x = month_list.get(numm)
            tag_event = (number_to_power(x) if x < 1000 else "*") if x else ""
            tag_birthday = "!" if (numm in every_year or every_month) else ""
            month_buttons[-1][
                f"{tag_today}{nameM}{tag_event}{tag_birthday}"
            ] = f"calendar_m ({command},{back},({YY},{numm}))"

    markup = generate_buttons(
        [
            {f"{YY} ({year_info(YY)})": "None"},
            *month_buttons,
            {
                text: f"calendar_y ({command},{back},{year})"
                for text, year in {"<<": YY - 1, "⟳": "'now'", ">>": YY + 1}.items()
            },
        ]
    )

    if back:
        markup.row(
            InlineKeyboardButton(get_theme_emoji("back"), callback_data=back[1:-1])
        )

    return markup


def edit_button_attrs(
    markup: InlineKeyboardMarkup, row: int, column: int, old: str, new: str, val: str
) -> None:
    button = markup.keyboard[row][column]
    button.__setattr__(old, None)
    button.__setattr__(new, val)


def delmarkup() -> InlineKeyboardMarkup:
    return generate_buttons([{get_theme_emoji("del"): "message_del"}])


def number_to_power(string: str) -> str:
    """
    Превратит строку чисел в строку степеней.
    Например "123" в "¹²³".
    """
    return "".join(calendar_event_count_template[int(ch)] for ch in str(string))


calendar_event_count_template = ("⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹")
