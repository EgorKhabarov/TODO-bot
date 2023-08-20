import re
import difflib
from time import time
from io import StringIO
from typing import Literal
from functools import wraps
from urllib.parse import urlparse
from textwrap import wrap as textwrap
from datetime import timedelta, datetime, timezone

import requests
from telebot.types import Message
from requests import ConnectionError
from requests.exceptions import MissingSchema

import config
import logging
from lang import get_translate
from time_utils import DayInfo
from todoapi.utils import is_admin_id
from todoapi.types import db, UserSettings


re_edit_message = re.compile(
    r"\A@\w{5,32} event\((\d{1,2}\.\d{1,2}\.\d{4}), (\d+), (\d+)\)\.text(?:\n|\Z)"
)


def markdown(text: str, statuses: str, sub_url: bool | int = False) -> str:
    """
    Добавляем эффекты к событию по статусу
    """

    def OrderList(_text: str, num=0) -> str:  # Нумерует каждую строчку
        lst = _text.splitlines()

        # Получаем длину отступа чтобы не съезжало
        width = len(
            str(
                len(
                    list(
                        line
                        for line in lst
                        if not (line.startswith("-- ") or line.startswith("— "))
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
                if not (line.startswith("-- ") or line.startswith("— "))
                else line.removeprefix("-- ").removeprefix("— ")
            )
            if line not in ("", "⠀")
            else "⠀"
            for line in lst
        )

    def List(_text: str):  # Заменяет \n на :black_small_square: (эмодзи Telegram)
        _text = "▪️" + _text
        for old, new in (
            ("\n", "\n▪️"),
            ("\n▪️⠀\n", "\n⠀\n"),
            ("▪️-- ", ""),
            ("▪️— ", ""),
        ):
            _text = _text.replace(old, new)
        return _text

    def Spoiler(_text: str):
        return f"<span class='tg-spoiler'>{_text}</span>"

    def SubUrls(_text: str):
        def la(m: re.Match):
            url = re.sub(r"\Ahttp://", "https://", m[0])

            if re.search(r"https://t\.me/\w{5,32}", url):
                # Если это ссылка на пользователя
                return f"<a href='{url}'>@{url.removeprefix('https://t.me/')}</a>"

            return f"<a href='{url}'>{urlparse(url).netloc}</a>"

        return re.sub(r"(http?s?://[^\"\'\n ]+)", la, _text)  # r"(http?s?://\S+)"

    def Code(_text: str):
        return f"<pre>{_text}</pre>"

    # Сокращаем несколько подряд переносов строки
    text = re.sub(r"\n(\n*)\n", "\n⠀\n", text)

    if ("🔗" in statuses and "⛓" not in statuses) or (
        sub_url and ("💻" not in statuses and "⛓" not in statuses)
    ):
        text = SubUrls(text)

    for status in statuses.split(","):
        if status == "🗒":
            text = List(text)
        if status == "🧮":
            text = OrderList(text)
        if status == "💻":
            text = Code(text)
        if status == "🪞":
            text = Spoiler(text)

    return text


def rate_limit_requests(
    requests_count: int = 3,
    time_sec: int = 60,
    key_path: int | str | tuple[str | int] | set[str | int] = None,
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
                result = (_kwargs.get(a) or _args[0]) if i == 0 else getattr(result, a)
            return result

        elif isinstance(path, tuple):
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
                return wait_time

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
        def wrapper(settings: UserSettings, city: str):
            key = f"{city} {settings.lang}"
            now = time()
            if key not in cache or now - cache[key][1] > cache_time_sec:
                cache[key] = (func(settings, city), now)
            return cache[key][0]

        return wrapper

    return decorator


# TODO добавить персональные api ключи для запрашивания погоды
# TODO декоратор для проверки api ключа у пользователя
# TODO в зависимости от наличия ключа ставить разные лимиты на запросы
@rate_limit_requests(4, 60)
@cache_with_ttl(300)
def fetch_weather(settings: UserSettings, city: str) -> str:
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
            "lang": settings.lang,
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

    return get_translate("weather", settings.lang).format(
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


@rate_limit_requests(4, 60)
@cache_with_ttl(3600)
def fetch_forecast(settings: UserSettings, city: str) -> str:
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
            "lang": settings.lang,
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

    citytimezone = timedelta(hours=weather["city"]["timezone"] // 60 // 60)
    sunrise = str(
        datetime.utcfromtimestamp(weather["city"]["sunrise"]) + citytimezone
    ).split(" ")[-1]
    sunset = str(
        datetime.utcfromtimestamp(weather["city"]["sunset"]) + citytimezone
    ).split(" ")[-1]
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
            day = DayInfo(settings, date)
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
    logging.info(f"{config.LINK}")

    try:
        logging.info(f"{requests.get(config.LINK, headers=config.headers).status_code}")
    except MissingSchema as e:
        logging.info(f"{e}")
    except ConnectionError:
        logging.info("404")


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
