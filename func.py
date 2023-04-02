from datetime import datetime, timedelta, timezone
from sqlite3 import connect, Error # pip3.10 install --user sqlite3
from calendar import monthcalendar
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Literal
from copy import deepcopy
from time import time
import re

from requests import get # pip install requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from lang import translation
import config


"""sql"""
def SQL(Query: str, params: tuple = (), commit: bool = False):
    """
    Выполняет SQL запрос
    Пробовал через with, но оно не закрывало файл

    :param Query: Запрос
    :param params: Параметры запроса (необязательно)
    :param commit: Нужно ли сохранить изменения? (необязательно, по умолчанию False)
    :return: Результат запроса
    """
    connection = connect(config.database_path)
    cursor = connection.cursor()
    try:
        cursor.execute(Query, params)
        if commit: connection.commit()
        result = cursor.fetchall()
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
        self.lang, self.sub_urls, self.city, self.timezone, self.direction, self.user_status = self.get_user_settings()

    def get_user_settings(self):
        query = f"""SELECT lang, sub_urls, city, timezone, direction, user_status FROM settings WHERE user_id={self.user_id};"""
        try:
            return SQL(query)[0]
        except (Error, IndexError):
            print("Добавляю нового пользователя")
            SQL(f"INSERT INTO settings (user_id) VALUES ({self.user_id});", commit=True)
        return SQL(query)[0]

    def get_settings_markup(self):
        """
        Ставит настройки для пользователя chat_id
        """
        not_lang = "ru" if self.lang == "en" else "en"
        not_sub_urls = 1 if self.sub_urls == 0 else 0
        not_direction = "⬇️" if self.direction == "⬆️" else "⬆️"

        utz = self.timezone
        time_zone_dict = {}
        time_zone_dict.__setitem__(*('‹‹‹', f'settings timezone {utz - 1}') if utz > -11 else ('   ', 'None'))
        time_zone_dict[f'{utz}'] = 'settings timezone 3'
        time_zone_dict.__setitem__(*('›››', f'settings timezone {utz + 1}') if utz < 11 else ('   ', 'None'))

        markup = generate_buttons([{f"🗣 {self.lang}": f"settings lang {not_lang}",
                                    f"🔗 {bool(self.sub_urls)}": f"settings sub_urls {not_sub_urls}",
                                    f"↕️": f"settings direction {not_direction}"},
                                   time_zone_dict,
                                   {"✖": "message_del"}])
        return self.lang, self.sub_urls, self.city, utz, self.direction, markup

def create_tables() -> None:
    """
    Создание нужных таблиц
    """
    try:
        SQL("""SELECT * FROM root LIMIT 1""")
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

    try:
        SQL("""SELECT * FROM settings LIMIT 1""")
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
                    user_max_event_id INT  DEFAULT (1)
                );""", commit=True)
create_tables()

def create_event(user_id: int, date: str, text: str) -> bool:
    """Создание события"""
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
        print(f"Произошла ошибка в функции create_event: '{e}'  arg: {user_id=}, {date=}, {text=}")
        return False

def get_values(column_to_limit: str, column_to_order: str, WHERE: str, table: str, MAXLEN: int = 3500, MAXEVENTCOUNT: int = 10, direction: Literal["ASC", "DESC"] = "DESC"):
    """
    :param table:           Название таблицы
    :param column_to_limit: Столбец для ограничения
    :param column_to_order: Столбец для сортировки (например id)
    :param WHERE:           Условие выбора строк из таблицы
    :param MAXLEN:          Максимальная длинна символов в одном диапазоне
    :param MAXEVENTCOUNT:   Максимальное количество строк в диапазоне
    :param direction:       Направление сбора строк ("ASC" or "DESC")
    """
    column = "end_id" if direction == "DESC" else "start_id"
    Query = f"""
WITH numbered_table AS (
  SELECT ROW_NUMBER() OVER (ORDER BY {column_to_order} {direction}) AS row_num, {column_to_order} AS order_column, LENGTH({column_to_limit}) as len
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
    data = SQL(Query)
    return data

def check_bells(settings: UserSettings, chat_id): # TODO доделать check_bells
    date = now_time_strftime(settings)
    res = SQL(f"""SELECT event_id, user_id, text, status FROM root
               WHERE ((date = '{date}' AND status = '⏰')
               OR (substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2) 
                   BETWEEN DATE('now') AND DATE('now', '+7 day') AND (status = '🎉' OR status = '🎊'))) 
               AND isdel = 0 AND user_id = {chat_id}""")
    alarm, holiday = get_translate("alarm", settings.lang)
    for event in res:
        event_id, user_id, text, status = event
        if status == '⏰':
            text = f'{alarm}\n<b>{event_id}.</b>🔕\n{text}'
        if status in ('🎉', '🎊'):
            text = f'{holiday}\n<b>{event_id}.</b>{status} {day_info(settings, date)}\n{text}'
        try:
            SQL(f"UPDATE root SET status = '🔕' WHERE user_id = {chat_id} AND event_id = {event_id} AND date = '{date}' AND status = '⏰';", commit=True)
        except Error as e:
            print(f"Произошла ошибка в функции check_bells: '{e}'")
        return text


"""time"""
def now_time(settings: UserSettings):
    return datetime.now()+timedelta(hours=settings.timezone)

def now_time_strftime(settings: UserSettings):
    return now_time(settings).strftime("%d.%m.%Y")

def log_time_strftime(log_timezone: int = config.hours_difference):
    return (datetime.now()+timedelta(hours=log_timezone)).strftime("%Y.%m.%d %H:%M:%S")

def new_time_calendar(settings: UserSettings):
    date = now_time(settings)
    return [date.year, date.month]

def year_info(settings: UserSettings, year):
    result = ""
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        result += get_translate("leap", settings.lang)
    else:
        result += get_translate("not_leap", settings.lang)
    result += ' '
    result += ("🐀", "🐂", "🐅", "🐇", "🐲", "🐍", "🐴", "🐐", "🐒", "🐓", "🐕", "🐖")[(year - 4) % 12]
    return result

def get_week_number(YY, MM, DD): # TODO добавить номер недели в календари
    return datetime(YY, MM, DD).isocalendar()[1]

class day_info:
    def __init__(self, settings, date):
        today, tomorrow, day_after_tomorrow, yesterday, day_before_yesterday, after, ago, Fday = get_translate("relative_date_list", settings.lang)
        x = now_time(settings)
        x = datetime(x.year, x.month, x.day)
        y = datetime(*[int(x) for x in date.split('.')][::-1])

        day_diff = (y - x).days
        if day_diff == 0: day_diff = f'{today}'
        elif day_diff == 1: day_diff = f'{tomorrow}'
        elif day_diff == 2: day_diff = f'{day_after_tomorrow}'
        elif day_diff == -1: day_diff = f'{yesterday}'
        elif day_diff == -2: day_diff = f'{day_before_yesterday}'
        elif day_diff > 2: day_diff = f'{after} {day_diff} {Fday(day_diff)}'
        else: day_diff = f'{-day_diff} {Fday(day_diff)} {ago}'

        week_days = get_translate("week_days_list_full", settings.lang)
        month_list = get_translate("months_name2", settings.lang)

        self.date = date
        self.str_date = f"{y.day} {month_list[y.month - 1]}"
        self.week_date = week_days[y.weekday()]
        self.relatively_date = day_diff


"""weather"""
def cache_decorator(cache_time_sec: int = 32):
    """
    Кеширует значений погоды для города
    не даёт запрашивать погоду для одного города чаще чем в 32 секунды
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

@cache_decorator(60)
def weather_in(settings: UserSettings, city: str): # TODO защита от спам атак
    """
    Возвращает текущую погоду по городу city
    """
    print(f"weather in {city}")
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

@cache_decorator(3600)
def forecast_in(settings: UserSettings, city: str):
    print(f"forecast in {city}")
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
            result += f"\n\n<b>{date}</b> {day_info(settings, date)}"
        result += f"\n{city_time.split()[-1]} {weather_icon}<b>{temp:⠀>2.0f}°C 💨{wind_speed:.0f}м/с {wind_deg_icon}</b> <u>{weather_description}</u>."
    return result


"""buttons"""
def generate_buttons(buttons_data):
    keyboard = [[InlineKeyboardButton(text, callback_data=data) for text, data in row.items()] for row in buttons_data]
    return InlineKeyboardMarkup(keyboard)

def mycalendar(settings: UserSettings, YY_MM, chat_id) -> InlineKeyboardMarkup():
    """Создаёт календарь на месяц и возвращает кнопки"""
    YY, MM = YY_MM
    markup = InlineKeyboardMarkup()
    #  December (12.2022)
    # Пн Вт Ср Чт Пт Сб Вс
    markup.row(InlineKeyboardButton(f"{get_translate('months_name', settings.lang)[MM-1]} ({MM}.{YY}) ({year_info(settings, YY)})",
                                    callback_data=f"generate_month_calendar {YY}"))
    week_day_list = get_translate("week_days_list", settings.lang)
    markup.row(*[InlineKeyboardButton(day, callback_data="None") for day in week_day_list])

    # получаем из базы данных дни на которых есть событие
    SqlResult = SQL(f'SELECT DISTINCT CAST(SUBSTR(date, 1, 2) as date) FROM root '
                    f'WHERE user_id = {chat_id} AND date LIKE "%.{MM:0>2}.{YY}" AND isdel = 0;') # SUBSTRING(date, 1, 2)
    beupdate = [x[0] for x in SqlResult]

    birthday = SQL(f'SELECT DISTINCT CAST(SUBSTR(date, 1, 2) as date) FROM root '
                   f'WHERE date LIKE "__.{MM:0>2}.{YY}" AND isdel = 0 AND '
                   f'user_id = {chat_id} AND status IN ("🎉", "🎊")')
    birthdaylist = [x[0] for x in birthday]

    # получаем сегодняшнее число
    today = now_time(settings).day
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
                weekbuttons.append(InlineKeyboardButton(f"{tag_today}{day}{tag_event}{tag_birthday}", callback_data=f"{f'0{day}' if len(str(day)) == 1 else day}.{f'0{MM}' if len(str(MM)) == 1 else MM}.{YY}"))
        markup.row(*weekbuttons)
    markup.row(*[InlineKeyboardButton(f"{day}", callback_data=f"{day}") for day in ('<<', '<', '⟳', '>', '>>')])
    return markup

def generate_month_calendar(settings: UserSettings, chat_id, YY) -> InlineKeyboardMarkup():
    """Создаёт календарь на год и возвращает кнопки"""
    SqlResult = SQL(f'SELECT DISTINCT CAST(SUBSTR(date, 4, 2) as date) FROM root '
                    f'WHERE user_id = {chat_id} AND date LIKE "__.__.{YY}" AND isdel = 0;')
    month_list = [x[0] for x in SqlResult] # Форматирование результата
    nowMonth = now_time(settings).month
    isNowMonth = lambda numM: numM == nowMonth

    months = get_translate("months_list", settings.lang)

    result = []
    for row in months:
        result.append({})
        for nameM, numm in row:
            tag_today = "#" if isNowMonth(numm) else ""
            tag_event = "*" if numm in month_list else ""
            tag_birthday = '!' if SQL(f'SELECT status FROM root WHERE date LIKE "__.{numm:0>2}.{YY}" AND isdel = 0 AND user_id = {chat_id} AND status IN ("🎉", "🎊") LIMIT 1') else ''
            result[-1][f'{tag_today}{nameM}{tag_event}{tag_birthday}'] = f'generate_calendar {YY} {numm}'

    markupL = [
        {f"{YY} ({year_info(settings, YY)})": "None"},
        *result,
        {"<<": f"generate_month_calendar {YY-1}", "⟳": "year now", ">>": f"generate_month_calendar {YY+1}"}
    ]
    markup = generate_buttons(markupL)
    return markup

allmarkup = generate_buttons([
    {"➕": "event_add", "📝": "event_edit", "🚩": "event_status", "🗑": "event_del"}, # "🔘": "menu"
    {"🔙": "back", "<": "<<<", ">": ">>>", "✖": "message_del"}])
minimarkup = generate_buttons([{"🔙": "back", "✖": "message_del"}])
backmarkup = generate_buttons([{"🔙": "back"}])
delmarkup = generate_buttons([{"✖": "message_del"}])
databasemarkup = generate_buttons([{'Применить базу данных': 'set database'}])


"""Другое"""
callbackTab = '⠀⠀⠀'

def ToHTML(text):
    return text.replace("<", '&lt;').replace(">", '&gt;').replace("'", '&#39;').replace('"', '&quot;')

def NoHTML(text):
    return text.replace("&lt;", '<').replace("&gt;", '>').replace("&#39;", "'").replace('&quot;', '"')

def markdown(text: str, status: str, suburl=False) -> str:
    """Добавляем эффекты к событию по статусу"""
    def OrderList(_text: str, n=0) -> str: # Нумерует каждую строчку
        lst = _text.splitlines()
        width = len(str(len(lst))) # Получаем длину отступа чтобы не съезжало
        # Заполняем с отступами числа + текст, а если двойной перенос строки то "⠀"
        return "\n".join(("0️⃣" * (width-len(str(n := n+1)))) + "⃣".join(str(n)) + "⃣" + t if t not in ("", "⠀") else "⠀" for t in lst)

    def List(_text: str): # Заменяет \n на :black_small_square: (эмодзи Telegram)
        return "▪️" + _text.replace("\n", "\n▪️").replace("\n▪️⠀\n", "\n⠀\n")

    def Spoiler(_text: str):
        return f'<span class="tg-spoiler">{_text}</span>'

    def SubUrls(_text: str):
        la = lambda url: f'<a href="{url[0]}">{urlparse(url[0]).netloc}</a>'
        return re.sub(r'(http?s?://\S+)', la, _text)

    def Code(_text: str):
        return f'<code>{_text}</code>'

    text = text.replace('\n\n', '\n⠀\n')
    if suburl and status not in ('💻', ):
        text = SubUrls(text)
    if status == '🧮':
        return OrderList(text)
    elif status == '💻':
        return Code(text)
    elif status == '🗒':
        return List(text)
    elif status == '🪞':
        return Spoiler(text)
    else: return text

def get_translate(target: str, lang_iso_code: str) -> str:
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
            print(f'Cooldown.check {e}')
        if update_dict or result[0]:
            self.cooldown_dict[f'{key}'] = t1
        return result
CSVCooldown = Cooldown(1800, {})

def main_log(settings: UserSettings, chat_id: int, text: str, action: str):
    log_chat_id = (f"\033[21m{chat_id}\033[0m" if settings.user_status == 0
                   else (f"\033[21m\033[32m{chat_id}\033[0m" if settings.user_status == 1
                         else f"\033[21m\033[34m{chat_id}\033[0m"))
    print(f'{log_time_strftime()} {log_chat_id.ljust(15)} {action} {text.replace(f"{chr(92)}n", f"{chr(92)}{chr(92)}n")}')  # {chr(92)} = \ (escape sequences)


"""Генерация сообщений"""
@dataclass()
class Event:
    """
    date: str
    event_id: int
    status: str
    text: str
    """
    date: str = "now"
    event_id: int = 0
    status: str = ""
    text: str = ""

class MyMessage:
    def __init__(self, settings: UserSettings, date: str = "now", event_list: tuple | list[Event, ...] = tuple(), reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup()):
        if date == "now":
            date = now_time_strftime(settings)
        self._event_list = event_list
        self._date = date
        self._settings = settings
        self.text = ""
        self.reply_markup = deepcopy(reply_markup)

    def get_data(self, *, column_to_limit: str = "text", column_to_order: str = "event_id", WHERE: str, table: str = "root", MAXLEN: int = 2500, MAXEVENTCOUNT: int = 10, direction: Literal["ASC", "DESC"] = "DESC"):
        data = get_values(column_to_limit, column_to_order, WHERE, table, MAXLEN, MAXEVENTCOUNT, direction)
        if data:
            if table == "root":
                first_message = [Event(*event) for event in SQL(f'SELECT date, event_id, status, text FROM root WHERE ({WHERE}) AND event_id IN ({data[0][0]});')]
            else:
                first_message = [Event(text=event[0]) for event in SQL(f'SELECT {column_to_limit} FROM {table} WHERE ({WHERE}) AND {column_to_order} IN ({data[0][0]});')]

            if self._settings.direction != "⬆️":
                first_message = first_message[::-1]
            self._event_list = first_message


            diapason_list = []
            for n, data in enumerate(data):  # Заполняем данные из диапазонов в список
                if int(f'{n}'[-1]) in (0, 5):  # Разделяем диапазоны в строчки по 5
                    diapason_list.append([])
                diapason_list[-1].append((n + 1, data[0]))  # Номер страницы, начальное id, конечное id

            if len(diapason_list[0]) != 1:  # Если страниц больше одной
                for i in range(5 - len(diapason_list[-1])):  # Заполняем пустые кнопки в последнем ряду до 5
                    diapason_list[-1].append((0, 0))

                [self.reply_markup.row(*[
                    InlineKeyboardButton(f'{numpage}', callback_data=f'|{vals}') if vals else
                    InlineKeyboardButton(f' ', callback_data=f'None') for numpage, vals in row]) for row in diapason_list[:8]]
                # Образаем до 8 строк кнопок чтобы не было ошибки

        return self

    def get_events(self, WHERE: str, values: list | tuple):
        """Возвращает события в диапазоне с условием WHERE"""
        try:
            res = [Event(*event) for event in SQL(f"SELECT date, event_id, status, text FROM root WHERE {WHERE} AND event_id IN ({', '.join(values)});")]
        except Error as e:
            print(f'Ошибка в get_text_in_diapason: {e}')
            self._event_list = []
        else:
            if self._settings.direction == "⬆️":
                self._event_list = res
            else:
                self._event_list = res[::-1]
        return self

    def format(self, title: str = "{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n", args: str = "<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n", ending: str = "", if_empty: str = "🕸🕷  🕸"):
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

        :param title:    Заголовок
        :param args:     Повторяющийся шаблон
        :param ending:   Конец сообщения
        :param if_empty: Если результат запроса пустой
        :return:         message.text
        """
        day = day_info(self._settings, self._date)

        format_string = title.format(
            date=day.date,
            strdate=day.str_date,
            weekday=day.week_date,
            reldate=day.relatively_date) + "\n"

        if not self._event_list:
            format_string += if_empty
        else:
            for n, event in enumerate(self._event_list):
                day = day_info(self._settings, event.date)
                format_string += args.format(
                    date=day.date,
                    strdate=day.str_date,
                    weekday=day.week_date,
                    reldate=day.relatively_date,
                    numd=f"{n + 1}",
                    nums=f"{n + 1}️⃣",  # создание смайлика с цифрой
                    event_id=f"{event.event_id}",
                    status=event.status,
                    markdown_text=markdown(event.text, event.status, self._settings.sub_urls),
                    markdown_text_nourlsub=markdown(event.text, event.status),
                    text=event.text
                ) + "\n"

        self.text = format_string+ending
        return self

def search(settings: UserSettings, chat_id: int, query: str, id_list: list | tuple = tuple()):
    if not re.match(r'\S', query):
        text = get_translate("request_empty", settings.lang)
        return text, delmarkup

    querylst = query.replace('\n', ' ').split()
    splitquery = " OR ".join(f"date LIKE '%{x}%' OR text LIKE '%{x}%'OR status LIKE '%{x}%' OR event_id LIKE '%{x}%'" for x in querylst)
    WHERE = f"""(user_id = {chat_id} AND isdel == 0) AND ({splitquery})"""

    generated = MyMessage(settings, reply_markup=delmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction])
    generated.format(title=f'{get_translate("search", settings.lang)} {query}:\n',
                     args="<b>{numd}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                     if_empty=get_translate("nothing_found", settings.lang))

    return generated

def week_event_list(settings: UserSettings, chat_id, id_list: list | tuple = tuple()):
    WHERE = f"""(user_id = {chat_id} AND isdel = 0)
                AND (substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2) 
                BETWEEN DATE('now') AND DATE('now', '+7 day'))"""
    generated = MyMessage(settings, reply_markup=delmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction="ASC")
    generated.format(title=f'{get_translate("week_events", settings.lang)}\n',
                     args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                     if_empty=get_translate("nothing_found", settings.lang))
    return generated

def deleted(settings: UserSettings, chat_id, id_list: list | tuple = tuple()):
    WHERE = f"""user_id = {chat_id} AND isdel != 0"""
    # Удаляем события старше MAXTIME дня
    SQL(f"""DELETE FROM root WHERE isdel != 0 AND user_id = {chat_id} AND julianday('now') - 
    julianday(substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)) > {7};""", commit=True)

    generated = MyMessage(settings, reply_markup=delmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction])
    generated.format(title=f'{get_translate("basket", settings.lang)}\n',
                     args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                     if_empty=get_translate("message_empty", settings.lang))
    return generated

def today_message(settings: UserSettings, chat_id, date: str, id_list: list | tuple = tuple()):
    WHERE = f"user_id = {chat_id} AND isdel = 0 AND date = '{date}'"
    generated = MyMessage(settings, date=date, reply_markup=allmarkup)
    if id_list:
        generated.get_events(WHERE=WHERE, values=id_list)
    else:
        generated.get_data(WHERE=WHERE, direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction])
    generated.format(title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n",
                     args="<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n",
                     if_empty=get_translate("nodata", settings.lang))
    return generated

"""Проверки"""
limits = {
    "normal": (4000, 20),
    "premium": (8000, 40),
    "admin": (999999, 999)
}

def is_exceeded_limit(chat_id: int, date: str, limit: tuple[int, int] = (4000, 20), difference: tuple[int, int] = (0, 0)) -> bool:
    """True если превышен лимит"""
    user_limit = SQL(f"""SELECT IFNULL(SUM(LENGTH(text)), 0), IFNULL(COUNT(date), 0) FROM root WHERE user_id={chat_id} AND date='{date}' AND isdel=0;""")[0]
    res = (user_limit[0] + difference[0]) >= limit[0] or (user_limit[1] + difference[1]) >= limit[1]
    return res

def is_admin_id(chat_id):
    return chat_id in config.admin_id
