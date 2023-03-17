from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta, timezone
from calendar import monthcalendar
from urllib.parse import urlparse
from lang import translation
from copy import deepcopy
from sqlite3 import Error
from requests import get # pip install requests
from time import time
import sqlite3 # pip3.10 install --user sqlite3
import config
import re

def SQL(Query: str, params: tuple = (), commit: bool = False):
    """Выполняет SQL запрос"""
    with sqlite3.connect(config.database_path) as connection:
        cursor = connection.cursor()
        cursor.execute(Query, params)
        if commit: connection.commit()
        result = cursor.fetchall()
    return result

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

def create_event(user_id: int, date: str, text: str) -> bool:
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

class UserSettings:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.lang, self.sub_urls, self.city, self.timezone, self.direction, self.user_status = self.get_user_settings()

    def get_user_settings(self):
        query = f"""SELECT lang, sub_urls, city, timezone, direction, user_status FROM settings WHERE user_id={self.user_id};"""
        try:
            return SQL(query)[0]
        except (Error, IndexError) as e:
            print("Добавляю нового пользователя")
            SQL(f"""INSERT INTO settings (user_id) VALUES ({self.user_id});""", commit=True)
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

def get_diapason(WHERE: str, reply_markup=InlineKeyboardMarkup(), MAXLEN=3500, MAXEVENTCOUNT=10) -> tuple[int, int, InlineKeyboardMarkup]:
    """
    Возвращает первый диапазон, чтобы показать первую страницу
    и reply_markup
    """
    try:
        diapason = SQL(f"""
WITH numbered_root AS (
  SELECT ROW_NUMBER() OVER (ORDER BY event_id DESC) AS row_num, event_id, LENGTH(text) as len
  FROM root
  WHERE {WHERE}
),
temp_table AS (
  SELECT numbered_root.row_num, numbered_root.event_id, numbered_root.len,
    numbered_root.event_id AS end_id, numbered_root.len AS sum_len,
    1 AS group_id,
    1 AS event_count
  FROM numbered_root WHERE numbered_root.row_num = 1
  UNION ALL
  SELECT
    numbered_root.row_num, numbered_root.event_id, numbered_root.len,
    CASE WHEN temp_table.sum_len + numbered_root.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.end_id ELSE numbered_root.event_id END AS end_id,
    CASE WHEN temp_table.sum_len + numbered_root.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.sum_len + numbered_root.len ELSE numbered_root.len END AS sum_len,
    CASE WHEN temp_table.sum_len + numbered_root.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.group_id ELSE temp_table.group_id + 1 END AS group_id,
    CASE WHEN temp_table.sum_len + numbered_root.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} THEN temp_table.event_count + 1 ELSE 1 END AS event_count
  FROM numbered_root JOIN temp_table ON numbered_root.row_num = temp_table.row_num + 1
)
SELECT MIN(numbered_root.event_id) AS start_id, MAX(temp_table.end_id) AS end_id, SUM(numbered_root.len) AS sum_len
FROM numbered_root
JOIN temp_table ON numbered_root.row_num = temp_table.row_num
GROUP BY temp_table.group_id;
""")

        if not diapason:
            # print('Вызываю Error в функции get_diapason: response is empty')
            raise Error
        diapason_list = []
        for n, data in enumerate(diapason): # Заполняем данные из диапазонов в список
            start_id, end_id, _ = data
            if int(f'{n}'[-1]) in (0, 5): # Разделяем диапазоны в строчки по 5
                diapason_list.append([])
            diapason_list[-1].append((n + 1, start_id, end_id)) # Номер страницы, начальное id, конечное id

        newmarkup = deepcopy(reply_markup) # Копируем старые и дополняем их новыми кнопками
        if len(diapason_list[0]) != 1: # Если страниц больше одной

            for i in range(5 - len(diapason_list[-1])): # Заполняем пустые кнопки в последнем ряду до 5
                diapason_list[-1].append((0, 0, 0))

            [newmarkup.row(*[
                InlineKeyboardButton(f'{page[0]}', callback_data=f'get_page({page[1]}, {page[2]})') if page[0] else
                InlineKeyboardButton(f' ', callback_data=f'None') for page in row]) for row in diapason_list[:8]]
            # Образаем до 8 строк кнопок чтобы не было ошибки
        return diapason[0][0], diapason[0][1], newmarkup
    except Error as e:
        #print(f'Произошла ошибка в функции get_diapason: "{e}"')
        return 0, 0, reply_markup

def get_text_in_diapason(settings: UserSettings, start_id, end_id, SELECT, WHERE: str) -> list[tuple]:
    """Возвращает события в диапазоне с условием WHERE"""
    try:
        res = SQL(f"""SELECT {SELECT} FROM root WHERE {WHERE} AND (event_id BETWEEN {start_id} AND {end_id});""")
    except Error as e:
        print(f'Ошибка в get_text_in_diapason: {e}')
        return [()]
    else:
        if settings.direction == "⬆️":
            return res
        else:
            return res[::-1]

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
            text = f'{holiday}\n<b>{event_id}.</b>{status} {okonchanie(settings, date)}\n{text}'
        try:
            SQL(f"UPDATE root SET status = '🔕' WHERE user_id = {chat_id} AND event_id = {event_id} AND date = '{date}' AND status = '⏰';", commit=True)
        except Error as e:
            print(f"Произошла ошибка в функции check_bells: '{e}'")
        return text









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

def get_translate(target: str, lang_iso_code: str):
    try:
        return translation[target][lang_iso_code]
    except KeyError:
        return translation[target]["en"]

def now_time(settings: UserSettings):
    return datetime.now()+timedelta(hours=settings.timezone) # TODO ???

def now_time_strftime(settings: UserSettings):
    return now_time(settings).strftime("%d.%m.%Y")

def log_time_strftime(log_timezone: int = config.hours_difference):
    return (datetime.now()+timedelta(hours=log_timezone)).strftime("%Y.%m.%d %H:%M:%S")

def new_time_calendar(settings: UserSettings):
    date = now_time(settings)
    return [date.year, date.month]

def generate_buttons(buttons_data):
    keyboard = [[InlineKeyboardButton(text, callback_data=data) for text, data in row.items()] for row in buttons_data]
    return InlineKeyboardMarkup(keyboard)

def ToHTML(text):
    return text.replace("<", '&lt;').replace(">", '&gt;').replace("'", '&#39;').replace('"', '&quot;')

def NoHTML(text):
    return text.replace("&lt;", '<').replace("&gt;", '>').replace("&#39;", "'").replace('&quot;', '"')

def okonchanie(settings: UserSettings, date: str) -> str:
    today, tomorrow, day_after_tomorrow, yesterday, day_before_yesterday, after, ago, Fday = get_translate("relative_date_list", settings.lang)
    x = now_time(settings)
    x = datetime(x.year, x.month, x.day)
    y = datetime(*[int(x) for x in date.split('.')][::-1])
    day_diff = (y - x).days
    if day_diff == 0: day_diff = f'({today})'
    elif day_diff == 1: day_diff = f'({tomorrow})'
    elif day_diff == 2: day_diff = f'({day_after_tomorrow})'
    elif day_diff == -1: day_diff = f'({yesterday})'
    elif day_diff == -2: day_diff = f'({day_before_yesterday})'
    elif day_diff > 2: day_diff = f'({after} {day_diff} {Fday(day_diff)})'
    else: day_diff = f'({-day_diff} {Fday(day_diff)} {ago})'
    week_days = get_translate("week_days_list_full", settings.lang)
    month_list = get_translate("months_name2", settings.lang)
    return f"<u><i>{y.day} {month_list[y.month-1]} {week_days[y.weekday()]}</i></u> {day_diff}"

def year_info(settings: UserSettings, year):
    result = ""
    if year % 400 == 0 or (year % 4 == 0 and year % 100 != 0):
        result += get_translate("leap", settings.lang)
    else:
        result += get_translate("not_leap", settings.lang)
    result += ', '
    result += ("🐀", "🐂", "🐅", "🐇", "🐲", "🐍", "🐴", "🐐", "🐒", "🐓", "🐕", "🐖")[(year - 4) % 12]
    return result

def get_week_number(YY, MM, DD): # TODO добавить номер недели в календари
    return datetime(YY, MM, DD).isocalendar()[1]

def mycalendar(settings: UserSettings, data, chat_id) -> InlineKeyboardMarkup():
    """Создаёт календарь и возвращает """
    YY, MM = data
    markup = InlineKeyboardMarkup()
    #  December (12.2022)
    # Пн Вт Ср Чт Пт Сб Вс
    markup.row(InlineKeyboardButton(f"{get_translate('months_name', settings.lang)[MM-1]} ({MM}.{YY}) ({year_info(settings, YY)})",
                                    callback_data=f"generate_month_calendar {YY}"))
    week_day_list = get_translate("week_days_list", settings.lang)
    markup.row(*[InlineKeyboardButton(day, callback_data="None") for day in week_day_list])

    # получаем из базы данных дни на которых есть событие
    SqlResult = SQL(f'SELECT DISTINCT CAST(SUBSTR(date, 1, 2) as date) FROM root WHERE user_id = {chat_id} AND date LIKE "%{MM}.{YY}" AND isdel = 0;') # SUBSTRING(date, 1, 2)
    beupdate = [x[0] for x in SqlResult]
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
                weekbuttons.append(InlineKeyboardButton(f"{tag_today}{day}{tag_event}", callback_data=f"{f'0{day}' if len(str(day)) == 1 else day}.{f'0{MM}' if len(str(MM)) == 1 else MM}.{YY}"))
        markup.row(*weekbuttons)
    markup.row(*[InlineKeyboardButton(f"{day}", callback_data=f"{day}") for day in ('<<', '<', '⟳', '>', '>>')])
    return markup

def generate_month_calendar(settings: UserSettings, chat_id, message_id, YY) -> InlineKeyboardMarkup():
    SqlResult = SQL(f"""SELECT DISTINCT CAST(SUBSTR(date, 4, 2) as date) FROM root
                       WHERE user_id = {chat_id} AND date LIKE "__.__.{YY}" AND isdel = 0;""")
    month_list = [x[0] for x in SqlResult] # Форматирование результата
    nowMonth = now_time(settings).month
    isNowMonth = lambda numM: numM == nowMonth

    months = get_translate("months_list", settings.lang)

    result = [{f'{"#" if isNowMonth(numm) else ""}{nameM}{"*" if numm in month_list else ""}': f'generate_calendar {YY} {numm}'
               for nameM, numm in row} for row in months]
    markupL = [
        {f"{YY} ({year_info(settings, YY)})": "None"},
        *result,
        {"<<": f"generate_month_calendar {YY-1}", "⟳": "year now", ">>": f"generate_month_calendar {YY+1}"}
    ]
    markup = generate_buttons(markupL)
    return markup

def is_admin_id(chat_id):
    return chat_id in config.admin_id

def search(settings: UserSettings, chat_id, query, start_id=0, end_id=0) -> tuple[str, InlineKeyboardMarkup]:
    newmarkup = InlineKeyboardMarkup()
    if not re.match(r'\S', query):
        text = get_translate("request_empty", settings.lang)
        return text, delmarkup
    query = query.replace('\n', ' ')
    querylst = query.split()
    splitquery = " OR ".join(f"date LIKE '%{x}%' OR text LIKE '%{x}%'OR status LIKE '%{x}%' OR event_id LIKE '%{x}%'" for x in querylst)
    WHERE = f"""(user_id = {chat_id} AND isdel == 0) AND ({splitquery})"""
    SELECT = """event_id, date, text, status"""
    if not start_id and not end_id:
        start_id, end_id, newmarkup = get_diapason(WHERE=WHERE, reply_markup=delmarkup, MAXLEN=2500, MAXEVENTCOUNT=15)
    sql_res = get_text_in_diapason(settings, start_id, end_id, SELECT=SELECT, WHERE=WHERE)
    text = f'{get_translate("search", settings.lang)} {query}:\n\n'
    counter = 0
    for EVENTID, DATE, TEXT, STATUS in sql_res:
        counter += 1
        TEXT = markdown(TEXT, STATUS, settings.sub_urls)
        text += f'<b>{DATE}</b>.<b>{EVENTID}.{STATUS}</b> <u>{okonchanie(settings, DATE)}</u>\n{TEXT}\n\n'
    if not counter:
        text += get_translate("nothing_found", settings.lang)
    return text, newmarkup

def week_event_list(settings: UserSettings, chat_id, start_id=0, end_id=0) -> tuple[str, InlineKeyboardMarkup]:
    WHERE = f"""(user_id = {chat_id} AND isdel = 0)
                AND (substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2) 
                BETWEEN DATE('now') AND DATE('now', '+7 day'))"""
    SELECT = """event_id, date, text, status"""
    return generate_text(settings, "week_events", SELECT, WHERE, start_id, end_id)

def deleted(settings: UserSettings, chat_id, start_id=0, end_id=0) -> tuple[str, InlineKeyboardMarkup]:
    WHERE = f"""user_id = {chat_id} AND isdel != 0"""
    SELECT = """event_id, date, text, status"""
    MAXTIME = 7
    SQL(f"""
    DELETE FROM root 
    WHERE isdel != 0 
      AND user_id = {chat_id} 
      AND julianday('now') - julianday(substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)) > {MAXTIME};
    """, commit=True) # Удаляем события старше MAXTIME дня
    return generate_text(settings, "basket", SELECT, WHERE, start_id, end_id) # TODO None

def generate_text(settings: UserSettings, mode, SELECT, WHERE, start_id=0, end_id=0) -> tuple[str, InlineKeyboardMarkup]:
    newmarkup = InlineKeyboardMarkup()
    if not start_id and not end_id:
        start_id, end_id, newmarkup = get_diapason(WHERE=WHERE, reply_markup=delmarkup, MAXLEN=2500)
    sql_res = get_text_in_diapason(settings, start_id, end_id, SELECT=SELECT, WHERE=WHERE)
    text = get_translate(mode, settings.lang)
    if not sql_res:
        if mode == 'search':
            text += "\n\n" + get_translate("nothing_found", settings.lang)
        else:
            text += "\n\n" + get_translate("message_empty", settings.lang)
    for EVENTID, DATE, TEXT, STATUS in sql_res:
        TEXT = markdown(TEXT, STATUS, settings.sub_urls)
        q = okonchanie(settings, DATE)
        text += f'\n\n<b>{DATE}.{EVENTID}.{STATUS}</b> <u>{q}</u> \n{TEXT}'
    return text[:4090], newmarkup


def markdown(text: str, status: str, suburl=False) -> str:
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
        la = lambda url: f'<a href="{url[0]}">{urlparse(url[0]).scheme}://{urlparse(url[0]).netloc}</a>'
        return re.sub(r'(http?s?://\S+)', la, _text)

    def Code(_text: str):
        return f'<code>{_text}</code>'

    text = text.replace('\n\n', '\n⠀\n')
    if suburl: text = SubUrls(text)
    if status == '🧮': return OrderList(text)
    elif status == '💻': return Code(text)
    elif status == '🗒': return List(text)
    elif status == '🪞': return Spoiler(text)
    else: return text



def format_fill_message(SQLQuery, title="%d %wd %rd", text_iter="%n.%e.%s\n%scs%t%sce\n", empty_translate_target="🕸🕷  🕸"):
    """
    Заполнение сообщения по шаблону
    \n %d  - Date
    \n %wd - Week Date
    \n %rd - Relatively Date
    \n %n  - Порядковый номер
    \n %e  - Event_id
    \n %s  - Status
    \n %sc - Status Code + s - start, e - end
    \n %t  - Text

    :param SQLQuery:               Запрос для заполнения text_iter
    :param title:                  Заголовок
    :param text_iter:              Повторяющийся шаблон
    :param empty_translate_target: Если результат запроса пустой
    :return:                       message.text
    """
    replace_dict, format_string = {}, ""
    for key, value in replace_dict.items():
        format_string = format_string.replace(key, str(value))
    return format_string


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
            if (localtime := (t1 - self.cooldown_dict[f'{key}'])) < self.cooldown_time_sec:
                result = False, int(self.cooldown_time_sec - int(localtime))
        except Exception as e:
            print(f'Cooldown.check "{e}"')
        if update_dict or result[0]:
            self.cooldown_dict[f'{key}'] = t1
        return result

create_tables()

allmarkup = generate_buttons([
    {"➕": "event_add", "📝": "event_edit", "🚩": "event_status", "🔘": "menu"}, # "🗑": "event_del"}, # ➖
    {"🔙": "back", "<": "<<<", ">": ">>>", "✖": "message_del"}])
menumarkup = generate_buttons([{"🔙": "back", "ℹ️": "holidays", "👥": "share", "🗑": "event_del"}])
minimarkup = generate_buttons([{"🔙": "back", "✖": "message_del"}])
backmarkup = generate_buttons([{"🔙": "back"}])
delmarkup = generate_buttons([{"✖": "message_del"}])
CSVCooldown = Cooldown(1800, {})
callbackTab = '⠀⠀⠀'
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

# fixme yt
