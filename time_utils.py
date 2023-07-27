from calendar import isleap
from datetime import datetime, timedelta

import config
from lang import get_translate
from user_settings import UserSettings


def now_time(user_timezone: int = 0) -> datetime:
    """
    Возвращает datetime.utcnow() с учётом часового пояса пользователя
    """
    return datetime.utcnow() + timedelta(hours=user_timezone)


def now_time_strftime(user_timezone: int) -> str:
    """
    Возвращает форматированную ("%d.%m.%Y") функцию now_time()
    """
    return now_time(user_timezone).strftime("%d.%m.%Y")


def log_time_strftime(log_timezone: int = config.hours_difference) -> str:
    """
    Возвращает форматированную ("%Y.%m.%d %H:%M:%S") функцию now_time()
    Для логов
    """
    return (now_time(log_timezone)).strftime("%Y.%m.%d %H:%M:%S")


def new_time_calendar(user_timezone: int) -> tuple[int, int]:
    """
    Возвращает [год, месяц]
    """
    date = now_time(user_timezone)
    return date.year, date.month


def convert_date_format(date: str) -> datetime:
    """
    Принимает дату в формате dd.mm.yyyy
    Возвращает datetime(year=yyyy, month=mm, day=dd)
    """
    return datetime(*[int(x) for x in date.split(".")][::-1])


def year_info(year: int, lang: str) -> str:
    """
    Строковая информация про год
    "'имя месяца' ('номер месяца'.'год')('високосный или нет' 'животное этого года')"
    """
    result = ""
    if isleap(year):  # year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        result += get_translate("leap", lang)
    else:
        result += get_translate("not_leap", lang)
    result += " "
    result += ("🐀", "🐂", "🐅", "🐇", "🐲", "🐍", "🐴", "🐐", "🐒", "🐓", "🐕", "🐖")[
        (year - 4) % 12
    ]
    return result


def get_week_number(YY, MM, DD) -> int:  # TODO добавить номер недели в календари
    """
    Номер недели по дате
    """
    return datetime(YY, MM, DD).isocalendar()[1]


class DayInfo:
    """
    Информация о дне
    self.date            "переданная дата"
    self.str_date        "число название месяца"
    self.week_date       "день недели"
    self.relatively_date "через x дней" или "x дней назад"
    """

    def __init__(self, settings: UserSettings, date: str):
        (
            today,
            tomorrow,
            day_after_tomorrow,
            yesterday,
            day_before_yesterday,
            after,
            ago,
            Fday,
        ) = get_translate("relative_date_list", settings.lang)
        x = now_time(settings.timezone)
        x = datetime(x.year, x.month, x.day)
        y = convert_date_format(date)

        day_diff = (y - x).days
        match day_diff:
            case 0:
                self.relatively_date = f"{today}"
            case 1:
                self.relatively_date = f"{tomorrow}"
            case 2:
                self.relatively_date = f"{day_after_tomorrow}"
            case -1:
                self.relatively_date = f"{yesterday}"
            case -2:
                self.relatively_date = f"{day_before_yesterday}"
            case n if n > 2:
                self.relatively_date = f"{after} {n} {Fday(n)}"
            case _ as n:
                self.relatively_date = f"{-n} {Fday(n)} {ago}"

        week_days = get_translate("week_days_list_full", settings.lang)
        month_list = get_translate("months_name2", settings.lang)

        self.date = date
        self.str_date = f"{y.day} {month_list[y.month - 1]}"
        self.week_date = week_days[y.weekday()]
