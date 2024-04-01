from calendar import isleap
from datetime import datetime, timedelta

from tgbot.request import request
from tgbot.lang import get_translate


def now_time_strftime() -> str:
    """
    Возвращает форматированную ("%d.%m.%Y") функцию now_time()
    """
    return request.entity.now_time().strftime("%d.%m.%Y")


def new_time_calendar() -> tuple[int, int]:
    """
    Возвращает [год, месяц]
    """
    date = request.entity.now_time()
    return date.year, date.month


def convert_date_format(date: str) -> datetime:
    """
    Принимает дату в формате dd.mm.yyyy
    Возвращает datetime(year=yyyy, month=mm, day=dd)
    """
    day, month, year = [int(x) for x in date.split(".")]
    try:
        return datetime(year, month, day)
    except ValueError as e:
        # Если дата 29 февраля и год невисокосный, то возвращать 1 апреля.
        if (
            f"{e}" == "day is out of range for month"
            and (month, day) == (2, 29)
            and not isleap(year)
        ):
            return datetime(year, 3, 1)
        else:
            raise e


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


class DayInfo:
    """
    Информация о дне
    self.date            "переданная дата"
    self.str_date        "число название месяца"
    self.week_date       "день недели"
    self.relatively_date "через x дней" или "x дней назад"
    """

    def __init__(self, date: str):
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
        x = request.entity.now_time()
        x = datetime(x.year, x.month, x.day)
        y = convert_date_format(date)

        self.datetime = y
        self.day_diff = (y - x).days
        match self.day_diff:
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

        week_days = get_translate("arrays.week_days_list_full")
        month_list = get_translate("arrays.months_name2")

        self.date = date
        self.str_date = f"{y.day} {month_list[y.month - 1]}"
        self.week_date = week_days[y.weekday()]


def parse_utc_datetime(time: str | None, relatively_date: bool = False) -> str:
    if time is None:
        return "NEVER"

    time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
    time += timedelta(hours=request.entity.settings.timezone)
    rel_date = (
        " ({})".format(DayInfo(f"{time:%d.%m.%Y}").relatively_date)
        if relatively_date
        else ""
    )
    return f"{time:%Y.%m.%d %H:%M:%S}" + rel_date
