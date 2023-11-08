import re
import html
import difflib
import logging
from time import time
from io import StringIO
from typing import Literal
from functools import wraps
from urllib.parse import urlparse
from textwrap import wrap as textwrap
from datetime import timedelta, datetime, timezone

import requests
from requests import ConnectionError
from requests.exceptions import MissingSchema
from telebot.apihelper import ApiTelegramException
from telebot.types import Message

from tgbot import config
from tgbot.bot import bot
from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.time_utils import DayInfo, convert_date_format, now_time
from todoapi.types import db, Event
from todoapi.utils import is_admin_id, isdigit

re_edit_message = re.compile(r"\A@\w{5,32} event\((\d+), (\d+)\)\.text(?:\n|\Z)")
msg_check = re.compile(
    rf"""(?xs)
\A
/                               # Команда
\w+                             # Текст команды
(@{re.escape(bot.username)}\b)? # Необязательный username бота
(\s|$)                          # Пробел или окончание строки
.*                              # Необязательные аргументы команды
\Z
"""
)
re_call_data_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}\Z")
re_setuserstatus = re.compile(r"\A(-?\d+) (-1|0|1|2)\Z")


def markdown(text: str, statuses: str) -> str:
    """
    Добавляем эффекты к событию по статусу
    """

    def check_comment_in_status(comment_string: Literal["##", "//", "--"]) -> bool:
        """
        Проверить будет ли этот символ комментария считаться за комментарий при выбранных языках.
        """
        status_set = {
            s.removeprefix("💻")
            for s in statuses_list
            if s.startswith("💻")
        }

        if comment_string == "##":
            return not status_set.isdisjoint({"py", "re"})
        elif comment_string == "//":
            return not status_set.isdisjoint({"cpp", "c"})
        elif comment_string == "--":
            return not status_set.isdisjoint({"sql"})
        else:
            return False

    def is_comment_line(line: str) -> bool:
        """
        Проверяет строку на комментарий для списков ("🗒") и сортированный список ("🧮").
        Комментарий не будет работать если в статусе стоит язык, в котором это часть синтаксиса.
        """
        return line == "⠀" or (
            line.startswith("— ")
            or (line.startswith("-- ") and not check_comment_in_status("--"))
            or (line.startswith("## ") and not check_comment_in_status("##"))
            or (line.startswith("// ") and not check_comment_in_status("//"))
        )

    def remove_comment_prefix(line: str) -> str:
        """
        Удаляет префикс комментария.
        В зависимости от наличия комментария удаляет
        """
        line = line.removeprefix("— ")

        if not check_comment_in_status("--"):
            line = line.removeprefix("-- ")
        if not check_comment_in_status("##"):
            line = line.removeprefix("## ")
        if not check_comment_in_status("//"):
            line = line.removeprefix("// ")
        return line


    def format_order_list(_text: str, num=0) -> str:  # Нумерует каждую строчку
        lst = _text.splitlines()

        # Получаем длину отступа чтобы не съезжало
        width = len(
            str(
                len(
                    tuple(
                        line
                        for line in lst
                        if not is_comment_line(line)
                    )
                )
            )
        )

        # Заполняем с отступами числа + текст, а если двойной перенос строки то "⠀"
        return "\n".join(
            (
                (
                    "0️⃣" * (width - len(str(num := num + 1)))
                )  # Ставим нули перед основным числом
                + "⃣".join(str(num))  # Само число
                + "⃣"
                + line
                if not is_comment_line(line)
                else remove_comment_prefix(line)
            )
            if line not in ("", "⠀")
            else "⠀"
            for line in lst
        )

    def format_list(_text: str):
        """Заменяет \n на :black_small_square: (эмодзи Telegram)"""
        point = "▫️" if request.user.settings.theme == 1 else "▪️"
        big_point = "◻️" if request.user.settings.theme == 1 else "◼️"
        lst = _text.splitlines()

        return "\n".join(
            (
                (
                    (big_point if line.startswith("!!") else point) + line.removeprefix("!!")
                )
                if not is_comment_line(line)
                else remove_comment_prefix(line)
            )
            if line not in ("", "⠀")
            else "⠀"
            for line in lst
        )

    def format_spoiler(spoiler: str):
        return f"<span class='tg-spoiler'>{spoiler}</span>"

    def sub_urls(_text: str):
        def la(m: re.Match):
            url = re.sub(r"\Ahttp://", "https://", m[0])

            if re.search(r"https://t\.me/\w{5,32}", url):
                # Если это ссылка на пользователя
                return f"<a href='{url}'>@{url.removeprefix('https://t.me/')}</a>"

            return f"<a href='{url}'>{urlparse(url).netloc}</a>"

        return re.sub(r"(http?s?://[^\"\'\n ]+)", la, _text)  # r"(http?s?://\S+)"

    def format_code(code: str):
        return f"<pre>{code}</pre>"

    def format_code_lang(code: str, lang: str) -> str:
        return f"<pre><code class='language-{lang}'>{code}</code></pre>"

    text = html.escape(text)

    # Сокращаем несколько подряд переносов строки
    text = re.sub(r"\n(\n*)\n", "\n⠀\n", text)  # Прозрачный символ chr(10240)

    if ("🔗" in statuses and "⛓" not in statuses) or (
        request.user.settings.sub_urls and ("💻" not in statuses and "⛓" not in statuses)
    ):
        text = sub_urls(text)

    statuses_list: list[str] = statuses.split(",")

    if "🗒" in statuses_list:
        text = format_list(text)
    elif "🧮" in statuses_list:
        text = format_order_list(text)

    if "💻" in statuses:
        status = [
            status.removeprefix("💻")
            for status in statuses_list
            if status.startswith("💻")
        ][-1]
        text = format_code_lang(text, status) if status else format_code(text)
    elif "🪞" in statuses_list:
        text = format_spoiler(text)

    return text


def rate_limit_requests(
    requests_count: int = 3,
    time_sec: int = 60,
    key_path: int | str | tuple[str | int] | set[str | int] = None,
    translate_key: str = "errors.many_attempts",
    send: bool = False,
):
    """
    Возвращает текст ошибки,
    если пользователи вызывали функцию чаще чем 3 раза в 60 секунд.
    """

    def get_key(
        _args: tuple,
        _kwargs: dict,
        path: int | str | tuple[str | int] | list[str | int] = None,
    ):
        if path is None:
            path = key_path

        if isinstance(path, int):
            return _args[path]
        elif isinstance(path, str):
            result = None
            for i, a in enumerate(path.split(".")):
                a: str
                if i == 0:
                    result = _kwargs.get(a) or _args[0]
                else:
                    result = result[int(a)] if isdigit(a) else getattr(result, a)
            return result

        elif isinstance(path, (tuple, list)):
            return tuple(get_key(_args, _kwargs, key) for key in path)
        elif isinstance(path, set):
            keys = []
            for key in path:
                try:
                    x = get_key(_args, _kwargs, key)
                    keys.append(x)
                except AttributeError:
                    pass

            return " ".join(f"{key}" for key in keys)

    def decorator(func):
        cache = [] if key_path is None else {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time()
            key = get_key(args, kwargs)

            if key not in cache and key_path is not None:
                cache[key] = []

            _cache = cache if key_path is None else cache[key]
            _cache[:] = [call for call in _cache if now - call < time_sec]

            if len(_cache) >= requests_count:
                wait_time = time_sec - int(now - _cache[0])

                raw_text: str = get_translate(translate_key)
                text = raw_text.format(wait_time)
                if send:
                    try:
                        return bot.send_message(key, text)
                    except ApiTelegramException:
                        return
                else:
                    return text

            _cache.append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def cache_with_ttl(cache_time_sec: int = 60):
    """
    Кеширует значение функции подобно functools.cache,
    но держит значение не больше cache_time_sec.
    Не даёт запрашивать новый результат функции
    с одним и тем же аргументом чаще чем в cache_time_sec секунды.
    """

    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(city: str):
            key = f"{city} {request.user.settings.lang}"
            now = time()
            if key not in cache or now - cache[key][1] > cache_time_sec:
                cache[key] = (func(city), now)
            return cache[key][0]

        return wrapper

    return decorator


# TODO добавить персональные api ключи для запрашивания погоды
# TODO декоратор для проверки api ключа у пользователя
# TODO в зависимости от наличия ключа ставить разные лимиты на запросы
@rate_limit_requests(4, 60, translate_key="errors.many_attempts_weather")
@cache_with_ttl(300)
def fetch_weather(city: str) -> str:
    """
    Возвращает текущую погоду по городу city
    """
    logging.info(f"weather in {city}")
    url = "http://api.openweathermap.org/data/2.5/weather"
    weather = requests.get(
        url,
        params={
            "APPID": config.WEATHER_API_KEY,
            "q": city,
            "units": "metric",
            "lang": request.user.settings.lang,
        },
    ).json()
    weather_icon = weather["weather"][0]["icon"]
    dn = {"d": "☀", "n": "🌑"}
    we = {
        "01": "",
        "02": "🌤",
        "03": "🌥",
        "04": "☁",
        "09": "🌨",
        "10": "🌧",
        "11": "⛈",
        "13": "❄",
        "50": "🌫",
    }
    de = {
        0: "⬆️",
        45: "↗️",
        90: "➡️",
        135: "↘️",
        180: "⬇️",
        225: "↙️",
        270: "⬅️",
        315: "↖️",
    }

    try:
        weather_icon = dn[weather_icon[-1]] + we[weather_icon[:2]]
    except KeyError:
        weather_icon = weather["weather"][0]["main"]

    delta = timedelta(hours=weather["timezone"] // 60 // 60)
    city_name = weather["name"].capitalize()
    weather_description = (
        weather["weather"][0]["description"].capitalize().replace(" ", "\u00A0")
    )
    time_in_city = f"{datetime.now(timezone.utc)+delta}".replace("-", ".")[:-13]
    weather_time = f"{datetime.utcfromtimestamp(weather['dt'])+delta}".replace("-", ".")
    temp = int(weather["main"]["temp"])
    feels_like = int(weather["main"]["feels_like"])
    wind_speed = f"{weather['wind']['speed']:.1f}"
    wind_deg = weather["wind"]["deg"]
    wind_deg_icon = de[0 if (d := round(int(wind_deg) / 45) * 45) == 360 else d]
    sunrise = str(datetime.utcfromtimestamp(weather["sys"]["sunrise"]) + delta)
    sunrise = sunrise.split(" ")[-1]
    sunset = str(datetime.utcfromtimestamp(weather["sys"]["sunset"]) + delta)
    sunset = sunset.split(" ")[-1]
    visibility = weather["visibility"]

    return get_translate("messages.weather").format(
        city_name,
        weather_icon,
        weather_description,
        time_in_city,
        weather_time,
        temp,
        feels_like,
        wind_speed,
        wind_deg_icon,
        wind_deg,
        sunrise,
        sunset,
        visibility,
    )


@rate_limit_requests(4, 60, translate_key="errors.many_attempts_weather")
@cache_with_ttl(3600)
def fetch_forecast(city: str) -> str:
    """
    Прогноз погоды на 5 дней для города city
    """
    logging.info(f"forecast in {city}")
    url = "http://api.openweathermap.org/data/2.5/forecast"
    weather = requests.get(
        url,
        params={
            "APPID": config.WEATHER_API_KEY,
            "q": city,
            "units": "metric",
            "lang": request.user.settings.lang,
        },
    ).json()
    dn = {"d": "☀", "n": "🌑"}
    we = {
        "01": "",
        "02": "🌤",
        "03": "🌥",
        "04": "☁",
        "09": "🌨",
        "10": "🌧",
        "11": "⛈",
        "13": "❄",
        "50": "🌫",
    }
    de = {
        0: "⬆️",
        45: "↗️",
        90: "➡️",
        135: "↘️",
        180: "⬇️",
        225: "↙️",
        270: "⬅️",
        315: "↖️",
    }

    city_timezone = timedelta(hours=weather["city"]["timezone"] // 60 // 60)
    sunrise = datetime.utcfromtimestamp(weather["city"]["sunrise"]) + city_timezone
    sunset = datetime.utcfromtimestamp(weather["city"]["sunset"]) + city_timezone
    result = f"{weather['city']['name']}\n☀ {sunrise}\n🌑 {sunset}"

    for hour in weather["list"]:
        weather_icon = hour["weather"][0]["icon"]

        try:
            weather_icon = dn[weather_icon[-1]] + we[weather_icon[:2]]
        except KeyError:
            weather_icon = hour["weather"][0]["main"]

        weather_description = (
            hour["weather"][0]["description"].capitalize().replace(" ", "\u00A0")
        )
        temp = hour["main"]["temp"]
        wind_speed = hour["wind"]["speed"]
        wind_deg = hour["wind"]["deg"]
        wind_deg_icon = de[0 if (d := round(int(wind_deg) / 45) * 45) == 360 else d]
        city_time = hour["dt_txt"].replace("-", ".")[:-3]
        date = ".".join(city_time.split()[0].split(".")[::-1])
        if date not in result:
            day = DayInfo(date)
            result += (
                f"\n\n<b>{date}</b> <u><i>{day.str_date}  "
                f"{day.week_date}</i></u> ({day.relatively_date})"
            )
        result += (
            f"\n{city_time.split()[-1]} {weather_icon}<b>{temp:⠀>2.0f}°C "
            f"💨{wind_speed:.0f}м/с {wind_deg_icon}</b> "
            f"<u>{weather_description}</u>."
        )
    return result


def is_secure_chat(message: Message):
    """
    Безопасный ли чат для админских команд.
    Чат должен быть приватным.
    """
    return is_admin_id(message.chat.id) and message.chat.type == "private"


def poke_link() -> None:
    try:
        requests.get(config.LINK, headers=config.headers)
    except MissingSchema as e:
        logging.error(f"{e}")
    except ConnectionError:
        logging.error("404")


def write_table_to_str(
    file: StringIO,
    table: list[tuple[str, ...], ...] = None,
    query: str = None,
    commit: bool = False,
    align: tuple[Literal["<", ">", "^"]] = "<",
) -> None:
    """
    Наполнит файл file строковым представлением таблицы результата SQL(query)
    """
    if not table:
        table = [
            [str(column) for column in row]
            for row in db.execute(query, commit=commit, column_names=True)
        ]

    # Обрезаем длинные строки до 126 символов (уменьшается размер файла)
    table = [
        [
            "\n".join(
                " \\\n".join(
                    textwrap(
                        line, width=126, replace_whitespace=False, drop_whitespace=True
                    )
                    or " "
                )
                for line in column.splitlines()
            )
            for column in row
        ]
        for row in table
    ]

    # Матрица максимальных длин и высот каждого столбца и строки
    w = [
        [max(len(line) for line in str(column).splitlines()) for column in row]
        for row in table
    ]

    # Вычисляем максимальную ширину и высоту каждого столбца и строки
    widths = [max(column) for column in zip(*w)]

    sep = "+" + "".join(("-" * (i + 2)) + "+" for i in widths)  # Разделитель строк
    template = "|" + "".join(f" {{:{align}{_}}} |" for _ in widths)

    for n, row in enumerate(table):
        file.write(sep + "\n")

        # Индексы столбцов в которых несколько строк
        indices = [
            i for i, column in enumerate(row) if len(str(column).splitlines()) > 1
        ]

        if indices:
            # Получаем первую текстовую строку строки таблицы
            first_line = row[:]
            for x in indices:
                first_line[x] = row[x].splitlines()[0]
            file.write(template.format(*first_line) + "\n")

            # Количество строк в каждом столбце
            indents = [len(str(column).splitlines()) for column in row]

            max_lines = max(indents)
            for ml in range(1, max_lines):  # проходим по максимум новых строчек
                new_line = ["" for _ in indents]
                for i in indices:  # получаем индексы многострочных ячеек
                    try:
                        new_line[i] = str(row[i]).splitlines()[ml]
                    except IndexError:
                        pass
                file.write(
                    template.format(*new_line) + ("\n" if ml < max_lines - 1 else "")
                )

        else:
            file.write(template.format(*row))
        file.write("\n")
    file.write(sep)
    file.seek(0)


def highlight_text_difference(_old_text, _new_text):
    sequence_matcher = difflib.SequenceMatcher(None, _old_text, _new_text)
    opcodes = sequence_matcher.get_opcodes()

    result_parts = []
    for opcode, i1, i2, j1, j2 in opcodes:
        if opcode in ("insert", "replace"):
            result_parts.append(f"<u>{_new_text[j1:j2]}</u>")
        elif opcode == "equal":
            result_parts.append(_new_text[j1:j2])

    result_text = "".join(result_parts)
    return result_text


def parse_message(text: str) -> list[Event]:
    """
    Парсит сообщение и возвращает список событий
    """
    event_list: list[Event] = []
    msg_date = None

    if m := re.match(r"\A\d{2}\.\d{2}\.\d{4}", text):
        msg_date = m[0]

    for str_event in text.split("\n\n")[1:]:
        if m := re.match(
            r"\A(\d{2}\.\d{2}\.\d{4})\.(\d+)\.(\S{1,3}(?:,\S{1,3}){0,4}) ", str_event
        ):
            event_date, event_id, event_status = m[1], m[2], m[3]
        elif m := re.match(
            r"\A(10|[1-9])\.(\d+)\.(\S{1,3}(?:,\S{1,3}){0,4})", str_event
        ):
            event_date, event_id, event_status = msg_date, m[2], m[3]
        else:
            continue

        event_list.append(
            Event(
                event_id=event_id,
                date=event_date,
                text=str_event.split("\n", maxsplit=1)[1],
                status=event_status,
            )
        )

    return event_list


def days_before_event(event_date: str, event_status: str) -> tuple[int, str, str]:
    """
    В сообщении уведомления показывает через сколько будет повторяющееся событие.
    :return: ('разница в днях', 'дата ближайшего повторения', 'текстовое представление разницы')
    """
    _date = convert_date_format(event_date)
    now_t = now_time()
    dates = []

    # Каждый день
    if "📬" in event_status:
        day = DayInfo(f"{now_t:%d.%m.%Y}")
        return day.day_diff, day.date, day.relatively_date

    # Каждую неделю
    if "🗞" in event_status:
        now_wd, event_wd = now_t.weekday(), _date.weekday()
        next_date = now_t + timedelta(days=(event_wd - now_wd + 7) % 7)
        dates.append(next_date)

    # Каждый месяц
    elif "📅" in event_status:
        day = DayInfo(f"{_date:%d}.{now_t:%m.%Y}")
        month, year = day.datetime.month, day.datetime.year
        if day.day_diff >= 0:
            dates.append(day.datetime)
        else:
            if month < 12:
                dates.append(day.datetime.replace(month=month + 1))
            else:
                dates.append(day.datetime.replace(year=year + 1, month=1))

    # Каждый год
    elif {*event_status.split(",")}.intersection({"📆", "🎉", "🎊"}):
        day = DayInfo(f"{_date:%d.%m}.{now_t:%Y}")
        if day.datetime.date() < now_t.date():
            dates.append(day.datetime.replace(year=now_t.year + 1))
        else:
            dates.append(day.datetime.replace(year=now_t.year))

    else:
        day = DayInfo(event_date)
        return day.day_diff, day.date, day.relatively_date

    day = DayInfo(f"{min(dates):%d.%m.%Y}")
    return day.day_diff, day.date, day.relatively_date
