from calendar import monthcalendar

# noinspection PyPackageRequirements
from telebot.types import InlineKeyboardMarkup

import config
from tgbot.request import request
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.time_utils import new_time_calendar, year_info, get_week_number
from todoapi.types import db
from todoapi.utils import is_valid_year, chunks, sqlite_format_date
from telegram_utils.buttons_generator import generate_buttons


alphabet = "0123456789aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ"
calendar_event_count_template = ("⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹")


def create_monthly_calendar_keyboard(
    YY_MM: list | tuple[int, int] = None,
    command: str = None,
    back: str = None,
    arguments: str = None,
) -> InlineKeyboardMarkup:
    """
    Создаёт календарь на месяц и возвращает inline клавиатуру
    :param YY_MM: Необязательный аргумент. Если None, то подставит текущую дату.
    :param command: Команда, которую пихать в кнопку + дата
    :param back: Кнопка назад
    :param arguments: Аргументы у команды и back
    """
    command = f"'{command.strip()}'" if command else None
    back = f"'{back.strip()}'" if back else None
    arguments = f"'{arguments.strip()}'" if arguments else None

    if YY_MM:
        YY, MM = YY_MM
    else:
        YY, MM = new_time_calendar()

    # Дни в которые есть события
    has_events = {
        x[0]: x[1]
        for x in db.execute(
            """
-- Дни в которые есть события
SELECT CAST (SUBSTR(date, 1, 2) AS INT) AS day_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND date LIKE :date
 GROUP BY day_number;
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
                "date": f"__.{MM:0>2}.{YY}",
            },
        )
    }

    # Дни рождения, праздники и каждый год или месяц
    every_year_or_month = tuple(
        x[0]
        for x in db.execute(
            """
-- Номера дней дней рождений в конкретном месяце
SELECT DISTINCT CAST (SUBSTR(date, 1, 2) AS INT) 
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id 
       AND removal_time IS NULL
       AND (
           statuses LIKE '%📅%'
           OR (
               (
                   statuses LIKE '%🎉%'
                   OR statuses LIKE '%🎊%'
                   OR statuses LIKE '%📆%'
               )
               AND SUBSTR(date, 4, 2) = :date
           )
       );
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
                "date": f"{MM:0>2}",
            },
        )
    )

    # Каждую неделю
    every_week = tuple(
        6 if x[0] == -1 else x[0]
        for x in db.execute(
            f"""
-- Номер дней недели в которых есть события повторяющиеся каждую неделю события
SELECT DISTINCT CAST (strftime('%w', {sqlite_format_date('date')}) - 1 AS INT) 
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND statuses LIKE '%🗞%';
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
            },
        )
    )

    second_line = [
        {(week_day + ("!" if wd in every_week else "")): "None"}
        for wd, week_day in enumerate(get_translate("arrays.week_days_list"))
    ]

    row_calendar = monthcalendar(YY, MM)
    title = (
        f"{get_translate('arrays.months_name')[MM - 1]} "
        f"({MM}.{YY}) ({year_info(YY)}) "
        f"({get_week_number(YY, MM, 1)}-"
        f"{get_week_number(YY, MM, max(row_calendar[-1]))})"
    )
    first_line = [{title: f"cy ({command},{back},{YY},{arguments})"}]

    buttons_lines = []
    today = request.entity.now_time().day
    for weekcalendar in row_calendar:
        weekbuttons = []
        for wd, day in enumerate(weekcalendar):
            if day == 0:
                weekbuttons.append({"  ": "None"})
            else:
                tag_today = "#" if day == today else ""
                x = has_events.get(day)
                tag_event = (number_to_power(x) if x < 10 else "*") if x else ""
                tag_birthday = "!" if (day in every_year_or_month) else ""
                date = f"{day:0>2}.{MM:0>2}.{YY}"
                weekbuttons.append(
                    {
                        f"{tag_today}{day}{tag_event}{tag_birthday}": (
                            f"{command[1:-1] if command else 'dl'} "
                            + (
                                (
                                    f"{arguments[1:-1].format(date)}"
                                    if "{}" in arguments[1:-1]
                                    else f"{arguments[1:-1]} {date}"
                                )
                                if arguments
                                else date
                            )
                        ).strip()
                    }
                )
        buttons_lines.append(weekbuttons)

    arrows_buttons = [
        {text: f"cm ({command},{back},{data},{arguments})" if data != "None" else data}
        for text, data in {
            "<<": f"({YY - 1},{MM})",
            "<": f"({YY - 1},12)" if MM == 1 else f"({YY},{MM - 1})",
            "⟳": "'now'",
            ">": f"({YY + 1},1)" if MM == 12 else f"({YY},{MM + 1})",
            ">>": f"({YY + 1},{MM})",
        }.items()
    ]

    markup = [
        first_line,
        second_line,
        *buttons_lines,
        arrows_buttons,
        [
            {
                get_theme_emoji("back"): (
                    f"{back[1:-1]}{f' {arguments[1:-1]}' if arguments else ''}"
                )
            }
        ]
        if back
        else [],
    ]

    return generate_buttons(markup)


def create_yearly_calendar_keyboard(
    YY: int,
    command: str = None,
    back: str = None,
    arguments: str = None,
) -> InlineKeyboardMarkup:
    """
    Создаёт календарь из месяцев на определённый год и возвращает inline клавиатуру
    """
    command = f"'{command.strip()}'" if command else None
    back = f"'{back.strip()}'" if back else None
    arguments = f"'{arguments.strip()}'" if arguments else None

    # В этом году
    month_list = {
        x[0]: x[1]
        for x in db.execute(
            """
-- Месяцы в которых есть события
SELECT CAST (SUBSTR(date, 4, 2) AS INT) AS month_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND date LIKE :date
 GROUP BY month_number;
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
                "date": f"__.__.{YY}",
            },
        )
    }

    # Повторение каждый год
    every_year = [
        x[0]
        for x in db.execute(
            """
-- Номера месяцев дней рождений в конкретном месяце
SELECT DISTINCT CAST (SUBSTR(date, 4, 2) AS INT) 
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND (
           statuses LIKE '%🎉%'
           OR statuses LIKE '%🎊%'
           OR statuses LIKE '%📆%'
       );
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
            },
        )
    ]

    # Повторение каждый месяц
    every_month = [
        x[0]
        for x in db.execute(
            """
-- Есть ли событие, которое повторяется каждый месяц
SELECT date
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND statuses LIKE '%📅%'
 LIMIT 1;
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
            },
        )
    ]

    now_month = request.entity.now_time().month

    month_buttons = []
    for row in get_translate("arrays.months_list"):
        month_buttons.append([])
        for nameM, numm in row:
            tag_today = "#" if numm == now_month else ""
            x = month_list.get(numm)
            tag_event = (number_to_power(x) if x < 1000 else "*") if x else ""
            tag_birthday = "!" if (numm in every_year or every_month) else ""
            month_buttons[-1].append(
                {
                    f"{tag_today}{nameM}{tag_event}{tag_birthday}": (
                        f"cm ({command},{back},({YY},{numm}),{arguments})"
                    )
                }
            )

    markup = [
        [
            {
                f"{YY} ({year_info(YY)})": f"ct ({command},{back},{str(YY)[:3]},{arguments})"
            }
        ],
        *month_buttons,
        [
            {text: f"cy ({command},{back},{year},{arguments})"}
            for text, year in {"<<": YY - 1, "⟳": "'now'", ">>": YY + 1}.items()
        ],
        [
            {
                get_theme_emoji("back"): (
                    f"{back[1:-1]}" f"{f' {arguments[1:-1]}' if arguments else ''}"
                )
            }
        ]
        if back
        else [],
    ]

    return generate_buttons(markup)


def create_twenty_year_calendar_keyboard(
    decade: int,
    command: str = None,
    back: str = None,
    arguments: str = None,
) -> InlineKeyboardMarkup:
    command = f"'{command.strip()}'" if command else None
    back = f"'{back.strip()}'" if back else None
    arguments = f"'{arguments.strip()}'" if arguments else None
    # example: millennium, decade =  '20', 2
    millennium, decade = str(decade)[:2], int(str(decade)[2])
    decade = (decade - 1) if decade % 2 else decade

    decade -= decade % 2  # if decade % 2: decade -= 1

    now_year = request.entity.now_time().year
    year = int(f"{millennium}{decade}0")
    years = chunks([(n, y) for n, y in enumerate(range(year, year + 20))], 4)

    # В этом году
    year_list = {
        x[0]: x[1]
        for x in db.execute(
            """
-- Года в которых есть события
SELECT CAST (SUBSTR(date, 7, 4) AS INT) AS year_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
 GROUP BY year_number;
""",
            params={
                "user_id": request.entity.safe_user_id,
                "group_id": request.entity.group_id,
            },
        )
    }

    # Повторение каждый год
    every_year = db.execute(
        """
-- Номера месяцев дней рождений в конкретном месяце
SELECT 1
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND removal_time IS NULL
       AND (
           statuses LIKE '%🎉%'
           OR statuses LIKE '%🎊%'
           OR statuses LIKE '%📆%'
       );
""",
        params={
            "user_id": request.entity.safe_user_id,
            "group_id": request.entity.group_id,
        },
    )

    if every_year:
        every_year = every_year[0]

    years_buttons = []
    for row in years:
        years_buttons.append([])
        for nameM, numY in row:
            if not is_valid_year(numY):
                years_buttons[-1].append({" " * (int(str(numY)[-1]) or 11): "None"})
                continue

            tag_today = "#" if numY == now_year else ""
            x = year_list.get(numY)
            tag_event = (number_to_power(x) if x < 1000 else "*") if x else ""
            tag_birthday = "!" if every_year else ""
            years_buttons[-1].append(
                {
                    f"{tag_today}{numY}{tag_event}{tag_birthday}": (
                        f"cy ({command},{back},{numY},{arguments})"
                    )
                }
            )

    markup = generate_buttons(
        [
            *years_buttons,
            [
                {text: f"ct ({command},{back},{year},{arguments})"}
                for text, year in {
                    "<<": str(int(f"{millennium}{decade}") - 2)[:3],
                    "⟳": "'now'",
                    ">>": str(int(f"{millennium}{decade}") + 2)[:3],
                }.items()
            ],
            [
                {
                    get_theme_emoji("back"): (
                        f"{back[1:-1]}{f' {arguments[1:-1]}' if arguments else ''}"
                    )
                }
            ]
            if back
            else [],
        ]
    )

    return markup


def create_select_status_keyboard(
    prefix: str,
    status_list: list[str],
    folder_path: str,
    save: str,
    back: str,
    arguments: str = "",
) -> InlineKeyboardMarkup:
    """

    :param prefix:
    :param status_list:
    :param folder_path:
    :param save:
    :param back:
    :param arguments:
    :return:
    """
    status_list = status_list[-5:]

    def join(lst) -> str:
        return ",".join(lst)

    string_statuses = join(status_list)

    if folder_path == "folders":
        buttons_data: tuple[tuple[tuple[str]]] = get_translate(
            "buttons.select_status.folders"
        )
        markup = generate_buttons(
            [
                *[
                    [
                        {
                            f"{title:{config.ts}<80}": f"{prefix} {string_statuses} {folder} {arguments}"
                        }
                        for (title, folder) in row
                    ]
                    for row in buttons_data
                ],
                [
                    {
                        (rm_status if rm_status else " "): (
                            f"{prefix} {join(filter(lambda x: x != rm_status, status_list)) or '⬜'} folders {arguments}"
                            if rm_status
                            else "None"
                        )
                    }
                    for rm_status in status_list + [""] * (5 - len(status_list))
                ]
                if status_list != ["⬜"]
                else ({" ": "None"},) * 5,
                [
                    {get_theme_emoji("back"): f"{back} {arguments}"},
                    {"💾": f"{save} {arguments} {string_statuses}"},
                ],
            ]
        )
    else:
        buttons_data: tuple[tuple[str]] = get_translate(
            f"buttons.select_status.{folder_path}"
        )
        markup = generate_buttons(
            [
                *[
                    [
                        {
                            f"{row:{config.ts}<80}": (
                                (
                                    f"{prefix} {string_statuses},{row.split(maxsplit=1)[0]} folders {arguments}"
                                    if "⬜" not in status_list
                                    else f"{prefix} {row.split(maxsplit=1)[0]} folders {arguments}"
                                )
                                if row.split(maxsplit=1)[0] != "⬜"
                                else f"{prefix} ⬜ folders {arguments}"
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
                        ): f"{prefix} {string_statuses} folders {arguments}"
                    }
                ],
            ]
        )

    return markup


def edit_button_attrs(
    markup: InlineKeyboardMarkup, row: int, column: int, old: str, new: str, val: str
) -> None:
    button = markup.keyboard[row][column]
    setattr(button, old, None)
    setattr(button, new, val)


def delmarkup() -> InlineKeyboardMarkup:
    return generate_buttons([[{get_theme_emoji("del"): "md"}]])


def number_to_power(string: str) -> str:
    """
    Превратит строку чисел в строку степеней.
    Например "123" в "¹²³".
    """
    return "".join(calendar_event_count_template[int(ch)] for ch in str(string))


def exel_str_int(excel_string: str) -> int:
    return sum(
        (alphabet.index(char) + 1) * len(alphabet) ** i
        for i, char in enumerate(reversed(excel_string))
    )


def int_str_exel(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, len(alphabet))
        result = alphabet[remainder] + result
    return result


def decode_id(input_ids: str) -> list[int]:
    """
    >>> decode_id("0,,,,,,,")
    [1, 2, 3, 4, 5, 6, 7, 8]
    >>> decode_id("0,,3,5,7")
    [1, 2, 4, 6, 8]
    >>> decode_id("0,,3,5,7,")
    [1, 2, 4, 6, 8, 9]
    """

    if (not input_ids) or input_ids == "_":
        return []

    result = []
    ids: list[int | Ellipsis] = [
        exel_str_int(i) if i else ... for i in input_ids.split(",")
    ]
    current_number = ids[0]

    if current_number is ...:
        raise ValueError("...")

    for char in ids:
        if char is ...:
            current_number += 1
        else:
            current_number = char
        result.append(current_number)
    return result


def encode_id(ids: tuple[int] | list[int]) -> str:
    """
    >>> encode_id([1, 2, 3, 4, 5, 6, 7, 8])
    '0,,,,,,,'
    >>> encode_id([1, 2, 4, 6, 8])
    '0,,3,5,7'
    >>> encode_id([8, 6, 7, 5, 4, 3, 2, 1])
    '7,5,,4,3,2,1,0'
    >>> encode_id([1, 2, 4, 6, 8, 6, 4, 2, 1])
    '0,,3,5,7,5,3,1,0'
    """

    result = []
    for n, i in enumerate(ids):
        abbreviated_int = int_str_exel(i)
        if n == 0:
            data = abbreviated_int
        else:
            diff = i - ids[n - 1]
            if diff == 1:
                data = ","
            else:
                data = f",{abbreviated_int}"
        result.append(data)

    return "".join(result) or "_"
