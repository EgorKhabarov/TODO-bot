from requests.exceptions import MissingSchema, ConnectionError
from threading import Thread
from sys import platform
from time import sleep
import csv

from telebot import TeleBot
from telebot.types import CallbackQuery, InputFile
from telebot.types import BotCommandScopeChat    # Команды для определённого чата
from telebot.types import BotCommandScopeDefault # Дефолтные команды для всех остальных
from telebot.types import InputMediaDocument     # Команда /files шлёт все файлы бота в одном сообщении

from func import * # InlineKeyboardMarkup, InlineKeyboardButton, re, config импортируются из func


"""Для цветных логов (Выполнять только для Windows)"""
if platform == "win32": # Windows := 0:
    from ctypes import windll
    (lambda k: k.SetConsoleMode(k.GetStdHandle(-11), 7))(windll.kernel32)

re_call_data_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}\Z")
re_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}")
re_edit_message = re.compile(r"message\((\d+), (\d{1,2}\.\d{1,2}\.\d{4}), (\d+)\)")

bot = TeleBot(config.bot_token)
Me = bot.get_me()
BOT_ID = Me.id
BOT_USERNAME = Me.username
COMMANDS = ("calendar", "start", "deleted", "version", "forecast", "week_event_list", "currency",
            "weather", "search", "bell", "dice", "help", "settings", "today", "sqlite", "account",
            "files", "SQL", "save_to_csv", "setuserstatus", "id", "deleteuser", "idinfo", "commands")

bot_dict = Me.to_dict()
bot_dict = {
    **bot_dict,
    "database":      config.database_path,
    "log_file":      config.log_file,
    "notifications": config.notifications,
    "__version__":   config.__version__,
    "Время запуска": log_time_strftime()
}
def check(key, val) -> str:
    """Подсветит не правильные настройки красным цветом"""
    keylist = {"can_join_groups": "True", "can_read_all_group_messages": "True", "supports_inline_queries": "False"}
    indent = " " * 22
    return (f"\033[32m{val!s:<5}\033[0m{indent}" # \033[32m{val!s:<5}\033[0m{indent}
            if keylist[key] == str(val) else
            f"\033[31m{val!s:<5}\033[0m{indent}"
            ) if key in keylist else f"{val}"
logging.info(f"+{'-'*59}+\n"+"".join(f"| {k: >27} = {check(k, v): <27} |\n" for k, v in bot_dict.items())+f"+{'-'*59}+")
del check

bot.disable_web_page_preview = True
bot.parse_mode = "html"

def send(self, chat_id: int) -> Message:
    return bot.send_message(chat_id=chat_id, text=self.text, reply_markup=self.reply_markup)

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
    if only_markup:
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=self.reply_markup)
    elif markup is not None:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=self.text, reply_markup=markup)
    else:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=self.text, reply_markup=self.reply_markup)

MessageGenerator.send = send
MessageGenerator.edit = edit
del send
del edit

def clear_state(chat_id: int | str):
    """
    Очищает состояние приёма сообщения у пользователя и изменяет сообщение по id из add_event_date
    """
    add_event_date = SQL(f"SELECT add_event_date FROM settings WHERE user_id={chat_id};")[0][0]
    if add_event_date:
        msg_date, message_id = add_event_date.split(",")
        SQL(f"UPDATE settings SET add_event_date=0 WHERE user_id={chat_id};", commit=True)
        callback_handler(UserSettings(chat_id), chat_id, message_id, msg_date, "update", None, None)

def set_commands(settings: UserSettings, chat_id: int, user_status: int | str = 0) -> bool:
    """
    Ставит список команд для пользователя chat_id
    """
    if is_admin_id(chat_id):
        user_status = 2
    target = f"{user_status}_command_list"
    lang = settings.lang
    try:
        return bot.set_my_commands(commands=get_translate(target, lang),
                                   scope=BotCommandScopeChat(chat_id))
    except (ApiTelegramException, KeyError) as e:
        logging.info(f'[main.py -> set_commands -> "|"] (ApiTelegramException, KeyError) "{e}"')
        return False

# Ставим дефолтные команды для всех пользователей при запуске бота
bot.set_my_commands(commands=get_translate("0_command_list", "ru"), scope=BotCommandScopeDefault())

def command_handler(settings: UserSettings, chat_id: int, message_text: str, message: Message) -> None:
    """
    Отвечает за реакцию бота на команды
    Метод message.text.startswith("") используется для групп (в них сообщение приходит в формате /command{BOT_USERNAME})
    """
    if message_text.startswith("/calendar"):
        text = get_translate("choose_date", settings.lang)
        markup = calendar_days(chat_id, settings.timezone, settings.lang)
        bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

    elif message_text.startswith("/start"):
        set_commands(settings, chat_id, settings.user_status)
        markup = generate_buttons([
            {"/calendar": "/calendar"},
            {get_translate("add_bot_to_group", settings.lang): {
                "url": f"https://t.me/{BOT_USERNAME}?startgroup=AddGroup"}},
            {get_translate("game_bot", settings.lang): {
                "url": "https://t.me/EgorGameBot"}}
        ])
        bot.send_message(chat_id=chat_id, text=get_translate("start", settings.lang), reply_markup=markup)

    elif message_text.startswith("/deleted"):
        if settings.user_status in (1, 2) or is_admin_id(chat_id):
            generated = deleted(settings=settings, chat_id=chat_id)
            generated.send(chat_id=chat_id)
        else:
            set_commands(settings, chat_id, int(settings.user_status))
            bot.send_message(chat_id=chat_id, text=get_translate("deleted", settings.lang), reply_markup=delmarkup)

    elif message_text.startswith("/week_event_list"):
        generated = week_event_list(settings=settings, chat_id=chat_id)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/weather") or message_text.startswith("/forecast"):
        if message_text not in ("/weather", f"/weather@{BOT_USERNAME}",
                                "/forecast", f"/forecast@{BOT_USERNAME}"): # Проверяем есть ли аргументы
            nowcity = message_text.split(maxsplit=1)[-1]
        else:
            nowcity = UserSettings(user_id=chat_id).city
        try:
            if message_text.startswith("/weather"):
                weather = weather_in(settings=settings, city=nowcity)
            else: # forecast
                weather = forecast_in(settings=settings, city=nowcity)

            bot.send_message(chat_id=chat_id, text=weather, reply_markup=delmarkup)
        except KeyError:
            if message_text.startswith("/weather"):
                bot.send_message(chat_id=chat_id, text=get_translate("weather_invalid_city_name", settings.lang))
            else: # forecast
                bot.send_message(chat_id=chat_id, text=get_translate("forecast_invalid_city_name", settings.lang))

    elif message_text.startswith("/search"):
        query = ToHTML(message_text[len("/search "):]).replace("--", "").replace("\n", " ")
        generated = search(settings=settings, chat_id=chat_id, query=query)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/dice"):
        value = bot.send_dice(chat_id=chat_id).json["dice"]["value"]
        sleep(4)
        bot.send_message(chat_id=chat_id, text=value)

    elif message_text.startswith("/help"): # TODO папки, странички и темы
        bot.send_message(chat_id=chat_id,
                         text=get_translate("help", settings.lang),
                         reply_markup=delmarkup)

    elif message_text.startswith("/settings"):
        generated = settings.to_message()
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/today"):
        message_date = now_time_strftime(settings.timezone)
        generated = today_message(settings=settings, chat_id=chat_id, date=message_date)
        new_message = generated.send(chat_id=chat_id)

        # Чтобы не создавать новый `generated`, изменяем уже существующее, если в сообщение событие только одно.
        if len(generated.event_list) == 1:
            event = generated.event_list[0]
            generated.reply_markup[0][1].replace(
                old="callback_data",
                new="switch_inline_query_current_chat",
                val=f"Edit message({event.event_id}, {event.date}, {new_message.message_id})\n{NoHTML(event.text)}"
            )

            try:
                generated.edit(chat_id=chat_id, message_id=new_message.message_id, only_markup=True)
            except ApiTelegramException: # message is not modified
                pass

    elif message_text.startswith("/sqlite") and is_admin_id(chat_id) and message.chat.type == "private":
        bot.send_chat_action(chat_id=chat_id, action="upload_document")
        try:
            with open(config.database_path, "rb") as file:
                bot.send_document(chat_id=chat_id, document=file,
                                  caption=f"{now_time_strftime(settings.timezone)}", reply_markup=databasemarkup)
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text="Отправить файл не получилось")

    elif message_text.startswith("/files") and is_admin_id(chat_id) and message.chat.type == "private":
        bot.send_chat_action(chat_id=chat_id, action="upload_document")
        try:
            with (open("config.py", "rb") as config_file,
                  open("lang.py",   "rb") as lang_file,
                  open("func.py",   "rb") as func_file,
                  open(__file__,    "rb") as main_file,
                  open(config.database_path, 'rb') as db_file):
                bot.send_media_group(
                    chat_id=chat_id,
                    media=[
                        InputMediaDocument(config_file, caption="Файл настроек"),
                        InputMediaDocument(lang_file,   caption="Языковой файл"),
                        InputMediaDocument(func_file,   caption="Файл с функциями"),
                        InputMediaDocument(main_file,   caption="Основной файл"),
                        InputMediaDocument(db_file,     caption=f"База данных\n\nВерсия от {config.__version__}")
                    ])
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text="Отправить файл не получилось")

    elif message_text.startswith("/SQL ") and is_admin_id(chat_id) and message.chat.type == "private":
        bot.send_chat_action(chat_id=chat_id, action="upload_document")
        # Выполнение запроса от админа к базе данных и красивый вывод результатов
        query = message_text[5:].strip()
        file = StringIO()
        file.name = "table.txt"
        try:

            write_table_to_str(file=file,
                               query=query,
                               commit=message_text.endswith("\n--commit=True"))
        except Error as e:
            bot.reply_to(message, text=f'[main.py -> "/SQL"] Error "{e}"')
        else:
            file.seek(0)
            bot.send_document(chat_id=chat_id,
                              document=InputFile(file),
                              caption=f"<code>/SQL {query}</code>",
                              reply_to_message_id=message.message_id)
        finally:
            file.close()

    elif message_text.startswith("/bell"):
        notifications(
            user_id_list=[chat_id],
            from_command=True)

    elif message_text.startswith("/save_to_csv"):
        response, t = CSVCooldown.check(key=chat_id, update_dict=False)
        if response:
            bot.send_chat_action(chat_id=chat_id, action="upload_document")
            file = StringIO()
            file.name = f"ToDoList {message.from_user.username} ({now_time_strftime(settings.timezone)}).csv"
            table = SQL(f"""
                SELECT event_id, date, status, text FROM root
                WHERE user_id={chat_id} AND isdel=0;""", column_names=True)
            file_writer = csv.writer(file)
            [file_writer.writerows([[str(event_id), event_date, str(event_status), NoHTML(event_text)]])
             for event_id, event_date, event_status, event_text in table]
            file.seek(0)
            try:
                bot.send_document(chat_id=chat_id, document=InputFile(file))
            except ApiTelegramException as e:
                logging.info(f'[main.py -> command_handler -> "/save_to_csv"] ApiTelegramException "{e}"')
                bot.send_message(chat_id=chat_id, text=get_translate("file_is_too_big", settings.lang))
        else:
            bot.send_message(chat_id=chat_id, text=get_translate("export_csv", settings.lang).format(t=t // 60))

    elif message_text.startswith("/version"):
        bot.send_message(chat_id=chat_id,
                         text=f'Version {config.__version__}')

    elif message_text.startswith("/setuserstatus") and is_admin_id(chat_id) and message.chat.type == "private":
        if len(message_text.split(" ")) == 3:
            user_id, user_status = message_text.split(" ")[1:]
            try:
                if user_status not in (-1, 0, 1, 2):
                    raise ValueError

                SQL(f"UPDATE settings SET user_status='{user_status}' WHERE user_id={user_id};", commit=True)

                if not set_commands(settings, user_id, user_status):
                    raise KeyError
            except IndexError: # Если user_id не существует
                text = "Ошибка: id не существует"
            except Error as e: # Ошибка sqlite3
                text = f'Ошибка базы данных: "{e}"'
            except ApiTelegramException as e:
                text = f'Ошибка telegram api: "{e}"'
            except KeyError:
                text = "Ошибка user_status"
            except ValueError:
                text = "Неверный status\nstatus должен быть в (-1, 0, 1, 2)"
            else:
                text = "Успешно изменено"
        else:
            text = """
SyntaxError
/setuserstatus {id} {status}

| -1 | ban
|  0 | default
|  1 | premium
|  2 | admin
"""

        bot.reply_to(message=message, text=text)

    elif message_text.startswith("/idinfo ") and is_admin_id(chat_id) and message.chat.type == "private":
        if len(message_text.split(" ")) == 2:
            user_id = int(message_text.removeprefix("/idinfo "))
            chat = bot.get_chat(user_id)
            text = f"""
type: <code>{chat.type}</code>
title: <code>{chat.title}</code>
username: <code>{chat.username}</code>
first_name: <code>{chat.first_name}</code>
last_name: <code>{chat.last_name}</code>
id: <code>{chat.id}</code>

lang: {settings.lang}
timezone: {settings.timezone}
city: {settings.city}
notifications: {settings.notifications}
notifications_time: {settings.notifications_time}
direction: {settings.direction}
sub_urls: {settings.sub_urls}

command: <code>/idinfo {chat.id}</code>
promote: <code>/setuserstatus {chat.id} </code>
delete: <code>/deleteuser {chat.id}</code>
"""
        else:
            text = """
SyntaxError
/setuserstatus {id} {status}

| 0 | default
| 1 | premium
| 2 | admin
"""
        bot.reply_to(message=message, text=text)

    elif message_text.startswith("/idinfo") and is_admin_id(chat_id) and message.chat.type == "private":
        try:
            command_handler(settings, chat_id, "/SQL SELECT user_id as id FROM settings;", message)
        except ApiTelegramException:
            pass

    elif message_text.startswith("/id"):
        bot.reply_to(message=message,
                     text=f"@{message.from_user.username}\n"
                          f"Your id <code>{chat_id}</code>")

    elif message_text.startswith("/deleteuser") and is_admin_id(chat_id):
        if len(message_text.split(" ")) == 2:
            user_id = int(message_text.removeprefix("/deleteuser "))
            if not is_admin_id(user_id):
                try:
                    # TODO присылать sql файл для восстановления
                    SQL(f"DELETE FROM root     WHERE user_id={user_id};", commit=True)
                    SQL(f"DELETE FROM settings WHERE user_id={user_id};", commit=True)
                except Error as e:
                    text = f'Ошибка базы данных: "{e}"'
                else:
                    text = "Пользователь успешно удалён"
            else:
                text = f"Это id админа\n<code>/setuserstatus {user_id} 0</code>"
        else:
            text = "SyntaxError\n/deleteuser {id}"

        bot.reply_to(message=message, text=text)

    elif message_text.startswith("/account"):
        date = now_time(settings.timezone)
        bot.send_photo(chat_id, create_image(settings, date.year, date.month, date.day))

    elif message_text.startswith("/currency") and 0:
        currency1 = "₽"
        currency2 = "$"
        bot.send_message(chat_id, f"Калькулятор валют\n0\n{currency1} ➡️ {currency2}", reply_markup=generate_buttons([
            *[
                {f"{val}": f"currency {val}" for val in i}
                for i in (
                    (7, 8, 9),
                    (4, 5, 6),
                    (1, 2, 3),
                    (0, ".", "="),
                    ("clear", "🔙")
                )
            ],
            {f"from {currency1}": "currency set 1", "↔️": "currency ↔️", f"to {currency2}": "currency set 2"}
        ]))

    elif message_text.startswith("/commands"): # TODO перевод
        # /account - Ваш аккаунт (просмотр лимитов)
        bot.send_message(chat_id, """
/start - Старт
/calendar - Календарь
/today - События на сегодня
/weather {city} - Погода сейчас
/forecast {city} - Прогноз погоды
/week_event_list - Список событий на ближайшие 7 дней
/deleted - Корзина
/dice - Кинуть кубик
/save_to_csv - Сохранить мои события в csv
/help - Помощь
/settings - Настройки
/search {...} - Поиск
/id - Получить свой Telegram id

/commands - Этот список
""" + ("" if not is_admin_id(chat_id) else """
/version - Версия бота
/bell - Сообщение с уведомлением
/sqlite - Бекап базы данных
/files - Сохранить все файлы
/SQL {...} - Выполнить sql запрос к базе данных
/idinfo {id}/None - Получить файл с id всех пользователей или информацию о id
/setuserstatus {id} {status} - Поставить пользователю id команды для статуса status
/deleteuser {id} - Удалить пользователя
"""))

def callback_handler(settings: UserSettings, chat_id: int, message_id: int, message_text: str,
                     call_data: str, call_id: int | None, message: Message | None):
    """
    Отвечает за реакцию бота на нажатия на кнопку
    "event_add" - Добавить событие. Бот входит в режим ожидания получения события.
    "/calendar" - Изменить сообщение на календарь дней
    "back" -
    "message_del" - Пытается удалить сообщение. При ошибке шлёт сообщение с просьбой выдать права.
    "set database" - Нужно быть админом. Шлёт свою базу данных и заменяет её на бд из сообщения.
    "confirm change" - Подтвердить изменение текста события.
    "select event edit" - Если событий несколько, то предлагает выбрать конкретное для изменения текста.
    "select event status" - Если событий несколько, то предлагает выбрать конкретное для изменения статуса.
                     Если событие одно, то предлагает сразу для него изменить статус.
    "select event delete" - Если событий несколько, то предлагает выбрать конкретное для удаления или *перемещение в корзину. *в зависимости от прав пользователя
                  Если событие одно, то предлагает сразу для него удалить или *переместить в корзину. *в зависимости от прав пользователя
    "select event delete bin" - Делает то же самое что "select event delete" но после выполнения возвращает сообщение в корзину.
    "select event recover bin" -
    "select event open" - Открывает день выбранного события.
    "recover" - Восстанавливает событие из корзины.
    "status_home_page" -
    "status page" -
    "status set" - Установить статус для события.
    "status delete" -
    "before del" -
    "del" -
    "|" -
    "generate calendar month" -
    "generate calendar days" -
    "settings" - par_name, par_val - Изменить значение колонки par_name на par_val и обновить сообщение с новыми настройками
    "recurring" - Вызвать сообщение с повторяющимися событиями. Например, дни рождения за прошлые года.
    "<<<", ">>>" - Изменение на 1 день в сообщении на дату.
    r"\A\d{1,2}\.\d{1,2}\.\d{4}\Z" - Вызвать сообщение с текущей датой.
    "update" - Обновить сообщение в зависимости от типа. Поддерживает сообщения типа поиск, week_event_list, корзина, сообщение с датой.
    """
    if call_data == "event_add":
        clear_state(chat_id)
        date = message_text[:10]

        # Проверяем будет ли превышен лимит для пользователя, если добавить 1 событие с 1 символом
        if is_exceeded_limit(settings, date, 1, 1):
            text = get_translate("exceeded_limit", settings.lang)
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True, text=text)
            return

        SQL(f"UPDATE settings SET add_event_date='{date},{message_id}' WHERE user_id={chat_id};", commit=True)

        text = get_translate("send_event_text", settings.lang)
        bot.answer_callback_query(callback_query_id=call_id, text=text)

        text = f"{ToHTML(message_text)}\n\n0.0.⬜\n{text}"
        bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=backmarkup)

    elif call_data == "/calendar":
        text = get_translate("choose_date", settings.lang)
        markup = calendar_days(chat_id=chat_id, user_timezone=settings.timezone, lang=settings.lang)
        bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=markup)

    elif call_data.startswith("back"):
        # не вызываем await clear_state(chat_id) так как она после очистки вызывает сегодняшнее сообщение
        add_event_date = SQL(f"SELECT add_event_date FROM settings WHERE user_id={chat_id};")[0][0]
        if add_event_date:
            add_event_message_id = add_event_date.split(",")[1]
            if int(message_id) == int(add_event_message_id):
                SQL(f"UPDATE settings SET add_event_date=0 WHERE user_id={chat_id};", commit=True)

        msg_date = message_text[:10]

        if call_data.endswith("bin"): # Корзина
            generated = deleted(settings=settings, chat_id=chat_id)
            generated.edit(chat_id=chat_id, message_id=message_id)

        elif message_text.startswith("🔍 "):  # Поиск
            query = ToHTML(message_text.split("\n", maxsplit=1)[0].split(maxsplit=2)[-1][:-1])
            generated = search(settings=settings, chat_id=chat_id, query=query)
            generated.edit(chat_id=chat_id, message_id=message_id)

        elif len(msg_date.split(".")) == 3: # Проверка на дату
            try: # Пытаемся изменить сообщение
                generated = today_message(settings=settings, chat_id=chat_id, date=msg_date, message_id=message_id)
                generated.edit(chat_id=chat_id, message_id=message_id)
            except ApiTelegramException: # Если сообщение не изменено, то шлём календарь
                YY_MM = [int(x) for x in msg_date.split(".")[1:]][::-1] # "dd.mm.yyyy" -> [yyyy, mm]
                text = get_translate("choose_date", settings.lang)
                markup = calendar_days(chat_id, settings.timezone, settings.lang, YY_MM)
                bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data == "message_del":
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException:
            text = get_translate("get_admin_rules", settings.lang)
            bot.reply_to(message=message, text=text, reply_markup=delmarkup)

    elif call_data == "set database" and is_admin_id(chat_id):
        try:
            with open(config.database_path, "rb") as file:
                text = f"{now_time_strftime(settings.timezone)}\nНа данный момент база выглядит так."
                bot.send_document(chat_id=chat_id, document=file, caption=text, reply_markup=databasemarkup)
        except ApiTelegramException:
            bot.send_message(chat_id, "Отправить файл не получилось...")
            return

        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            with open(f"{message.document.file_name}", "wb") as new_file:
                new_file.write(downloaded_file)
            bot.reply_to(message, "Файл записан")
        except ApiTelegramException:
            bot.send_message(chat_id, "Скачать или записать файл не получилось...")
            return

    elif call_data == "confirm change":
        text = ToHTML(message_text.split("\n", maxsplit=2)[-1]) # Получаем изменённый текст
        msg_date, *_, event_id = message_text.split("\n", maxsplit=1)[0].split(" ") # TODO изменить парсинг переменных

        try:
            SQL(f"""
                UPDATE root SET text='{text}'
                WHERE user_id={chat_id} AND event_id={event_id}
                AND date='{msg_date}';""", commit=True)
        except Error as e:
            logging.info(f'[main.py -> callback_handler -> "confirm change"] Error "{e}"')
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("error", settings.lang))

        callback_handler(UserSettings(chat_id), chat_id, message_id, msg_date, "update", None, None)

    elif call_data.startswith("select event "):
        action = call_data[13:] # Literal["edit", "status", "delete", "delete bin", "recover bin", "open"]

        events_list = message_text.split('\n\n')[1:]

        # Заглушка если событий нет
        if events_list[0].startswith("👀") or events_list[0].startswith("🕸"):
            bot.answer_callback_query(call_id, get_translate("no_events_to_interact", settings.lang), show_alert=True)
            return

        msg_date = message_text[:10]

        # Если событие одно то оно сразу выбирается
        if len(events_list) == 1:
            event_id = events_list[0].split(".", maxsplit=2)[1]
            if action.endswith("bin"): # TODO изменить парсинг переменных
                event_id = events_list[0].split(".", maxsplit=4)[-2]
            try:
                SQL(f"""
                    SELECT text FROM root 
                    WHERE event_id={event_id} AND user_id={chat_id}
                    {"AND isdel!=0" if action.endswith("bin") else ""};""")[0][0]
            except IndexError: # Если этого события не существует
                callback_handler(settings, chat_id, message_id, message_text, "update", call_id, message)
                return

            if action in ("status", "delete", "delete bin", "recover bin", "open"):
                event_date = events_list[0][:10]
                if action == "status":        new_call_data = f"status_home_page {event_id} {msg_date}"
                elif action == "delete":      new_call_data = f"before del {msg_date} {event_id} _"
                elif action == "delete bin":  new_call_data = f"del {event_date} {event_id} bin delete"
                elif action == "recover bin": new_call_data = f"recover {event_date} {event_id}"
                else:                         new_call_data = f"{event_date}" # "select event open"

                callback_handler(settings, chat_id, message_id, message_text, new_call_data, call_id, message)
                return

        markup = InlineKeyboardMarkup()
        for event in events_list:
            # Парсим данные
            if action.endswith("bin") or message_text.startswith("🔍 "):
                event_id = event.split(".", maxsplit=4)[-2]
            else:
                event_id = event.split(".", maxsplit=2)[-2]

            # Проверяем существование события
            try:
                event_text = SQL(f"""
                    SELECT text FROM root 
                    WHERE event_id={event_id} AND user_id={chat_id}
                    AND isdel{"!" if action.endswith("bin") else ""}=0;""")[0][0]
            except IndexError:
                continue

            if action == "edit":
                markup.row(InlineKeyboardButton(
                    text=f"{event}{callbackTab * 20}",
                    switch_inline_query_current_chat=f"Edit message({event_id}, {msg_date}, {message.message_id})\n"
                                                     f"{NoHTML(event_text)}"))

            elif action in ("status", "delete"): # Действия в обычном дне
                button_title = event.replace("\n", " ")[:50]
                if action == "status":
                    callback_data = f"status_home_page {event_id} {msg_date}"
                else: # "delete"
                    callback_data = f"before del {msg_date} {event_id} _"

                markup.row(InlineKeyboardButton(text=f"{button_title}{callbackTab * 20}", callback_data=callback_data))

            elif action in ("delete bin", "recover bin"): # Действия в корзине
                event_date = event[:10]
                button_title = event.split(" ", maxsplit=1)[0] + " " + event.split("\n", maxsplit=1)[-1][:50]
                if action == "delete bin":
                    callback_data = f"del {event_date} {event_id} bin delete"
                else: # "recover bin"
                    callback_data = f"recover {event_date} {event_id}"

                markup.row(InlineKeyboardButton(f"{button_title}{callbackTab * 20}", callback_data=callback_data))

            elif action == "open":
                event_text = event.split("\n", maxsplit=1)[-1]
                text = f"{event.split(' ', maxsplit=1)[0]} {event_text}{callbackTab * 20}"
                markup.row(InlineKeyboardButton(text=text, callback_data=f"{event[:10]}"))

        if not markup.to_dict()["inline_keyboard"]: # Созданный markup пустой
            callback_handler(settings, chat_id, message_id, message_text, "update", call_id, message)
            return

        # TODO заменить чтобы при поиске ставилось другое и убрать костыль в back
        # if message_text.startswith("🔍 "):  # Поиск
        #     query = ToHTML(message_text.split("\n", maxsplit=1)[0].split(maxsplit=2)[-1][:-1])
        markup.row(InlineKeyboardButton("🔙", callback_data="back" if not action.endswith("bin") else "back bin"))

        if action == "edit":
            text = f"{msg_date}\n" \
                   f"{get_translate('select_event_to_edit', settings.lang)}"

        elif action == "status":
            text = f"{msg_date}\n" \
                   f"{get_translate('select_event_to_change_status', settings.lang)}"

        elif action == "delete":
            text = f"{msg_date}\n" \
                   f"{get_translate('select_event_to_delete', settings.lang)}"

        elif action == "delete bin":
            text = f"{get_translate('basket', settings.lang)}\n" \
                   f"{get_translate('select_event_to_delete', settings.lang)}"

        elif action == "recover bin":
            text = f"{get_translate('basket', settings.lang)}\n" \
                   f"{get_translate('select_event_to_recover', settings.lang)}"

        elif message_text.startswith("🔍 "):
            query = ToHTML(message_text.split("\n", maxsplit=1)[0].split(maxsplit=2)[-1][:-1])
            text = f"🔍 {get_translate('search', settings.lang)} {query}:\n" \
                   f"{get_translate('choose_event', settings.lang)}"

        else:
            text = f"{msg_date}\n" \
                   f"{get_translate('choose_event', settings.lang)}"

        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("recover"):
        event_date, event_id = call_data.split(maxsplit=2)[1:]
        try:
            event_len = SQL(f"""
                SELECT LENGTH(text) FROM root
                WHERE user_id={chat_id} AND event_id={event_id}
                AND date='{event_date}' AND isdel!=0;""")[0][0]
        except IndexError:
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True,
                                      text=get_translate("error", settings.lang))
            return # такого события нет

        # TODO проверка лимита
        if is_exceeded_limit(settings, event_date, 1, event_len):
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True,
                                      text=get_translate("exceeded_limit", settings.lang))
            return

        SQL(f"""
            UPDATE root SET isdel=0
            WHERE user_id={chat_id} AND event_id={event_id}
            AND date='{event_date}';""", commit=True)
        callback_handler(settings, chat_id, message_id, message_text, "back bin", call_id, message)

    elif call_data.startswith("status_home_page") or call_data.startswith("status page "):
        # Парсим данные
        if call_data.startswith("status_home_page"):
            event_id, event_date = call_data.split(" ")[1:]
        else: # status page
            args = message_text.split("\n", maxsplit=3)
            event_date, event_id = args[0], args[2].split(".", maxsplit=4)[3]

        # Проверяем наличие события
        try: # Если события нет, то обновляем сообщение
            text, status = SQL(f"""
                SELECT text, status FROM root
                WHERE user_id={chat_id} AND event_id="{event_id}"
                AND isdel=0 AND date="{event_date}";""")[0]
        except IndexError:  # Если этого события уже нет
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return

        if call_data.startswith("status_home_page"):
            sl = status.split(",")
            sl.extend([""]*(5-len(sl)))
            markup = generate_buttons([
                *[{f"{title}{callbackTab * 20}": (
                    f"{data}" if data else f"status set {title.split(maxsplit=1)[0]} {event_id} {event_date}")}
                  for title, data in get_translate("status_home_page", settings.lang).items()],
                {f"{i}" if i else " "*n:
                 f"status delete {i} {event_id} {event_date}" if i else "None"
                 for n, i in enumerate(sl)} if status != "⬜️" else {},
                {"🔙": "back"}
            ])
        else: # status page
            buttons_data = get_translate(call_data, settings.lang)
            markup = generate_buttons([
                *[{f"{row}{callbackTab * 20}": f"status set {row.split(maxsplit=1)[0]} {event_id} {event_date}"
                   for row in status_column} if len(status_column) > 1 else {
                    f"{status_column[0]}{callbackTab * 20}": f"status set {status_column[0].split(maxsplit=1)[0]} {event_id} {event_date}"
                }
                  for status_column in buttons_data],
                {"🔙": f"status_home_page {event_id} {event_date}"}
            ])

        bot.edit_message_text(f"{event_date}\n"
                              f"<b>{get_translate('select_status_to_event', settings.lang)}\n"
                              f"{event_date}.{event_id}.{status}</b>\n"
                              f"{markdown(text, status, settings.sub_urls)}",
                              chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("status set"):
        new_status, event_id, event_date = call_data.split()[2:]

        try: # Если события нет, то обновляем сообщение
            text, old_status = SQL(f"""
                SELECT text, status FROM root
                WHERE user_id={chat_id} AND event_id="{event_id}"
                AND isdel=0 AND date="{event_date}";""")[0]
        except IndexError:
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return

        if new_status == "⬜️" == old_status:
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return

        elif new_status in old_status:
            text = get_translate("status_already_posted", settings.lang)
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True, text=text)

        elif len(old_status.split(",")) > 4 and new_status != "⬜️":
            text = get_translate("more_5_statuses", settings.lang)
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True, text=text)

        # Убираем конфликтующие статусы
        elif ("🔗" in old_status or "💻" in old_status) and new_status in ("🔗", "💻"):
            get_translate("conflict_statuses", settings.lang) + f" 🔗, 💻"
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True, text=text)

        elif ("🪞" in old_status or "💻" in old_status) and new_status in ("🪞", "💻"):
            text = get_translate("conflict_statuses", settings.lang) + f" 🪞, 💻"
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True, text=text)

        elif ("🔗" in old_status or "❌🔗" in old_status) and new_status in ("🔗", "❌🔗"):
            text = get_translate("conflict_statuses", settings.lang) + f" 🔗, ❌🔗"
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True, text=text)

        else:
            if old_status == "⬜️":
                res_status = new_status

            elif new_status == "⬜️":
                res_status = "⬜️"

            else:
                res_status = f"{old_status},{new_status}"

            SQL(f"""
                UPDATE root SET status='{res_status}'
                WHERE user_id={chat_id} AND event_id={event_id}
                AND date='{event_date}';""", commit=True)

        if new_status == "⬜️":
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
        else:
            callback_handler(settings, chat_id, message_id, message_text, f"status_home_page {event_id} {event_date}", call_id, message)

        # callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)

    elif call_data.startswith("status delete"):
        status, event_id, event_date = call_data.split()[2:]

        try: # Если события нет, то обновляем сообщение
            text, old_status = SQL(f"""
                SELECT text, status FROM root
                WHERE user_id={chat_id} AND event_id="{event_id}"
                AND isdel=0 AND date="{event_date}";""")[0]
        except IndexError:
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return

        if status == "⬜️":
            return

        res_status = old_status.replace(f",{status}", "").replace(f"{status},", "").replace(f"{status}", "")

        if not res_status:
            res_status = "⬜️"

        SQL(f"""
            UPDATE root SET status='{res_status}' 
            WHERE user_id={chat_id} AND event_id={event_id} 
            AND date='{event_date}';""", commit=True)

        callback_handler(settings, chat_id, message_id, message_text, f"status_home_page {event_id} {event_date}", call_id, message)

        # callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)

    elif call_data.startswith("before del "):
        event_date, event_id, back_to_bin = call_data.split()[2:]
        try:
            text, status = SQL(f"""
                SELECT text, status FROM root
                WHERE user_id={chat_id} AND event_id={event_id} AND date='{event_date}' AND
                isdel{"!" if back_to_bin == "bin" else ""}=0;""")[0]
        except IndexError as e:
            logging.info(f'[main.py -> callback_handler -> "before del"] IndexError "{e}"')
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("error", settings.lang))
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return

        predelmarkup = generate_buttons([
            {"🔙": "back" if back_to_bin != "bin" else
             "back bin", "❌ "+get_translate("delete_permanently", settings.lang): f"{call_data.split(maxsplit=1)[-1]} delete"},
            {
                "🗑 " + get_translate("trash_bin", settings.lang): f"{call_data.split(maxsplit=1)[-1]} to_bin"
            } if ((settings.user_status in (1, 2) and back_to_bin != "bin") or is_admin_id(chat_id)) else {}
        ])

        day = DayInfo(settings, event_date)
        sure_text = get_translate('are_you_sure', settings.lang)
        end_text = get_translate("/deleted", settings.lang) if (settings.user_status in (1, 2) or is_admin_id(chat_id)) else ""
        text = (f"<b>{event_date}.{event_id}.</b>{status} <u><i>{day.str_date}  {day.week_date}</i> {day.relatively_date}</u>\n"
                f"<b>{sure_text}:</b>\n{text[:3800]}\n\n{end_text}")
        bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=predelmarkup)

    elif call_data.startswith("del "):
        event_date, event_id, where, mode = call_data.split(maxsplit=4)[1:]
        try:
            if (settings.user_status in (1, 2) or is_admin_id(chat_id)) and mode == "to_bin":
                SQL(f"""
                    UPDATE root SET isdel='{now_time_strftime(settings.timezone)}' 
                    WHERE user_id={chat_id} AND date='{event_date}' AND event_id={event_id};""", commit=True)
            else:
                SQL(f"""
                    DELETE FROM root 
                    WHERE user_id={chat_id} AND date='{event_date}' AND event_id={event_id};""", commit=True)
        except Error as e:
            logging.info(f'[main.py -> callback_handler -> "del"] Error "{e}"')
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("error", settings.lang))
        callback_handler(settings, chat_id, message_id, message_text, "back" if where != "bin" else "back bin", call_id, message)

    elif call_data.startswith("|"): # Список id событий на странице
        page, id_list = call_data.split("|")[1:]
        id_list = id_list.split(",")
        try:
            if message_text.startswith("🔍 "): # Поиск
                query = ToHTML(message_text.split("\n", maxsplit=1)[0].split(maxsplit=2)[-1][:-1])
                generated = search(settings=settings, chat_id=chat_id, query=query, id_list=id_list, page=page)
                generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

            elif message_text.startswith("📆"): # Если /week_event_list
                generated = week_event_list(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
                generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

            elif message_text.startswith("🗑"): # Корзина
                generated = deleted(settings=settings, chat_id=chat_id, id_list=id_list, page=page)
                generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

            elif re_date.match(message_text) is not None:
                msg_date = re_date.match(message_text)[0]
                if page.startswith("!"):
                    generated = recurring(settings=settings,
                                          date=msg_date,
                                          chat_id=chat_id,
                                          id_list=id_list,
                                          page=page[1:])
                else:
                    generated = today_message(settings=settings,
                                              chat_id=chat_id,
                                              date=msg_date,
                                              id_list=id_list,
                                              page=page,
                                              message_id=message_id)
                generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

            elif message_text.startswith("🔔"): # Будильник
                notifications(user_id_list=[chat_id], id_list=id_list, page=page, message_id=message_id, markup=message.reply_markup)

        except ApiTelegramException:
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("already_on_this_page", settings.lang))

    elif call_data.startswith("generate calendar months "):
        sleep(0.5)  # FIXME Задержка
        year = call_data.split()[-1]
        if year == "now":
            YY = now_time(settings.timezone).year
        else:
            YY = int(year)

        if 1980 <= YY <= 3000:
            markup = calendar_months(settings.timezone, settings.lang, chat_id, YY)
            try:
                bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
            except ApiTelegramException: # Сообщение не изменено
                callback_handler(settings, chat_id, message_id, message_text, "/calendar", call_id, message)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data.startswith("generate calendar days "):
        sleep(0.5) # FIXME Задержка
        if call_data.split()[-1] == "now":
            YY_MM = new_time_calendar(settings.timezone)
        else:
            YY_MM = [int(i) for i in call_data.split()[-2:]]

        if 1980 <= YY_MM[0] <= 3000:
            markup = calendar_days(chat_id, settings.timezone, settings.lang, YY_MM)
            try:
                bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
            except ApiTelegramException: # Если нажата кнопка ⟳, но сообщение не изменено
                date = now_time_strftime(settings.timezone)
                generated = today_message(settings=settings, chat_id=chat_id, date=date, message_id=message_id)
                generated.edit(chat_id=chat_id, message_id=message_id)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data.startswith("settings"):
        par_name, par_val = call_data.split(" ", maxsplit=2)[1:]
        if isinstance(par_val, str):
            par_val = f"'{par_val}'"

        SQL(f"UPDATE settings SET {par_name}={par_val} WHERE user_id={chat_id};", commit=True)

        settings = UserSettings(chat_id)
        set_commands(settings, chat_id, settings.user_status)
        generated = settings.to_message()
        try:
            generated.edit(chat_id=chat_id, message_id=message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("recurring"):
        generated = recurring(settings=settings, date=message_text[:10], chat_id=chat_id)
        generated.edit(chat_id=chat_id, message_id=message_id)

    elif re_call_data_date.search(call_data):
        year = int(call_data[-4:])
        sleep(0.3)  # FIXME Задержка
        if 1980 < year < 3000:
            generated = today_message(settings=settings, chat_id=chat_id, date=call_data, message_id=message_id)
            generated.edit(chat_id=chat_id, message_id=message_id)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data == "update":
        if message_text.startswith("🔍 "): # Поиск
            query = ToHTML(message_text.split("\n", maxsplit=1)[0].split(maxsplit=2)[-1][:-1])
            generated = search(settings=settings, chat_id=chat_id, query=query)

        elif message_text.startswith("📆"):  # Если /week_event_list
            generated = week_event_list(settings=settings, chat_id=chat_id)

        elif message_text.startswith("🗑"):  # Корзина
            generated = deleted(settings=settings, chat_id=chat_id)

        elif re_date.match(message_text) is not None:
            msg_date = re_date.match(message_text)[0]
            generated = today_message(settings=settings, chat_id=chat_id, date=msg_date, message_id=message_id)

        else:
            return

        try:
            generated.edit(chat_id=chat_id, message_id=message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("currency"):
        data = call_data.split(" ", maxsplit=1)[-1]
        value = message_text.splitlines()[1]
        currency1, currency2 = message_text.splitlines()[-1].split(" ➡️ ")
        if data == "clear": value = "0"
        if data == "↔️": currency1, currency2 = currency2, currency1
        if data in "0123456789.":
            if value == "0" and data != ".": value = ""
            if data == "." and "." in value: return
            value += data
        if data == "🔙":
            value = value[:-1]
            if value == "": value = "0"

        try:
            bot.edit_message_text(
                text=f"Калькулятор валют\n{value}\n{currency1} ➡️ {currency2}",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=generate_buttons([
                    *[
                        {f"{val}": f"currency {val}" for val in i}
                        for i in (
                            (7, 8, 9),
                            (4, 5, 6),
                            (1, 2, 3),
                            (0, ".", "="),
                            ("clear", "🔙")
                        )
                    ],
                    {f"from {currency1}": "currency set 1", "↔️": "currency ↔️", f"to {currency2}": "currency set 2"}
                ])
            )
        except ApiTelegramException:
            pass


@bot.message_handler(commands=[*COMMANDS])
@execution_time
def message_handler(message: Message):
    """
    Ловит команды от пользователей
    """
    chat_id, message_text = message.chat.id, message.text
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(user_status=settings.user_status, chat_id=chat_id, text=message_text, action="send")
    command_handler(settings, chat_id, message_text, message)

@bot.callback_query_handler(func=lambda call: True)
@execution_time
def callback_query_handler(call: CallbackQuery):
    """
    Ловит нажатия на кнопки
    """
    chat_id, message_id, call_data, message_text = call.message.chat.id, call.message.message_id, call.data, call.message.text
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(user_status=settings.user_status, chat_id=chat_id, text=call_data, action="pressed")
    if call.data == "None":
        return 0
    callback_handler(settings, chat_id, message_id, call.message.text, call.data, call.id, call.message)

@bot.message_handler(func=lambda m: m.text.startswith("#"))
@execution_time
def get_search_message(message: Message):
    """
    Ловит сообщения поиска
    #   (ИЛИ)
    #!  (И)
    """
    query = ToHTML(message.text[1:].replace("--", "").replace("\n", " "))
    chat_id = message.chat.id
    settings = UserSettings(user_id=chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(user_status=settings.user_status, chat_id=chat_id, text=message.text, action="search ")
    generated = search(settings=settings, chat_id=chat_id, query=query)
    generated.send(chat_id=chat_id)

@bot.message_handler(func=lambda m: m.text.startswith(f"@{BOT_USERNAME} Edit message(") and re_edit_message.search(m.text))
@execution_time
def get_edit_message(message: Message):
    """
    Ловит сообщения для изменения событий
    """
    chat_id, edit_message_id = message.chat.id, message.message_id
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(user_status=settings.user_status, chat_id=chat_id, text="edit event text", action="send")

    res = re_edit_message.search(message.text)[0]

    (
        event_id,
        event_date,
        message_id,
        text
    ) = (
        int(re.findall(r"\((\d+)", res)[0]),
        str(re.findall(r" (\d{1,2}\.\d{1,2}\.\d{4}),", res)[0]),
        int(re.findall(r", (\d+)\)", res)[0]),
        message.text.split("\n", maxsplit=1)[-1].strip("\n")  # ВАЖНО!
    )

    markup = generate_buttons([
        {f"{event_id} {text[:20]}{callbackTab * 20}": {
            "switch_inline_query_current_chat": f"{message.text.split(maxsplit=1)[-1]}"}},
        {"✖": "message_del"}
    ])

    tag_len_max = len(text) > 3800
    try:
        # Уменьшится ли длинна события
        len_old_event, tag_len_less = SQL(f"""
            SELECT LENGTH(text), {len(text)} < LENGTH(text) FROM root
            WHERE user_id={chat_id} AND event_id='{event_id}'
            AND date='{event_date}' AND isdel=0;""")[0]
    except ValueError:
        return # Этого события нет

    # Вычисляем сколько символов добавил пользователь. Если символов стало меньше, то 0.
    added_length = 0 if tag_len_less else len(text) - len_old_event
    # TODO проверка лимита
    tag_limit_exceeded = is_exceeded_limit(settings, event_date, 0, added_length)

    if tag_len_max:
        bot.reply_to(message, get_translate("message_is_too_long", settings.lang), reply_markup=markup)
    elif tag_limit_exceeded:
        bot.reply_to(message, get_translate("exceeded_limit", settings.lang), reply_markup=markup)
    else:
        try:
            day = DayInfo(settings, event_date)
            bot.edit_message_text(f"""
{event_date} <u><i>{day.str_date}  {day.week_date}</i> {day.relatively_date}</u> {event_id}
<b>{get_translate("are_you_sure_edit", settings.lang)}</b>
<i>{ToHTML(text)}</i>
""",
                                  chat_id, message_id,
                                  reply_markup=generate_buttons([
                                      {
                                          "🔙": "back",
                                          "📝": {
                                              "switch_inline_query_current_chat": f"{message.text.split(maxsplit=1)[-1]}"
                                          },
                                          "✅": "confirm change"
                                      }
                                  ])
                                  )
        except ApiTelegramException as e:
            if "message is not modified" not in str(e):
                logging.info(f'[main.py -> get_edit_message] ApiTelegramException "{e}"')
                return
    try:
        bot.delete_message(chat_id, edit_message_id)
    except ApiTelegramException:
        bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

@bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.text.startswith("⚙️") and m.reply_to_message.from_user.id == BOT_ID)
@execution_time
def get_edit_city_message(message: Message):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    chat_id, message_id = message.chat.id, message.message_id
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(user_status=settings.user_status, chat_id=chat_id, text="edit city", action="send")
    callback_handler(settings, chat_id, message.reply_to_message.message_id, message.text, f"settings city {message.text[:25]}", 0, message.reply_to_message)
    try:
        bot.delete_message(chat_id, message_id)
    except ApiTelegramException:
        bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

add_event_func = lambda msg: add_event_date[0][0] \
    if (add_event_date := SQL(f"SELECT add_event_date FROM settings WHERE user_id={msg.chat.id};")) else 0
@bot.message_handler(func=add_event_func)
@execution_time
def add_event(message: Message):
    """
    Ловит сообщение если пользователь хочет добавить событие
    """
    chat_id, message_id, message_text = message.chat.id, message.message_id, ToHTML(message.text) # Экранируем текст
    settings = UserSettings(chat_id)

    if settings.user_status == -1 and not is_admin_id(chat_id):
        return

    main_log(user_status=settings.user_status, chat_id=chat_id, text="add event", action="send")

    new_event_date = SQL(f"SELECT add_event_date FROM settings WHERE user_id={chat_id};")[0][0].split(",")[0]

    # Если сообщение команда то проигнорировать
    if message_text.split("@")[0][1:] in COMMANDS:
        return

    # Если сообщение длиннее 3800 символов, то ошибка
    if len(message_text) >= 3800:
        bot.reply_to(message, get_translate("message_is_too_long", settings.lang), reply_markup=delmarkup)
        return

    # TODO проверка лимита
    if is_exceeded_limit(settings, new_event_date, 1, len(message_text)):
        bot.reply_to(message, get_translate("exceeded_limit", settings.lang), reply_markup=delmarkup)
        return

    # Пытаемся создать событие
    if create_event(chat_id, new_event_date, message_text):
        clear_state(chat_id)
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException: # Если в группе у бота нет прав для удаления сообщений
            bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)
    else:
        bot.reply_to(message, get_translate("error", settings.lang), reply_markup=delmarkup)
        clear_state(chat_id)


def schedule_loop():
    # ждём чтобы цикл уведомлений начинался
    sleep(60 - now_time(config.hours_difference).second)
    while True:
        while_time = now_time(config.hours_difference)
        if str(while_time.minute).endswith("0"): # 0, 10, 20, 30, 40, 50
            Thread(target=notifications, daemon=True).start()
        if while_time.minute in (0, 30):
            if config.link:
                logging.info(f"[{log_time_strftime()}] {config.link} ", end="")
                try:
                    logging.info(f"{get(config.link, headers=config.headers).status_code}")
                except MissingSchema as e:
                    logging.info(f"{e}")
                except ConnectionError:
                    logging.info("404")

        sleep(60)

if __name__ == "__main__":
    if config.notifications:
        Thread(target=schedule_loop, daemon=True).start()
    bot.infinity_polling()
