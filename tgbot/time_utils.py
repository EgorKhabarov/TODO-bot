from calendar import isleap
from datetime import datetime, timedelta

from tgbot.request import request
from tgbot.lang import get_translate


def new_time_calendar() -> tuple[int, int]:
    """
    Возвращает [год, месяц]
    """
    date = request.entity.now_time()
    return date.year, date.month


def year_info(year: int) -> str:
    """
    Строковая информация про год
    "'имя месяца' ('номер месяца'.'год')('високосный или нет' 'животное этого года')"
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


def get_week_number(YY, MM, DD) -> int:
    """
    Номер недели по дате
    """
    return datetime(YY, MM, DD).isocalendar()[1]


def relatively_string_date(day_diff: int) -> tuple[str, str, str]:
    """
    str_date, rel_date, week_date = relatively_string_date(Event(...).days_before_event(timezone))
    # ('4 Апреля', 'Сегодня', 'Четверг')
    """
    (
        today,
        tomorrow,
        day_after_tomorrow,
        yesterday,
        day_before_yesterday,
        after,
        ago,
        Fday,
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
            rel_date = f"{after} {n} {Fday(n)}"
        case _ as n:
            rel_date = f"{-n} {Fday(n)} {ago}"

    date = request.entity.now_time() + timedelta(days=day_diff)
    str_date = f"{date.day} {month_list[date.month - 1]}"
    week_date = week_days[date.weekday()]
    return str_date, rel_date, week_date


def parse_utc_datetime(time: str | None, relatively_date: bool = False) -> str:
    if time is None:
        return "NEVER"

    n_time = request.entity.now_time()
    time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
    time += timedelta(hours=request.entity.settings.timezone)
    rel_date = (
        " ({})".format(relatively_string_date((time - n_time).days)[1])
        if relatively_date
        else ""
    )
    return f"{time:%Y.%m.%d %H:%M:%S}" + rel_date
