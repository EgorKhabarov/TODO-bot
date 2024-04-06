import re
import html
import difflib
import logging
from time import time
from functools import wraps
from urllib.parse import urlparse
from typing import Literal, Callable
from datetime import timedelta, datetime, timezone

import requests
from cachetools.keys import hashkey
from requests import ConnectionError
from cachetools import TTLCache, LRUCache, cached
from requests.exceptions import MissingSchema

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery, BotCommandScopeChat

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

import config
from config import ts
from tgbot.bot import bot
from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.time_utils import relatively_string_date
from todoapi.utils import is_admin_id


re_edit_message = re.compile(r"\A@\w{5,32} event\((\d+), (\d+)\)\.text(?:\n|\Z)")
re_group_edit_name_message = re.compile(
    r"(?s)\A@\w{5,32} group\((\w{32}), (\d+)\)\.name(?:\n|\Z)(.*)"
)
re_user_edit_name_message = re.compile(
    r"(?s)\A@\w{5,32} user\((\d+)\)\.name(?:\n|\Z)(.*)"
)
re_user_edit_password_message = re.compile(
    r"\A@\w{5,32} user\(\)\.password\nold password: ?(.*)\nnew password: ?(.*)\Z"
)
link_sub = re.compile(r"<a href=\"(.+?)\">(.+?)(\n*?)</a>")
add_group_pattern = re.compile(r"\A/start@\w{5,32} group-(\d+)-([a-z\d]{32})\Z")


def telegram_log(action: str, text: str):
    text = text.replace("\n", "\\n")
    thread_id = getattr(request.query, "message", request.query).message_thread_id
    if request.entity:
        logging.info(
            f"[{str(request.entity_type).capitalize()}:{request.entity.request_id}]"
            + f"[{request.entity.request_chat_id:<10}"
            + (f":{thread_id}" if thread_id else "")
            + "]"
            + (
                f"[{request.entity.user.user_status}]"
                if request.is_user
                else f"[{request.entity.group.member_status}]"
            )
            + f".{action} {text}"
        )
    else:
        logging.info(
            f"[Not Login {str(request.entity_type).capitalize()}]"
            + f"[{request.chat_id:<10}"
            + (f":{thread_id}" if thread_id else "")
            + "]"
            + f".{action} {text}"
        )


def add_status_effect(text: str, statuses: str) -> str:
    """
    Добавляем эффекты к событию по статусу
    """

    def check_comment_in_status(comment_string: Literal["##", "//", "--"]) -> bool:
        """
        Проверить будет ли этот символ комментария считаться за комментарий при выбранных языках.
        """
        status_set = {s.removeprefix("💻") for s in statuses_list if s.startswith("💻")}

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
        return line == ts or (
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
        width = len(str(len(tuple(line for line in lst if not is_comment_line(line)))))

        # Заполняем с отступами числа + текст, а если двойной перенос строки то ""
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
            if line
            else ""
            for line in lst
        )

    def format_list(_text: str) -> str:
        """Заменяет \n на :black_small_square: (эмодзи Telegram)"""
        point = "▫️" if request.entity.settings.theme == 1 else "▪️"
        big_point = "◻️" if request.entity.settings.theme == 1 else "◼️"
        lst = _text.splitlines()

        return "\n".join(
            (
                (
                    (big_point if line.startswith("!!") else point)
                    + line.removeprefix("!!")
                )
                if not is_comment_line(line)
                else remove_comment_prefix(line)
            )
            if line
            else ""
            for line in lst
        )

    def format_spoiler(spoiler: str) -> str:
        return f"<span class='tg-spoiler'>{spoiler}</span>"

    def sub_urls(_text: str) -> str:
        def la(m: re.Match):
            url = re.sub(r"\Ahttp://", "https://", m[0])

            if re.search(r"https://t\.me/\w{5,32}", url):
                # Если это ссылка на пользователя
                return f"<a href='{url}'>@{url.removeprefix('https://t.me/')}</a>"

            return f"<a href='{url}'>{urlparse(url).netloc}</a>"

        return re.sub(r"(http?s?://[^\"\')\n ]+)", la, _text)  # r"(http?s?://\S+)"

    def format_code(code: str) -> str:
        return f"<pre>{code}</pre>"

    def format_code_lang(code: str, lang: str) -> str:
        return f"<pre><code class='language-{lang}'>{code}</code></pre>"

    def format_blockquote(_text: str) -> str:
        return f"<blockquote>{_text}</blockquote>"

    text = html.escape(text)

    # Сокращаем несколько подряд переносов строки
    text = re.sub(r"\n(\n*)\n", "\n\n", text)

    if ("🔗" in statuses and "⛓" not in statuses) or (
        request.entity.settings.sub_urls
        and ("💻" not in statuses and "⛓" not in statuses)
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

    if "💬" in statuses:
        text = format_blockquote(text)

    return text


def rate_limit(
    storage: LRUCache,
    max_calls: int,
    seconds: int,
    key_func: Callable = hashkey,
    else_func: Callable = lambda args, kwargs, key, sec: (key, sec),
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs)
            contains = key in storage
            t = time()

            if contains:
                storage[key] = [call for call in storage[key] if t - call < seconds]

                if len(storage[key]) >= max_calls:
                    sec = seconds - int(t - storage[key][0])
                    return else_func(args, kwargs, key=key, sec=sec)

            storage.setdefault(key, []).append(t)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _get_cache_city_key(city):
    return city, request.entity.settings.lang


def _get_cache_city_key_user_id(city):
    return city, request.entity.settings.lang, request.entity.user_id


@rate_limit(
    LRUCache(maxsize=100),
    10,
    60,
    lambda *args, **kwargs: request.entity.user_id,
    lambda *args, **kwargs: None,
)
def _else_func(args, kwargs, key, sec) -> str:  # noqa
    return get_translate("errors.many_attempts_weather").format(int(sec))


@rate_limit(LRUCache(maxsize=100), 4, 60, _get_cache_city_key_user_id, _else_func)
@cached(TTLCache(100, 60 * 5), _get_cache_city_key)
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
            "lang": request.entity.settings.lang,
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


@rate_limit(LRUCache(maxsize=100), 4, 60, _get_cache_city_key_user_id, _else_func)
@cached(TTLCache(100, 60 * 60), _get_cache_city_key)
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
            "lang": request.entity.settings.lang,
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
            dt_date = datetime.strptime(date, "%d.%m.%Y")
            n_time = request.entity.now_time()
            n_time = datetime(n_time.year, n_time.month, n_time.day)
            str_date, rel_date, week_date = relatively_string_date(
                (dt_date - n_time).days
            )
            result += f"\n\n<b>{dt_date:%d.%m.%Y}</b> <u><i>{str_date}  {week_date}</i></u> ({rel_date})"

        mps = get_translate("text.meters_per_second")
        result += (
            f"\n{city_time.split()[-1]} {weather_icon}<b>{temp:{ts}>2.0f}°C "
            f"💨{wind_speed:.0f}{mps} {wind_deg_icon}</b> "
            f"<u>{weather_description}</u>."
        )
    return result


def is_secure_chat(message: Message | CallbackQuery):
    """
    Безопасный ли чат для админских команд.
    Чат должен быть приватным.
    """
    if isinstance(message, CallbackQuery):
        message = message.message

    chat_id, chat_type = message.chat.id, message.chat.type
    return is_admin_id(chat_id) and chat_type == "private"


def poke_link() -> None:
    try:
        requests.get(config.SERVER_URL, headers=config.headers)
    except MissingSchema as e:
        logging.error(f"poke_link {e}")
    except ConnectionError:
        logging.error("poke_link 404")


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

    def prepare_url(url) -> str:
        url = url.removeprefix("http://").removeprefix("https://")
        url = url.strip().strip("/").strip("\\")
        return f"https://{url}"

    def replace_url(m: re.Match) -> str:
        # Экранируем символы []() для правильного взаимодействия с markdown ссылками
        url = prepare_url(m.group(1)).replace("(", "%28").replace(")", "%29")
        caption = str(m.group(2)).strip().replace("[", "\[").replace("]", "\]")

        # Проверяем, что caption не совпадает с доменом ссылки
        condition = caption != urlparse(m.group(1)).netloc
        if condition:
            return f"[{caption}]({url}){m.group(3)}"
        else:
            return f"{url}{m.group(3)}"

    html_text = html.unescape(link_sub.sub(replace_url, html_text))
    return html_text


def sqlite_format_date2(_date: str) -> str:
    """12.34.5678 -> 5678-34-12"""
    return "-".join(_date.split(".")[::-1])


def extract_search_query(message_text: str) -> str:
    first_line = message_text.split("\n", maxsplit=1)[0]
    return html.escape(first_line.split(maxsplit=2)[-1][:-1])


def set_bot_commands(not_login: bool = False):
    """
    Ставит список команд для пользователя chat_id
    """

    if not_login:
        target = "buttons.commands.not_login"
    else:
        status = request.entity.user.user_status
        if request.is_user and request.entity.is_admin and status != -1:
            status = 2
        target = f"buttons.commands.{status}.{request.entity_type}"

    try:
        bot.set_my_commands(get_translate(target), BotCommandScopeChat(request.chat_id))
    except ApiTelegramException as e:
        logging.error(f'set_bot_commands ApiTelegramException "{e}"')
