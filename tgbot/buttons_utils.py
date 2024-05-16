from calendar import monthcalendar

# noinspection PyPackageRequirements
from telebot.types import InlineKeyboardMarkup

import config
from tgbot.request import request
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.time_utils import now_time_calendar, year_info, get_week_number
from todoapi.types import db
from todoapi.utils import is_valid_year, chunks, sqlite_format_date
from telegram_utils.buttons_generator import generate_buttons


alphabet = "0123456789aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ"
calendar_event_count_template = ("⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹")


def create_monthly_calendar_keyboard(
    year_month: list | tuple[int, int] = None,
    command: str = None,
    back: str = None,
    arguments: str = None,
) -> InlineKeyboardMarkup:
    """
    Creates a monthly calendar and returns an inline keyboard
    :param year_month: Optional argument. If None, then it will substitute the current date.
    :param command: The command to push into the button + date
    :param back: Back button
    :param arguments: Arguments for the command and back
    """
    command = f"'{command.strip()}'" if command else None
    back = f"'{back.strip()}'" if back else None
    arguments = f"'{arguments.strip()}'" if arguments else None

    if year_month:
        year, month = year_month
    else:
        year, month = now_time_calendar()

    # Days with events
    has_events = {
        x[0]: x[1]
        for x in db.execute(
            """
-- Days with events
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
                "date": f"__.{month:0>2}.{year}",
            },
        )
    }

    # Birthdays, holidays and every year or month
    every_year_or_month = tuple(
        x[0]
        for x in db.execute(
            """
-- Numbers of birthdays in a specific month
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
                "date": f"{month:0>2}",
            },
        )
    )

    # Every week
    every_week = tuple(
        6 if x[0] == -1 else x[0]
        for x in db.execute(
            f"""
-- Number of days of the week in which there are events that repeat every week
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

    row_calendar = monthcalendar(year, month)
    title = (
        f"{get_translate('arrays.months_name')[month - 1]} "
        f"({month}.{year}) ({year_info(year)}) "
        f"({get_week_number(year, month, 1)}-"
        f"{get_week_number(year, month, max(row_calendar[-1]))})"
    )
    first_line = [{title: f"cy ({command},{back},{year},{arguments})"}]

    buttons_lines = []
    today = request.entity.now_time().day
    for week_calendar in row_calendar:
        week_buttons = []
        for wd, day in enumerate(week_calendar):
            if day == 0:
                week_buttons.append({"  ": "None"})
            else:
                tag_today = "#" if day == today else ""
                x = has_events.get(day)
                tag_event = (number_to_power(x) if x < 10 else "*") if x else ""
                tag_birthday = "!" if (day in every_year_or_month) else ""
                date = f"{day:0>2}.{month:0>2}.{year}"
                week_buttons.append(
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
        buttons_lines.append(week_buttons)

    arrows_buttons = [
        {text: f"cm ({command},{back},{data},{arguments})" if data != "None" else data}
        for text, data in {
            "<<": f"({year - 1},{month})",
            "<": f"({year - 1},12)" if month == 1 else f"({year},{month - 1})",
            "⟳": "'now'",
            ">": f"({year + 1},1)" if month == 12 else f"({year},{month + 1})",
            ">>": f"({year + 1},{month})",
        }.items()
    ]

    markup = [
        first_line,
        second_line,
        *buttons_lines,
        arrows_buttons,
        (
            [
                {
                    get_theme_emoji("back"): (
                        f"{back[1:-1]}{f' {arguments[1:-1]}' if arguments else ''}"
                    )
                }
            ]
            if back
            else []
        ),
    ]

    return generate_buttons(markup)


def create_yearly_calendar_keyboard(
    year: int,
    command: str = None,
    back: str = None,
    arguments: str = None,
) -> InlineKeyboardMarkup:
    """
    Creates a calendar of months for a specific year and returns an inline keyboard
    """
    command = f"'{command.strip()}'" if command else None
    back = f"'{back.strip()}'" if back else None
    arguments = f"'{arguments.strip()}'" if arguments else None

    # This year
    month_list = {
        x[0]: x[1]
        for x in db.execute(
            """
-- Months with events
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
                "date": f"__.__.{year}",
            },
        )
    }

    # Repeat every year
    every_year = [
        x[0]
        for x in db.execute(
            """
-- Month numbers of birthdays in a specific month
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

    # Repeat every month
    every_month = [
        x[0]
        for x in db.execute(
            """
-- Is there an event that repeats every month?
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
                        f"cm ({command},{back},({year},{numm}),{arguments})"
                    )
                }
            )

    markup = [
        [
            {
                f"{year} ({year_info(year)})": f"ct ({command},{back},{str(year)[:3]},{arguments})"
            }
        ],
        *month_buttons,
        [
            {text: f"cy ({command},{back},{y},{arguments})"}
            for text, y in {"<<": year - 1, "⟳": "'now'", ">>": year + 1}.items()
        ],
        (
            [
                {
                    get_theme_emoji("back"): (
                        f"{back[1:-1]}" f"{f' {arguments[1:-1]}' if arguments else ''}"
                    )
                }
            ]
            if back
            else []
        ),
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

    # This year
    year_list = {
        x[0]: x[1]
        for x in db.execute(
            """
-- Years with events
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

    # Repeat every year
    every_year = db.execute(
        """
-- Month numbers of birthdays in a specific month
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
                (
                    {
                        get_theme_emoji("back"): (
                            f"{back[1:-1]}{f' {arguments[1:-1]}' if arguments else ''}"
                        )
                    }
                    if back
                    else {}
                )
            ],
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
                (
                    [
                        {
                            (rm_status if rm_status else " "): (
                                f"{prefix} {join(filter(lambda x: x != rm_status, status_list)) or '⬜'} "
                                f"folders {arguments}"
                                if rm_status
                                else "None"
                            )
                        }
                        for rm_status in status_list + [""] * (5 - len(status_list))
                    ]
                    if status_list != ["⬜"]
                    else ({" ": "None"},) * 5
                ),
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

        def unique_string_statuses(row) -> str:
            new_status = row.split(maxsplit=1)[0]

            if new_status == "⬜":
                return f"{prefix} ⬜ folders {arguments}"

            if "⬜" in status_list:
                return f"{prefix} {new_status} folders {arguments}"

            # if new_status in status_list:
            #     return "raise Error"

            res_status = ",".join(list(dict.fromkeys(status_list + [new_status])))
            return f"{prefix} {res_status} folders {arguments}"

        markup = generate_buttons(
            [
                *[
                    [
                        {f"{row:{config.ts}<80}": unique_string_statuses(row)}
                        for row in status_column
                    ]
                    for status_column in buttons_data
                ],
                [
                    {
                        get_theme_emoji("back"): (
                            f"{prefix} {string_statuses} folders {arguments}"
                        )
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
    Turns a string of numbers into a string of powers.
    For example "123" in "¹²³".
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
