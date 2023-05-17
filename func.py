from datetime import datetime, timedelta, timezone
from calendar import monthcalendar, isleap
from sqlite3 import connect, Error # pip3.10 install --user sqlite3
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Literal, Any
from copy import deepcopy
from io import StringIO
from time import time
import re

from requests import get # pip install requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException

from lang import translation
import config


"""sql"""
sqlite_format_date = lambda column, quotes="", sep="-": f"""
    SUBSTR({quotes}{column}{quotes}, 7, 4) || \'{sep}\' || 
    SUBSTR({quotes}{column}{quotes}, 4, 2) || \'{sep}\' || 
    SUBSTR({quotes}{column}{quotes}, 1, 2)"""
"""SUBSTR({column}, 7, 4) || '{sep}' || SUBSTR({column}, 4, 2) || '{sep}' || SUBSTR({column}, 1, 2)"""
sqlite_format_date2 = lambda date: "-".join(date.split(".")[::-1])
"""\"12.34.5678\" -> \"5678-34-12\""""

def SQL(query: str, params: tuple = (), commit: bool = False,
        column_names: bool = False) -> list[tuple[int | str | bytes, ...], ...]:
    """
    Выполняет SQL запрос
    Пробовал через with, но оно не закрывало файл

    :param query: Запрос
    :param params: Параметры запроса (необязательно)
    :param commit: Нужно ли сохранить изменения? (необязательно, по умолчанию False)
    :param column_names: Названия столбцов вставить в результат
    :return: Результат запроса
    """
    connection = connect(config.database_path)
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        if commit: connection.commit()
        result = cursor.fetchall()
        if column_names:
            description = [column[0] for column in cursor.description]
            result = [description] + result
    finally:
        connection.close()
    return result

class UserSettings:
    """
    Настройки для пользователя

    Параметры:
    .user_id     ID пользователя
    .lang        Язык
    .sub_urls    Сокращать ли ссылки
    .city        Город
    .timezone    Часовой пояс
    .direction   Направление вывода
    .user_status Обычный, Премиум, Админ (0, 1, 2)

    Функции
    .get_user_settings()
    """
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.lang, self.sub_urls, self.city, self.timezone, \
            self.direction, self.user_status, self.notifications = self._get_user_settings()

    def _get_user_settings(self):
        """
        Возвращает список из настроек для пользователя self.user_id
        """
        query = f"""SELECT lang, sub_urls, city, timezone, direction, user_status, notifications
                    FROM settings WHERE user_id={self.user_id};"""
        try:
            return SQL(query)[0]
        except (Error, IndexError):
            print("Добавляю нового пользователя")
            SQL(f"INSERT INTO settings (user_id) VALUES ({self.user_id});", commit=True)
        return SQL(query)[0]

    def get_settings(self) -> tuple[str, InlineKeyboardMarkup]:
        """
        Ставит настройки для пользователя chat_id
        """
        not_lang = "ru" if self.lang == "en" else "en"
        not_sub_urls = 1 if self.sub_urls == 0 else 0
        not_direction = "⬇️" if self.direction == "⬆️" else "⬆️"
        not_notifications_ = ("🔔", 8, "🔕") if self.notifications == -1 else ("🔕", -1, "🔔")

        utz = self.timezone
        str_utz = f"""{utz} {"🌍" if -2 < int(utz) < 5 else ("🌏" if 4 < int(utz) < 12 else "🌎")}"""

        time_zone_dict = {}
        time_zone_dict.__setitem__(*('‹‹‹', f'settings timezone {utz - 1}') if utz > -11 else ('   ', 'None'))
        time_zone_dict[str_utz] = 'settings timezone 3'
        time_zone_dict.__setitem__(*('›››', f'settings timezone {utz + 1}') if utz < 11 else ('   ', 'None'))

        notifications_time = {}
        if not_notifications_[2] == "🔔":
            notifications_time.__setitem__(*('‹‹‹', f'settings notifications {self.notifications - 1}') if self.notifications > 0 else ('   ', 'None'))
            notifications_time[f"{self.notifications}:00 ⏰"] = 'settings notifications 8'
            notifications_time.__setitem__(*('›››', f'settings notifications {self.notifications + 1}') if self.notifications < 24 else ('   ', 'None'))

        markup = generate_buttons([{f"🗣 {self.lang}": f"settings lang {not_lang}",
                                    f"🔗 {bool(self.sub_urls)}": f"settings sub_urls {not_sub_urls}",
                                    f"{not_direction}": f"settings direction {not_direction}",
                                    f"{not_notifications_[0]}": f"settings notifications {not_notifications_[1]}"},
                                   time_zone_dict,
                                   notifications_time,
                                   {"✖": "message_del"}])
        return get_translate("settings", self.lang).format(
            self.lang,
            bool(self.sub_urls),
            self.city,
            str_utz,
            self.direction,
            not_notifications_[2],
            f"{self.notifications}:00" if not_notifications_[2] == "🔔" else ""), markup

def create_tables() -> None:
    """
    Создание нужных таблиц
    # ALTER TABLE table ADD COLUMN new_column TEXT
    """
    try:
        SQL("""
            SELECT event_id, user_id, date, text, isdel, status
            FROM root LIMIT 1;""")
    except Error as e:
        if str(e) == "no such table: root":
            SQL("""
                CREATE TABLE root (
                    event_id  INTEGER,
                    user_id   INT,
                    date      TEXT,
                    text      TEXT,
                    isdel     INTEGER DEFAULT (0),
                    status    TEXT    DEFAULT ⬜️
                );""", commit=True)
        else:
            quit(f"{e}")

    try:
        SQL("""
            SELECT
            user_id, lang, sub_urls, city, timezone, direction, 
            user_status, notifications, user_max_event_id, add_event_date
            FROM settings LIMIT 1;""")
    except Error as e:
        if str(e) == "no such table: settings":
            SQL("""
                CREATE TABLE settings (
                    user_id           INT  NOT NULL UNIQUE ON CONFLICT ROLLBACK,
                    lang              TEXT DEFAULT ru,
                    sub_urls          INT  DEFAULT (1),
                    city              TEXT DEFAULT Москва,
                    timezone          INT  DEFAULT (3),
                    direction         TEXT DEFAULT ⬇️,
                    user_status       INT  DEFAULT (0),
                    notifications     INT  DEFAULT (-1),
                    user_max_event_id INT  DEFAULT (1),
                    add_event_date    INT  DEFAULT (0)
                );""", commit=True)
        else:
            quit(f"{e}")
create_tables()

def create_event(user_id: int, date: str, text: str) -> bool:
    """
    Создание события
    """
    try:
        SQL(f"""
            INSERT INTO root(event_id, user_id, date, text)
            VALUES(
              COALESCE((SELECT user_max_event_id FROM settings WHERE user_id = {user_id}), 1),
              {user_id}, '{date}', '{text}'
            );""", commit=True)
        SQL(f"""
            UPDATE settings
            SET user_max_event_id = user_max_event_id + 1
            WHERE user_id = {user_id};""", commit=True)
        return True
    except Error as e:
        print(f"[func.py -> create_event] Error \"{e}\"  arg: {user_id=}, {date=}, {text=}")
        return False

def get_values(column_to_limit: str,
               column_to_order: str,
               column_to_return: str,
               WHERE: str,
               table: str,
               MAXLEN: int = 3500,
               MAXEVENTCOUNT: int = 10,
               direction: Literal["ASC", "DESC"] = "DESC"
               ) -> list[tuple[int | str | bytes, ...], ...]:
    """
    Возвращает результаты по условиям WHERE, разделённые по условиям MAXLEN и MAXEVENTCOUNT на 'страницы'

    :param column_to_limit: Столбец для ограничения
    :param column_to_order: Столбец для сортировки (например id)
    :param column_to_return: Столбец для return (например id)
    :param WHERE:           Условие выбора строк из таблицы
    :param table:           Название таблицы
    :param MAXLEN:          Максимальная длинна символов в одном диапазоне
    :param MAXEVENTCOUNT:   Максимальное количество строк в диапазоне
    :param direction:       Направление сбора строк ("ASC" or "DESC")
    """
    column = "end_id" if direction == "DESC" else "start_id"
    query = f"""
WITH numbered_table AS (
  SELECT ROW_NUMBER() OVER (ORDER BY {column_to_order} {direction}) AS row_num, {column_to_return} AS order_column, LENGTH({column_to_limit}) as len
  FROM {table}
  WHERE {WHERE}
),
temp_table AS (
  SELECT numbered_table.row_num, numbered_table.order_column, numbered_table.len,
    numbered_table.order_column AS {column}, numbered_table.len AS sum_len,
    1 AS group_id, 1 AS event_count
  FROM numbered_table WHERE numbered_table.row_num = 1
  UNION ALL
  SELECT
    numbered_table.row_num, numbered_table.order_column, numbered_table.len,
    CASE WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.{column}                     ELSE numbered_table.order_column END AS {column},
    CASE WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.sum_len + numbered_table.len ELSE numbered_table.len          END AS sum_len,
    CASE WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.group_id                     ELSE temp_table.group_id + 1     END AS group_id,
    CASE WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.event_count + 1              ELSE 1                           END AS event_count
  FROM numbered_table JOIN temp_table ON numbered_table.row_num = temp_table.row_num + 1
)
SELECT GROUP_CONCAT(COALESCE(numbered_table.order_column, ''), ',') AS ids -- , SUM(numbered_table.len) AS sum_len
FROM numbered_table
JOIN temp_table ON numbered_table.row_num = temp_table.row_num
GROUP BY temp_table.group_id;
"""
    data = SQL(query)
    return data


"""time"""
def now_time(user_timezone: int) -> datetime:
    """
    Возвращает datetime с настоящим временем с учётом часовых поясов
    """
    return datetime.now()+timedelta(hours=user_timezone)

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

def year_info(year: int, lang: str) -> str:
    """
    Строковая информация про год
    "'имя месяца' ('номер месяца'.'год')('високосный или нет' 'животное этого года')"
    """
    result = ""
    if isleap(year): # year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        result += get_translate("leap", lang)
    else:
        result += get_translate("not_leap", lang)
    result += ' '
    result += ("🐀", "🐂", "🐅", "🐇", "🐲", "🐍", "🐴", "🐐", "🐒", "🐓", "🐕", "🐖")[(year - 4) % 12]
    return result

def get_week_number(YY, MM, DD) -> int: # TODO добавить номер недели в календари
    """
    Номер недели по дате
    """
    return datetime(YY, MM, DD).isocalendar()[1]

def execution_time(func):
    def wrapper(*args, **kwargs):
        start = time()
        result = func(*args, **kwargs)
        end = time()
        print(f" \t({end - start:.3f})")
        return result
    return wrapper

class DayInfo:
    """
    Информация о дне
    self.date            "переданная дата"
    self.str_date        "число название месяца"
    self.week_date       "день недели"
    self.relatively_date "через x дней" или "x дней назад"
    """
    def __init__(self, settings: UserSettings, date: str):
        today, tomorrow, day_after_tomorrow, yesterday, day_before_yesterday, after, ago, Fday = get_translate("relative_date_list", settings.lang)
        x = now_time(settings.timezone)
        x = datetime(x.year, x.month, x.day)
        y = datetime(*[int(x) for x in date.split('.')][::-1])

        day_diff = (y - x).days
        if day_diff == 0:    day_diff = f'{today}'
        elif day_diff == 1:  day_diff = f'{tomorrow}'
        elif day_diff == 2:  day_diff = f'{day_after_tomorrow}'
        elif day_diff == -1: day_diff = f'{yesterday}'
        elif day_diff == -2: day_diff = f'{day_before_yesterday}'
        elif day_diff > 2:   day_diff = f'{after} {day_diff} {Fday(day_diff)}'
        else: day_diff = f'{-day_diff} {Fday(day_diff)} {ago}'

        week_days = get_translate("week_days_list_full", settings.lang)
        month_list = get_translate("months_name2", settings.lang)

        self.date = date
        self.str_date = f"{y.day} {month_list[y.month - 1]}"
        self.week_date = week_days[y.weekday()]
        self.relatively_date = day_diff


"""weather"""
# TODO добавить персональные api ключи для запрашивания погоды
#  Сделать декоратор для проверки api ключа у пользователя
#  и в зависимости от наличия ключа ставить разные лимиты на запросы
def no_spam(requests_count: int = 3, time_sec: int = 60):
    """
    Возвращает текст ошибки, если пользователи вызывали функцию чаще чем 3 раза в 60 секунд.
    """
    def decorator(func):
        cache = []

        def wrapper(*args, **kwargs):
            now = time()
            cache[:] = [call for call in cache if now - call < time_sec]
            if len(cache) >= requests_count:
                wait_time = time_sec - int(now - cache[0])
                return (f"Погоду запрашивали слишком часто...\n"
                        f"Подождите ещё {wait_time} секунд")
            cache.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def time_cache(cache_time_sec: int = 60):
    """
    Кеширует значение функции подобно functools.cache, но держит значение не больше cache_time_sec.
    Не даёт запрашивать новый результат функции с одним и тем же аргументом чаще чем в cache_time_sec секунды.
    """
    def decorator(func):
        cache = {}

        def wrapper(settings: UserSettings, city: str):
            key = f"{city}"
            now = time()
            if key not in cache or now - cache[key][1] > cache_time_sec:
                cache[key] = (func(settings, city), now)
            return cache[key][0]

        return wrapper

    return decorator

@no_spam(4, 60)
@time_cache(300)
def weather_in(settings: UserSettings, city: str) -> str:
    """
    Возвращает текущую погоду по городу city
    """
    print(f"\nweather in {city:<67}", end="")
    url = 'http://api.openweathermap.org/data/2.5/weather'
    weather = get(url, params={'APPID': config.weather_api_key, 'q': city, 'units': 'metric', 'lang': settings.lang}).json()
    weather_icon = weather['weather'][0]['icon']
    dn = {"d": "☀", "n": "🌑"}
    we = {"01": "", "02": "🌤", "03": "🌥", "04": "☁", "09": "🌨", "10": "🌧", "11": "⛈", "13": "❄", "50": "🌫"}
    de = {0: "⬆️", 45: "↗️", 90: "➡️", 135: "↘️", 180: "⬇️", 225: "↙️", 270: "⬅️", 315: "↖️"}

    try:
        weather_icon = dn[weather_icon[-1]] + we[weather_icon[:2]]
    except KeyError:
        weather_icon = weather['weather'][0]['main']

    delta = timedelta(hours=weather["timezone"]//60//60)
    city_name = weather["name"].capitalize()
    weather_description = weather['weather'][0]['description'].capitalize().replace(' ', "\u00A0")
    time_in_city = f'{datetime.now(timezone.utc)+delta}'.replace('-', '.')[:-13]
    weather_time = f'{datetime.utcfromtimestamp(weather["dt"])+delta}'.replace('-', '.')
    temp = int(weather['main']['temp'])
    feels_like = int(weather['main']['feels_like'])
    wind_speed = f"{weather['wind']['speed']:.1f}"
    wind_deg = weather['wind']['deg']
    wind_deg_icon = de[0 if (d := round(int(wind_deg)/45)*45) == 360 else d]
    sunrise = f'{datetime.utcfromtimestamp(weather["sys"]["sunrise"])+delta}'.split(' ')[-1]
    sunset = f'{datetime.utcfromtimestamp(weather["sys"]["sunset"])+delta}'.split(' ')[-1]
    visibility = weather['visibility']

    return get_translate("weather", settings.lang).format(city_name, weather_icon, weather_description,
                                                          time_in_city, weather_time,
                                                          temp, feels_like,
                                                          wind_speed, wind_deg_icon,  wind_deg,
                                                          sunrise, sunset, visibility)

@no_spam(4, 60)
@time_cache(3600)
def forecast_in(settings: UserSettings, city: str) -> str:
    """
    Прогноз погоды на 5 дней для города city
    """
    print(f"\nforecast in {city:<67}", end="")
    url = "http://api.openweathermap.org/data/2.5/forecast"
    weather = get(url, params={'APPID': config.weather_api_key, 'q': city, 'units': 'metric', 'lang': settings.lang}).json()
    dn = {"d": "☀", "n": "🌑"}
    we = {"01": "", "02": "🌤", "03": "🌥", "04": "☁", "09": "🌨", "10": "🌧", "11": "⛈", "13": "❄", "50": "🌫"}
    de = {0: "⬆️", 45: "↗️", 90: "➡️", 135: "↘️", 180: "⬇️", 225: "↙️", 270: "⬅️", 315: "↖️"}

    citytimezone = timedelta(hours=weather['city']['timezone']//60//60)
    sunrise = f"{datetime.utcfromtimestamp(weather['city']['sunrise'])+citytimezone}".split(' ')[-1]
    sunset = f"{datetime.utcfromtimestamp(weather['city']['sunset'])+citytimezone}".split(' ')[-1]
    result = f"{weather['city']['name']}\n☀ {sunrise}\n🌑 {sunset}"
    for hour in weather["list"]:
        weather_icon = hour['weather'][0]['icon']

        try:
            weather_icon = dn[weather_icon[-1]] + we[weather_icon[:2]]
        except KeyError:
            weather_icon = hour['weather'][0]['main']

        weather_description = hour['weather'][0]['description'].capitalize().replace(' ', "\u00A0")
        temp = hour['main']['temp']
        wind_speed = hour['wind']['speed']
        wind_deg = hour['wind']['deg']
        wind_deg_icon = de[0 if (d := round(int(wind_deg) / 45) * 45) == 360 else d]
        city_time = hour['dt_txt'].replace('-', '.')[:-3]
        date = ".".join(city_time.split()[0].split('.')[::-1])
        if date not in result:
            day = DayInfo(settings, date)
            result += f"\n\n<b>{date}</b> <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})"
        result += f"\n{city_time.split()[-1]} {weather_icon}<b>{temp:⠀>2.0f}°C 💨{wind_speed:.0f}м/с {wind_deg_icon}</b> <u>{weather_description}</u>."
    return result


"""buttons"""
def generate_buttons(buttons_data: list[dict]) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры из списка словарей
    """
    keyboard = [[InlineKeyboardButton(text=text, callback_data=data)
                 for text, data in row.items()]
                for row in buttons_data]
    return InlineKeyboardMarkup(keyboard=keyboard)

def mycalendar(chat_id: str | int, user_timezone: int, lang: str, YY_MM: list | tuple[int, int] = None) -> InlineKeyboardMarkup():
    """
    Создаёт календарь на месяц и возвращает inline клавиатуру
    """
    if YY_MM:
        YY, MM = YY_MM
    else:
        YY, MM = new_time_calendar(user_timezone)
    markup = InlineKeyboardMarkup()
    #  December (12.2022)
    # Пн Вт Ср Чт Пт Сб Вс
    markup.row(InlineKeyboardButton(f"{get_translate('months_name', lang)[MM-1]} ({MM}.{YY}) ({year_info(YY, lang)})",
                                    callback_data=f"generate month calendar {YY}"))
    week_day_list = get_translate("week_days_list", lang)
    markup.row(*[InlineKeyboardButton(day, callback_data="None") for day in week_day_list])

    # получаем из базы данных дни на которых есть событие
    SqlResult = SQL(f"""
        SELECT DISTINCT CAST(SUBSTR(date, 1, 2) as date) FROM root
        WHERE user_id={chat_id} AND isdel=0 AND date LIKE \"%.{MM:0>2}.{YY}\";""")
    beupdate = [x[0] for x in SqlResult]

    birthday = SQL(f"""
        SELECT DISTINCT CAST(SUBSTR(date, 1, 2) as date) FROM root
        WHERE user_id={chat_id} AND isdel=0 AND 
        status IN (\"🎉\", \"🎊\", \"📆\") AND date LIKE \"__.{MM:0>2}.____\";""")
    birthdaylist = [x[0] for x in birthday]

    # получаем сегодняшнее число
    today = now_time(user_timezone).day
    # получаем список дней
    for weekcalendar in monthcalendar(YY, MM):
        weekbuttons = []
        for day in weekcalendar:
            if day == 0:
                weekbuttons.append(InlineKeyboardButton("  ", callback_data="None"))
            else:
                tag_today = '#' if day == today else ''
                tag_event = '*' if day in beupdate else ''
                tag_birthday = '!' if day in birthdaylist else ''
                weekbuttons.append(InlineKeyboardButton(f"{tag_today}{day}{tag_event}{tag_birthday}",
                                                        callback_data=f"{f'0{day}' if len(str(day)) == 1 else day}."
                                                                      f"{f'0{MM}' if len(str(MM)) == 1 else MM}.{YY}"))
        markup.row(*weekbuttons)
    markup.row(*[InlineKeyboardButton(f"{day}", callback_data=f"{day}") for day in ('<<', '<', '⟳', '>', '>>')])
    return markup

def generate_month_calendar(user_timezone: int, lang: str, chat_id, YY) -> InlineKeyboardMarkup():
    """
    Создаёт календарь из месяцев на определённый год и возвращает inline клавиатуру
    """
    month_list = [x[0] for x in SQL(f"""
        SELECT DISTINCT CAST(SUBSTR(date, 4, 2) as date) FROM root
        WHERE user_id={chat_id} AND date LIKE "__.__.{YY}" AND isdel=0;
    """)] # Форматирование результата

    recurring_list = [x[0] for x in SQL(f"""
        SELECT DISTINCT CAST(SUBSTR(date, 4, 2) as date) FROM root
        WHERE user_id={chat_id} AND status IN ("🎉", "🎊", "📆") AND isdel=0;
    """)] # Форматирование результата

    nowMonth = now_time(user_timezone).month
    isNowMonth = lambda numM: numM == nowMonth

    months = get_translate("months_list", lang)

    result = []
    for row in months:
        result.append({})
        for nameM, numm in row:
            tag_today = "#" if isNowMonth(numm) else ""
            tag_event = "*" if numm in month_list else ""
            tag_birthday = "!" if numm in recurring_list else ""
            result[-1][f"{tag_today}{nameM}{tag_event}{tag_birthday}"] = f"generate calendar {YY} {numm}"

    markupL = [
        {f"{YY} ({year_info(YY, lang)})": "None"},
        *result,
        {"<<": f"generate month calendar {YY-1}", "⟳": "year now", ">>": f"generate month calendar {YY+1}"}
    ]
    return generate_buttons(markupL)

allmarkup = generate_buttons([
    {"➕": "event_add", "📝": "event_edit", "🚩": "event_status", "🗑": "event_del"}, # "🔘": "menu"
    {"🔙": "back", "<": "<<<", ">": ">>>", "✖": "message_del"}])
minimarkup = generate_buttons([{"🔙": "back", "✖": "message_del"}])
backmarkup = generate_buttons([{"🔙": "back"}])
delmarkup = generate_buttons([{"✖": "message_del"}])
databasemarkup = generate_buttons([{'Применить базу данных': 'set database'}])


"""Другое"""
callbackTab = '⠀⠀⠀'
backslash_n = "\n"

def ToHTML(text: str) -> str:
    return text.replace("<", '&lt;').replace(">", '&gt;').replace("'", '&#39;').replace('"', '&quot;')

def NoHTML(text: str) -> str:
    return text.replace("&lt;", '<').replace("&gt;", '>').replace("&#39;", "'").replace('&quot;', '"')

def markdown(text: str, status: str, suburl: bool | int = False) -> str:
    """
    Добавляем эффекты к событию по статусу
    """
    def OrderList(_text: str, num=0) -> str: # Нумерует каждую строчку
        lst = _text.splitlines()
        width = len(str(len(lst))) # Получаем длину отступа чтобы не съезжало
        # Заполняем с отступами числа + текст, а если двойной перенос строки то "⠀"
        return "\n".join(("0️⃣" * (width-len(str(num := num+1)))) + "⃣".join(str(num)) + "⃣" +
                         line if line not in ("", "⠀") else "⠀" for line in lst)

    def List(_text: str): # Заменяет \n на :black_small_square: (эмодзи Telegram)
        return "▪️" + _text.replace("\n", "\n▪️").replace("\n▪️⠀\n", "\n⠀\n")

    def Spoiler(_text: str):
        return f'<span class="tg-spoiler">{_text}</span>'

    def SubUrls(_text: str):
        la = lambda url: f'<a href="{url[0]}">{urlparse(url[0]).netloc}</a>'
        return re.sub(r'(http?s?://[^\"\'\n ]+)', la, _text) # r'(http?s?://\S+)'

    def Code(_text: str):
        return f'<code>{_text}</code>'

    # Сокращаем несколько подряд переносов строки
    text = re.sub(r'\n(\n*)\n', '\n⠀\n', text)

    if (suburl and status not in ('💻', '❌🔗')) or status == "🔗":
        text = SubUrls(text)
    if status == '🧮':
        return OrderList(text)
    elif status == '💻':
        return Code(text)
    elif status == '🗒':
        return List(text)
    elif status == '🪞':
        return Spoiler(text)
    else:
        return text

def get_translate(target: str, lang_iso_code: str) -> Any:
    """
    Взять перевод из файла lang.py c нужным языком
    """
    try:
        return translation[target][lang_iso_code]
    except KeyError:
        return translation[target]["en"]

class Cooldown:
    """
    Возвращает True если прошло больше времени
    MyCooldown = Cooldown(cooldown_time, {})
    MyCooldown.check(chat_id)
    """
    def __init__(self, cooldown_time_sec: int, cooldown_dict: dict):
        self.cooldown_time_sec = cooldown_time_sec
        self.cooldown_dict = cooldown_dict

    def check(self, key, update_dict=True):
        """
        :param key: Ключ по которому проверять словарь
        :param update_dict: Отвечает за обновление словаря
        Если True то после каждого обновления время будет обнуляться
        :return: (bool, int(time_difference))
        """
        t1 = time()
        result = True, 0
        try:
            if (localtime := (t1 - self.cooldown_dict[str(key)])) < self.cooldown_time_sec:
                result = False, int(self.cooldown_time_sec - int(localtime))
        except Exception as e:
            print(f"[func.py -> Cooldown.check] Exception \"{e}\"")
        if update_dict or result[0]:
            self.cooldown_dict[f'{key}'] = t1
        return result
CSVCooldown = Cooldown(1800, {})

def main_log(user_status: int, chat_id: int, action: str, text: str) -> None:
    if user_status == 2 or is_admin_id(chat_id):
        log_chat_id = f"\033[21m\033[34m{chat_id}\033[0m"
    elif user_status == 1:
        log_chat_id = f"\033[21m\033[32m{chat_id}\033[0m"
    else: # user_status == 0:
        log_chat_id = f"\033[21m{chat_id}\033[0m"
    log_text = f"{log_time_strftime()} {log_chat_id:<15} {action} " + text.replace(f"\n", f"\\n")
    print(f"{log_text:<90}", end="")


"""Генерация сообщений"""
@dataclass
class Event:
    """
    date: str = "now"
    event_id: int = 0
    status: str = ""
    text: str = ""
    deldate: str = "0"
    """
    date: str = "now"
    event_id: int = 0
    status: str = ""
    text: str = ""
    deldate: str = "0"

class MyMessage:
    """
    Класс для заполнения и форматирования сообщений по шаблону
    """
    def __init__(self,
                 settings: UserSettings,
                 date: str = "now",
                 event_list: tuple | list[Event, ...] = tuple(),
                 reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup()):
        if date == "now":
            date = now_time_strftime(settings.timezone)
        self.event_list = event_list
        self._date = date
        self._settings = settings
        self.text = ""
        self.reply_markup = deepcopy(reply_markup)

    def get_data(self,
                 *,
                 column_to_limit: str = "text",
                 column_to_order: str = sqlite_format_date('date'),
                 column_to_return: str = "event_id",
                 WHERE: str,
                 table: str = "root",
                 MAXLEN: int = 2500,
                 MAXEVENTCOUNT: int = 10,
                 direction: Literal["ASC", "DESC"] = "DESC",
                 prefix: str = "|"):
        """
        Получить [список (кортежей 'строк id',)] по страницам
        """
        data = get_values(column_to_limit=column_to_limit,
                          column_to_order=column_to_order,
                          column_to_return=column_to_return,
                          WHERE=WHERE,
                          table=table,
                          MAXLEN=MAXLEN,
                          MAXEVENTCOUNT=MAXEVENTCOUNT,
                          direction=direction)
        if data:
            if table == "root":
                first_message = [Event(*event) for event in SQL(f"""
                    SELECT date, event_id, status, text, isdel FROM root 
                    WHERE event_id IN ({data[0][0]}) AND ({WHERE})
                    ORDER BY {column_to_order} {direction};""")]
            else:
                first_message = [Event(text=event[0]) for event in SQL(f"""
                    SELECT {column_to_limit} FROM {table}
                    WHERE {column_to_order} IN ({data[0][0]}) AND ({WHERE})
                    ORDER BY {column_to_order} {direction};""")]

            if self._settings.direction == "⬆️":
                first_message = first_message[::-1]
            self.event_list = first_message

            count_columns = 5
            diapason_list = []
            for num, d in enumerate(data):  # Заполняем данные из диапазонов в список
                if int(f'{num}'[-1]) in (0, count_columns):  # Разделяем диапазоны в строчки по 5
                    diapason_list.append([])
                diapason_list[-1].append((num + 1, d[0]))  # Номер страницы, id

            if len(diapason_list[0]) != 1:  # Если страниц больше одной
                for i in range(count_columns - len(diapason_list[-1])):  # Заполняем пустые кнопки в последнем ряду до 5
                    diapason_list[-1].append((0, 0))

                [self.reply_markup.row(*[
                    InlineKeyboardButton(f'{numpage}', callback_data=f'{prefix}{numpage}|{vals}') if vals else
                    InlineKeyboardButton(f' ', callback_data=f'None') for numpage, vals in row])
                 for row in diapason_list[:8]] # Обрезаем до 8 строк кнопок чтобы не было слишком много строк кнопок
        return self

    def get_events(self, WHERE: str, values: list | tuple):
        """
        Возвращает события входящие в values с условием WHERE
        """
        try:
            direction = {"⬇️": "DESC", "⬆️": "ASC"}[self._settings.direction]
            res = [Event(*event) for event in SQL(f"""
                SELECT date, event_id, status, text, isdel FROM root
                WHERE event_id IN ({', '.join(values)}) AND ({WHERE})
                ORDER BY {sqlite_format_date('date')} {direction};""")]
        except Error as e:
            print(f"[func.py -> MyMessage.get_events] Error \"{e}\"")
            self.event_list = []
        else:
            if self._settings.direction != "⬆️":
                self.event_list = res
            else:
                self.event_list = res[::-1]
        return self

    def format(self,
               title: str = "{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n",
               args: str = "<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n",
               ending: str = "",
               if_empty: str = "🕸🕷  🕸",
               **kwargs):
        """
        Заполнение сообщения по шаблону
        \n ⠀
        \n {date}     - Date                                                                       ["0000.00.00"]
        \n {strdate}  - String Date                                                                ["0 January"]
        \n {weekday} - Week Date                                                                   ["Понедельник"]
        \n {reldate}  - Relatively Date                                                            ["Завтра"]
        \n ⠀
        \n {numd}     - Порядковый номер (циферный)                                                ["1 2 3"]
        \n {nums}     - Порядковый номер (смайлики)                                                ["1 2 3"]
        \n {event_id} - Event_id                                                                   ["1"]
        \n {status}   - Status                                                                     ["⬜️"]
        \n {markdown_text} - оборачивает текст в нужный тег по статусу                             ["<b>"]
        \n {markdown_text_nourlsub} - оборачивает текст в нужный тег по статусу без сокращения url ["</b>"]
        \n {text}     - Text                                                                       ["text"]
        \n {days_before_delete} - Дней до удаления

        :param title:    Заголовок
        :param args:     Повторяющийся шаблон
        :param ending:   Конец сообщения
        :param if_empty: Если результат запроса пустой
        :return:         message.text
        """
        dd = lambda deldate_: 30 if deldate_ in (0, 1) else (30 - (
            (datetime.now() + timedelta(hours=self._settings.timezone)) -
            datetime(*[int(x) for x in str(deldate_).split('.')][::-1])).days)

        day = DayInfo(self._settings, self._date)

        format_string = title.format(
            date=day.date,
            strdate=day.str_date,
            weekday=day.week_date,
            reldate=day.relatively_date) + "\n"

        if not self.event_list:
            format_string += if_empty
        else:
            for num, event in enumerate(self.event_list):
                day = DayInfo(self._settings, event.date)
                format_string += args.format(
                    date=day.date,
                    strdate=day.str_date,
                    weekday=day.week_date,
                    reldate=day.relatively_date,
                    numd=f"{num + 1}",
                    nums=f"{num + 1}️⃣",  # создание смайлика с цифрой
                    event_id=f"{event.event_id}",
                    status=event.status,
                    markdown_text=markdown(event.text, event.status, self._settings.sub_urls),
                    markdown_text_nourlsub=markdown(event.text, event.status),
                    days_before_delete=get_translate("deldate", self._settings.lang)(dd(event.deldate)),
                    **kwargs,
                    text=event.text
                ) + "\n"

        self.text = format_string+ending
        return self

    def send(self, chat_id: int) -> None:
        ...

    def edit(self,
             *,
             chat_id: int,
             message_id: int,
             only_markup: bool = False,
             markup: InlineKeyboardMarkup = None) -> None:
        """
        :param chat_id: chat_id
        :param message_id: message_id
        :param only_markup: обновить только клавиатуру self.reply_markup
        :param markup: обновить текст self.text и клавиатура markup
        """
        ...

def search(settings: UserSettings,
           chat_id: int,
           query: str,
           id_list: list | tuple = tuple(),
           page: int | str = 1) -> MyMessage:
    """
    :param settings: settings
    :param chat_id: chat_id
    :param query: поисковый запрос
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с поиском:
        search(settings=settings, chat_id=chat_id, query=query)
    Изменить страницу:
        search(settings=settings, chat_id=chat_id, query=query, id_list=id_list, page=page)
    TODO шаблоны для поиска
    """
    if not re.match(r'\S', query):
        generated = MyMessage(settings, reply_markup=delmarkup)
        generated.format(title=f'{get_translate("search", settings.lang)} {query}:\n',
                         if_empty=get_translate("request_empty", settings.lang))
        return generated

    re_day = re.compile(r"[#\b ]day=(\d{1,2})[\b]?")
    re_month = re.compile(r"[#\b ]month=(\d{1,2})[\b]?")
    re_year = re.compile(r"[#\b ]year=(\d{4})[\b]?")
    re_id = re.compile(r"[#\b ]id=(\d{,6})[\b]?")
    re_status = re.compile(r"[#\b ]status=(\S+)[\b]?")

    querylst = query.replace('\n', ' ').split()
    splitquery = " OR ".join(f"date LIKE '%{x}%' OR text LIKE '%{x}%'OR status LIKE '%{x}%' OR event_id LIKE '%{x}%'" for x in querylst)
    WHERE = f"(user_id = {chat_id} AND isdel == 0) AND ({splitquery})"

    generated = MyMessage(settings, reply_markup=delmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction])
    generated.format(title=f'{get_translate("search", settings.lang)} {query}:\n'
                           f'{"<b>"+get_translate("page", settings.lang)+f" {page}</b>{backslash_n}" if int(page) > 1 else ""}',
                     args="<b>{numd}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                     if_empty=get_translate("nothing_found", settings.lang))

    return generated

def week_event_list(settings: UserSettings,
                    chat_id: int,
                    id_list: list | tuple = tuple(),
                    page: int | str = 1) -> MyMessage:
    """
    :param settings: settings
    :param chat_id: chat_id
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с событиями в эту неделю:
        week_event_list(settings=settings, chat_id=chat_id)
    Изменить страницу:
        week_event_list(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"""
    (user_id={chat_id} AND isdel=0) AND (
        (
            {sqlite_format_date('date')} BETWEEN DATE('now') AND DATE('now', '+7 day')
        ) 
        OR 
        (
            (
                strftime('%m-%d', {sqlite_format_date('date')}) BETWEEN strftime('%m-%d', 'now') AND strftime('%m-%d', 'now', '+7 day')
            ) 
            AND status IN ('🎉', '🎊', '📆')
        )
        OR
        status IN ('🗞')
    )
    """
    generated = MyMessage(settings, reply_markup=delmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction="ASC")
    generated.format(title=f'{get_translate("week_events", settings.lang)}\n'
                           f'{"<b>"+get_translate("page", settings.lang)+f" {page}</b>{backslash_n}" if int(page) > 1 else ""}',
                     args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                     if_empty=get_translate("nothing_found", settings.lang))
    return generated

def deleted(settings: UserSettings,
            chat_id: int,
            id_list: list | tuple = tuple(),
            page: int | str = 1) -> MyMessage:
    """
    :param settings: settings
    :param chat_id: chat_id
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с корзиной:
        deleted(settings=settings, chat_id=chat_id)
    Изменить страницу:
        deleted(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"""user_id={chat_id} AND isdel!=0"""
    # Удаляем события старше 30 дней
    SQL(f"""DELETE FROM root WHERE isdel!=0 AND 
    (julianday('now') - julianday({sqlite_format_date("isdel")}) > 30);""", commit=True)


    generated = MyMessage(settings, reply_markup=generate_buttons([
        {"✖": "message_del", "❌ "+get_translate("delete_permanently", settings.lang): "event_del bin"},
        {"↩️ "+get_translate("recover", settings.lang): "event_recover bin"}]))

    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction])
    generated.format(title=f'{get_translate("basket", settings.lang)}\n'
                           f'{"<b>"+get_translate("page", settings.lang)+f" {page}</b>{backslash_n}" if int(page) > 1 else ""}',
                     args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({days_before_delete})\n{markdown_text}\n",
                     if_empty=get_translate("message_empty", settings.lang))
    return generated

def today_message(settings: UserSettings,
                  chat_id: int,
                  date: str,
                  id_list: list | tuple = tuple(),
                  page: int | str = 1) -> MyMessage:
    """
    :param settings: settings
    :param chat_id: chat_id
    :param date: дата у сообщения
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с сегодняшним днём:
        today_message(settings=settings, chat_id=chat_id, date=now_time_strftime(settings.timezone))
    Изменить страницу:
        today_message(settings=settings, chat_id=chat_id, date=date, id_list=id_list, page=page)
    """
    WHERE = f"user_id={chat_id} AND isdel=0 AND date='{date}'"
    generated = MyMessage(settings, date=date, reply_markup=allmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction])
    generated.format(title='{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n'
                           f'{"<b>"+get_translate("page", settings.lang)+f" {page}</b>{backslash_n}" if int(page) > 1 else ""}',
                     args="<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n",
                     if_empty=get_translate("nodata", settings.lang))

    # Добавить дополнительную кнопку для дней в которых есть праздники
    birthday = SQL(f"""
    SELECT DISTINCT date FROM root 
    WHERE isdel=0 AND user_id={chat_id} AND 
    (
        (
            status IN ('🎉', '🎊', '📆') AND
            date LIKE '{date[:-5]}.____'
        )
        OR
        (
            status IN ('🗞') AND
            strftime('%w', {sqlite_format_date('date')}) = CAST(strftime('%w', '{sqlite_format_date2(date)}') as TEXT)
        )
    );
    """)
    daylist = [x[0] for x in birthday if x[0] != date]
    if daylist:
        generated.reply_markup.row(InlineKeyboardButton("📅", callback_data=f"recurring"))
    return generated

def notifications(user_id_list: list | tuple[int | str, ...] = None,
                  id_list: list | tuple = tuple(),
                  page: int | str = 1,
                  message_id: int = -1,
                  markup: InlineKeyboardMarkup = None,
                  from_command: bool = False) -> None:
    """
    :param user_id_list: user_id_list
    :param id_list: Список из event_id
    :param page: Номер страницы
    :param message_id: message_id сообщения для изменения
    :param markup: markup для изменения сообщения
    :param from_command: Если True то сообщение присылается в любом случае

    Вызвать сообщение с будильником для всех:
        notifications()
    Вызвать сообщение для одного человека:
        notifications(user_id=[chat_id])
    Изменить страницу сообщения:
        notifications(user_id=[chat_id],
                      id_list=id_list,
                      page=page,
                      message_id=message_id,
                      markup=message.reply_markup)
    """
    user_id_list = user_id_list if user_id_list else [user_id[0] for user_id in SQL(
        f"SELECT user_id FROM settings WHERE notifications!=-1;")]
    for user_id in user_id_list:
        user_id = int(user_id)
        settings = UserSettings(user_id)

        WHERE = f"""
            (
                (
                    status IN ('🔔', '🔕') 
                    AND date='{now_time_strftime(settings.timezone)}'
                ) 
                OR 
                (
                    status IN ('🎉', '🎊', '📆')
                    AND {sqlite_format_date("date")} IN (
                        DATE('now'), 
                        DATE('now', '+1 day'),
                        DATE('now', '+2 day'), 
                        DATE('now', '+3 day'), 
                        DATE('now', '+7 day')
                    )
                )
            )
            AND isdel=0
        """

        generated = MyMessage(settings, reply_markup=delmarkup)
        if id_list:
            generated.get_events(WHERE=WHERE, values=id_list)
        else:
            generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction])
        if len(generated.event_list) or from_command:
            generated.format(title=(f'🔔 {get_translate("reminder", settings.lang)} 🔔\n'
                                    f'{"<b>" + get_translate("page", settings.lang) + f" {page}</b>{backslash_n}" if int(page) > 1 else ""}'),
                             args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                             if_empty=get_translate("message_empty", settings.lang))
            print(f"[func.py -> notifications]")
            try:
                if id_list:
                    generated.edit(chat_id=user_id, message_id=message_id, markup=markup)
                else:
                    generated.send(chat_id=user_id)
                if not from_command:
                    SQL(f"UPDATE root SET status='🔕' WHERE {WHERE} AND status='🔔';", commit=True)
            except ApiTelegramException:
                pass

def recurring(settings: UserSettings,
              date: str,
              chat_id: int,
              id_list: list | tuple = tuple(),
              page: int | str = 1):
    """
    :param settings: settings
    :param date: дата у сообщения
    :param chat_id: chat_id
    :param id_list: Список из event_id
    :param page: Номер страницы

    Вызвать сообщение с повторяющимися событиями:
        recurring(settings=settings, date=date, chat_id=chat_id)
    Изменить страницу:
        recurring(settings=settings, date=date, chat_id=chat_id, id_list=id_list, page=page)
    """
    WHERE = f"""
        isdel=0 AND user_id={chat_id} 
        AND 
        (
            (
                status IN ('🎉', '🎊', '📆')
                AND date LIKE '{date[:-5]}.____'
            )
            OR
            (
                status IN ('🗞') AND
                strftime('%w', {sqlite_format_date('date')}) = CAST(strftime('%w', '{sqlite_format_date2(date)}') as TEXT)
            )
        )
    """
    generated = MyMessage(settings=settings, date=date, reply_markup=backmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction], prefix="|!")
    generated.format(title='{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n'
                           f'{"<b>"+get_translate("page", settings.lang)+f" {page}</b>{backslash_n}" if int(page) > 1 else ""}',
                     args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                     if_empty=get_translate("nothing_found", settings.lang))
    return generated

def parse(chat_id, message_text, call_data):
    res = message_text.split('\n\n')[1:]
    if res[0].startswith("👀") or res[0].startswith("🕸"):
        return 0
    markup = InlineKeyboardMarkup()
    date = message_text.split(maxsplit=1)[0]

"""Проверки"""
limits = {
    "normal": (4000, 20),
    "premium": (8000, 40),
    "admin": (999999, 999)
}

def is_exceeded_limit(chat_id: int,
                      date: str,
                      limit: tuple[int, int] = (4000, 20),
                      difference: tuple[int, int] = (0, 0)) -> bool:
    """
    True если превышен лимит для пользователя
    """
    user_limit = SQL(f"""SELECT IFNULL(SUM(LENGTH(text)), 0), IFNULL(COUNT(date), 0) FROM root 
                         WHERE user_id={chat_id} AND date='{date}' AND isdel=0;""")[0]
    res = (user_limit[0] + difference[0]) >= limit[0] or (user_limit[1] + difference[1]) >= limit[1]
    return res

def is_admin_id(chat_id) -> bool:
    """
    Проверка на админа
    Админом могут быть только люди, чьи id записаны в config.admin_id
    """
    # or (int(SQL(f"SELECT user_status FROM settings WHERE user_id={chat_id};")[0][0]) == 2)
    return chat_id in config.admin_id

def write_table_to_str(file: StringIO, query: str, commit: bool = False, align: Literal["<", ">", "^"] = "<") -> None:
    """
    Наполнит файл file строковым представлением таблицы результата SQL(query)
    """
    table = [list(column) for column in SQL(query, commit=commit, column_names=True)]

    # Матрица максимальных длин и высот каждого столбца и строки
    w = [[max(len(line) for line in str(column).splitlines()) for column in row] for row in table]

    # Вычисляем максимальную ширину и высоту каждого столбца и строки
    widths = [max(column) for column in zip(*w)]


    sep = "+" + "".join(("-" * (i + 2)) + "+" for i in widths)  # Разделитель строк
    template = "|" + "".join(f" {{:{align}{_}}} |" for _ in widths)

    for n, row in enumerate(table):
        file.write(sep + "\n")
        indices = [i for i, column in enumerate(row) if len(str(column).split("\n")) > 1]

        if indices:
            first_line = row[:]
            for x in indices:
                first_line[x] = row[x].splitlines()[0]
            file.write(template.format(*first_line) + "\n")

            indents = [len(str(column).splitlines()) for column in row]
            max_lines = max(indents)
            for ml in range(1, max_lines):  # проходим по максимум новых строчек
                new_line = ["" for _ in indents]
                for i in indices: # получаем индексы многострочных ячеек
                    new_line[i] = str(row[i]).splitlines()[ml]
                file.write(template.format(*new_line) + ("\n" if ml < max_lines-1 else ""))

        else:
            file.write(template.format(*row))
        file.write("\n")
    file.write(sep)
