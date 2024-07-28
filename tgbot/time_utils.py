from calendar import isleap

import arrow

from tgbot.request import request
from tgbot.lang import get_translate


def now_time_calendar() -> tuple[int, int]:
    """
    Returns [year, month]
    """
    date = request.entity.now_time()
    return date.year, date.month


def year_info(year: int) -> str:
    """
    String information about the year
    "'month name' ('month number'.'year')('leap year or not' 'animal of this year')"
    """
    result = ""
    if isleap(year):  # year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        result += get_translate("text.leap")
    else:
        result += get_translate("text.not_leap")
    result += " "
    emoji = ("🐀", "🐂", "🐅", "🐇", "🐲", "🐍", "🐴", "🐐", "🐒", "🐓", "🐕", "🐖")
    result += emoji[(year - 4) % 12]
    return result


def get_week_number(year, month, day) -> int:
    """
    Week number by date
    """
    return arrow.get(year, month, day).isocalendar()[1]


def relatively_string_date(day_diff: int) -> tuple[str, str, str]:
    """
    str_date, rel_date, week_date = relatively_string_date(Event(...).days_before_event(timezone))
    # ('April 4', 'Today', 'Thursday')
    """
    (
        today,
        tomorrow,
        day_after_tomorrow,
        yesterday,
        day_before_yesterday,
        after,
        ago,
        func_rel_day,
    ) = get_translate("arrays.relative_date_list")
    week_days = get_translate("arrays.week_days_list_full")
    month_list = get_translate("arrays.months_name2")

    match day_diff:
        case 0:
            rel_date = today
        case 1:
            rel_date = tomorrow
        case 2:
            rel_date = day_after_tomorrow
        case -1:
            rel_date = yesterday
        case -2:
            rel_date = day_before_yesterday
        case n if n > 2:
            rel_date = f"{after} {n} {func_rel_day(n)}"
        case _ as n:
            rel_date = f"{-n} {func_rel_day(n)} {ago}"

    date = request.entity.now_time().shift(days=day_diff)
    str_date = f"{date.day} {month_list[date.month - 1]}"
    week_date = week_days[date.weekday()]
    return str_date, rel_date, week_date


def parse_utc_datetime(
    time: str | None,
    relatively_date: bool = False,
) -> str | tuple[str, str]:
    if time is None:
        return "NEVER"

    time = arrow.get(time).shift(hours=request.entity.settings.timezone)

    if relatively_date:
        n_time = request.entity.now_time()
        rel_date = relatively_string_date((time - n_time).days)[1]
        return f"{time:YYYY.MM.DD HH:mm:ss}", rel_date
    else:
        return f"{time:YYYY.MM.DD HH:mm:ss}"
