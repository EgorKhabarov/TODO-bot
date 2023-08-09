import re
from time import time
from io import StringIO
from typing import Any, Literal
from urllib.parse import urlparse
from textwrap import wrap as textwrap
from datetime import timedelta, datetime, timezone

import requests
from requests import ConnectionError
from requests.exceptions import MissingSchema
from telebot.types import Message, CallbackQuery

import config
import logging
from lang import get_translate
from time_utils import DayInfo
from todoapi.api import User
from todoapi.utils import is_admin_id
from todoapi.types import db, UserSettings


def to_html_escaping(text: str) -> str:
    return (
        text.replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&#39;")
        .replace('"', "&quot;")
    )


def remove_html_escaping(text: str) -> str:
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )


def html_to_markdown(html_text: str) -> str:
    for (k1, k2), v in {
        ("<i>", "</i>"): "__",
        ("<b>", "</b>"): "**",
        ("<s>", "</s>"): "~~",
        ("<pre>", "</pre>"): "```",
        ("<code>", "</code>"): "`",
        ('<span class="tg-spoiler">', "</span>"): "||",
    }.items():
        html_text = html_text.replace(k1, v).replace(k2, v)

    def prepare_url(url):
        url = url.removeprefix("http://").removeprefix("https://")
        url = url.strip().strip("/").strip("\\")
        return f"https://{url}"

    html_text = re.sub(
        r"<a href=\"(.+?)\">(\S+?)(\n??)</a>",
        lambda x: " {url} ({text}) {n}".format(  #
            url=prepare_url(x.group(1)),
            text=x.group(2).strip(),
            n=x.group(3),
        ),
        html_text,
    )
    return html_text


def markdown(text: str, statuses: str, sub_url: bool | int = False) -> str:
    """
    Добавляем эффекты к событию по статусу
    """

    def OrderList(_text: str, num=0) -> str:  # Нумерует каждую строчку
        lst = _text.splitlines()
        width = len(str(len(lst)))  # Получаем длину отступа чтобы не съезжало
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
        def la(url):
            return f"<a href='{url[0]}'>{urlparse(url[0]).netloc}</a>"

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


class Cooldown:
    """
    Возвращает True если прошло больше времени
    MyCooldown = Cooldown(cooldown_time, {})
    MyCooldown.check(chat_id)
    """

    def __init__(self, cooldown_time_sec: int, cooldown_dict: dict):
        self._cooldown_time_sec = cooldown_time_sec
        self._cooldown_dict = cooldown_dict

    def check(self, key: Any, update_dict=True):
        """
        :param key: Ключ по которому проверять словарь
        :param update_dict: Отвечает за обновление словаря
        Если True то после каждого обновления время будет обнуляться
        :return: (bool, int(time_difference))
        """
        t1 = time()
        result = True, 0

        try:
            if (
                localtime := (t1 - self._cooldown_dict[str(key)])
            ) < self._cooldown_time_sec:
                result = (False, int(self._cooldown_time_sec - int(localtime)))
        except KeyError:
            pass

        if update_dict or result[0]:
            self._cooldown_dict[f"{key}"] = t1
        return result


def rate_limit_requests(requests_count: int = 3, time_sec: int = 60):
    """
    Возвращает текст ошибки,
    если пользователи вызывали функцию чаще чем 3 раза в 60 секунд.
    """

    def decorator(func):
        cache = []

        def wrapper(*args, **kwargs):
            now = time()
            cache[:] = [call for call in cache if now - call < time_sec]
            if len(cache) >= requests_count:
                wait_time = time_sec - int(now - cache[0])
                return (
                    "Погоду запрашивали слишком часто...\n"
                    f"Подождите ещё {wait_time} секунд"
                )
            cache.append(now)
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
    table = [
        list(str(column) for column in row)
        for row in (
            db.execute(query, commit=commit, column_names=True) if not table else table
        )
    ]

    # Обрезаем длинные строки до 126 символов (уменьшается размер файла)
    table = [
        [
            "\\n\n".join(
                textwrap(
                    column, width=126, replace_whitespace=False, drop_whitespace=True
                )
                or " "
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

def check_user(func):
    def wrapper(x: Message | CallbackQuery):
        if isinstance(x, Message):
            chat_id = x.chat.id
        elif isinstance(x, CallbackQuery):
            chat_id = x.message.chat.id
            if x.data == "None":
                return 0
        else:
            return

        with db.connection(), db.cursor():
            user = User(chat_id)

            if user.settings.user_status == -1 and not is_admin_id(chat_id):
                return

            res = func(x, user)
        return res

    return wrapper
