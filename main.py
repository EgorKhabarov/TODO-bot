from threading import Thread
from sys import platform
from time import sleep
import csv

from telebot import TeleBot
from telebot.types import CallbackQuery, Message, InputFile
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
COMMANDS = ('calendar', 'start', 'deleted', 'version', 'forecast', 'week_event_list',
            'weather', 'search', 'bell', 'dice', 'help', 'settings', 'today', 'sqlite',
            'files', 'SQL', 'save_to_csv', 'setuserstatus', 'id')
def check(key, val) -> str:
    """Подсветит не правильные настройки красным цветом"""
    keylist = {"can_join_groups": "True", "can_read_all_group_messages": "True", "supports_inline_queries": "False"}
    indent = ' ' * 22
    return (f"\033[32m{val!s:<5}\033[0m{indent}" # \033[32m{val!s:<5}\033[0m{indent}
            if keylist[key] == str(val) else
            f"\033[31m{val!s:<5}\033[0m{indent}"
            ) if key in keylist else f"{val}"

print(f"+{'-'*59}+\n"+''.join(f'| {k: >27} = {check(k, v): <27} |\n' for k, v in Me.to_dict().items())+f"+{'-'*59}+")

bot.disable_web_page_preview = True
bot.parse_mode = "html"

def send(self, chat_id: int) -> None:
    bot.send_message(chat_id=chat_id, text=self.text, reply_markup=self.reply_markup)

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

MyMessage.send = send
MyMessage.edit = edit

def clear_state(chat_id: int | str):
    """
    Очищает состояние приёма сообщения у пользователя и изменяет сообщение по id из add_event_date
    """
    add_event_date = SQL(f"SELECT add_event_date FROM settings WHERE user_id={chat_id};")[0][0]
    if add_event_date:
        msg_date, message_id = add_event_date.split(",")
        SQL(f"UPDATE settings SET add_event_date=0 WHERE user_id={chat_id};", commit=True)
        try:
            generated = today_message(settings=UserSettings(chat_id), chat_id=chat_id, date=msg_date)
            generated.edit(chat_id=chat_id, message_id=message_id)
        except ApiTelegramException:
            pass

def set_commands(settings: UserSettings, chat_id: int, user_status: int | str = 0) -> bool:
    """
    Ставит список команд для пользователя chat_id
    """
    if is_admin_id(chat_id):
        user_status = 2
    target = f"{user_status}_command_list"
    lang = settings.lang
    try:
        return bot.set_my_commands(commands=get_translate(target, lang), scope=BotCommandScopeChat(chat_id=chat_id))
    except (ApiTelegramException, KeyError) as e:
        print(f"[main.py -> set_commands -> \"|\"] (ApiTelegramException, KeyError) \"{e}\"")
        return False

# Ставим дефолтные команды для всех пользователей при запуске бота
bot.set_my_commands(commands=get_translate("0_command_list", "ru"), scope=BotCommandScopeDefault())

def command_handler(settings: UserSettings, chat_id: int, message_text: str, message: Message) -> None:
    """
    Отвечает за реакцию бота на команды
    Метод message.text.startswith("") используется для групп (в них сообщение приходит в формате /command{BOT_USERNAME})
    """
    if message_text.startswith("/calendar"):
        bot.send_message(chat_id, 'Выберите дату',
                         reply_markup=mycalendar(chat_id, settings.timezone, settings.lang))

    elif message_text.startswith("/start"):
        set_commands(settings, chat_id, settings.user_status)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("/calendar", callback_data="/calendar"))
        markup.row(InlineKeyboardButton(get_translate("add_bot_to_group", settings.lang),
                                        url=f'https://t.me/{BOT_USERNAME}?startgroup=AddGroup'))
        markup.row(InlineKeyboardButton(get_translate("game_bot", settings.lang), url='https://t.me/EgorGameBot'))
        bot.send_message(chat_id=chat_id, text=get_translate("start", settings.lang), reply_markup=markup)

    elif message_text.startswith("/deleted"):
        if list(limits.keys())[int(settings.user_status)] in ("premium", "admin") or is_admin_id(chat_id):
            generated = deleted(settings=settings, chat_id=chat_id)
            generated.send(chat_id=chat_id)
        else:
            set_commands(settings, chat_id, int(settings.user_status))
            bot.send_message(chat_id=chat_id, text=get_translate("deleted", settings.lang), reply_markup=delmarkup)

    elif message_text.startswith("/week_event_list"):
        generated = week_event_list(settings=settings, chat_id=chat_id)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/weather"):
        if message_text not in ('/weather', f'/weather@{BOT_USERNAME}'):  # Проверяем есть ли аргументы
            nowcity = message_text.split(maxsplit=1)[-1]
        else:
            nowcity = UserSettings(user_id=chat_id).city
        try:
            weather = weather_in(settings=settings, city=nowcity)
            bot.send_message(chat_id=chat_id, text=weather, reply_markup=delmarkup)
        except KeyError:
            bot.send_message(chat_id=chat_id, text=get_translate("weather_invalid_city_name", settings.lang))

    elif message_text.startswith("/forecast"):
        if message_text not in ('/forecast', f'/forecast@{BOT_USERNAME}'):  # Проверяем есть ли аргументы
            nowcity = message_text.split(maxsplit=1)[-1]
        else:
            nowcity = UserSettings(user_id=chat_id).city
        try:
            weather = forecast_in(settings=settings, city=nowcity)
            bot.send_message(chat_id=chat_id, text=weather, reply_markup=delmarkup)
        except KeyError:
            bot.send_message(chat_id=chat_id, text=get_translate("forecast_invalid_city_name", settings.lang))

    elif message_text.startswith("/search"):
        query = ToHTML(message_text[len("/search "):]).replace("--", '').replace("\n", ' ')
        generated = search(settings=settings, chat_id=chat_id, query=query)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/dice"):
        value = bot.send_dice(chat_id=chat_id).json['dice']['value']
        sleep(4)
        bot.send_message(chat_id=chat_id, text=value)

    elif message_text.startswith("/help"):
        bot.send_message(chat_id=chat_id, text=get_translate("help", settings.lang),
                         reply_markup=delmarkup)

    elif message_text.startswith("/settings"):
        text, markup = settings.get_settings()
        bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

    elif message_text.startswith("/today"):
        generated = today_message(settings=settings, chat_id=chat_id, date=now_time_strftime(settings.timezone))
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/sqlite") and is_admin_id(chat_id) and message.chat.type == "private":
        try:
            with open(config.database_path, 'rb') as file:
                bot.send_document(chat_id=chat_id, document=file,
                                  caption=f'{now_time_strftime(settings.timezone)}', reply_markup=databasemarkup)
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text='Отправить файл не получилось')

    elif message_text.startswith("/files") and is_admin_id(chat_id) and message.chat.type == "private":
        try:
            with open("config.py", 'rb') as config_file,\
                 open("lang.py",   'rb') as lang_file, \
                 open("func.py",   'rb') as func_file,\
                 open(__file__,    'rb') as main_file,\
                 open(config.database_path, 'rb') as db_file:
                bot.send_media_group(chat_id=chat_id,
                                     media=[
                                         InputMediaDocument(config_file, caption=f'Файл настроек'),
                                         InputMediaDocument(lang_file,   caption=f'Языковой файл'),
                                         InputMediaDocument(func_file,   caption=f'Файл с функциями'),
                                         InputMediaDocument(main_file,   caption=f'Основной файл'),
                                         InputMediaDocument(db_file,     caption=f'База данных\n\n'
                                                                                 f'Версия от {config.__version__}')
                                     ])
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text='Отправить файл не получилось')

    elif message_text.startswith("/SQL ") and is_admin_id(chat_id) and message.chat.type == "private":
        # Выполнение запроса от админа к базе данных и красивый вывод результатов
        query = message_text[5:].strip()
        file = StringIO()
        file.name = "table.txt"
        try:

            write_table_to_str(file=file,
                               query=query,
                               commit=message_text.endswith("\n--commit=True"))
            file.seek(0)
            bot.send_document(chat_id=chat_id, document=InputFile(file), reply_to_message_id=message.id)
        except Error as e:
            bot.reply_to(message, text=f"{e}")
        finally:
            file.close()

    elif message_text.startswith("/bell"):
        notifications(
            user_id_list=[chat_id],
            from_command=True)

    elif message_text.startswith("/save_to_csv"):
        response, t = CSVCooldown.check(key=chat_id)
        if response:
            bot.send_chat_action(chat_id=message.chat.id, action="upload_document")
            file = StringIO()
            file.name = f"ToDoList {message.from_user.username} ({now_time_strftime(settings.timezone)}).csv"
            res = SQL(f"SELECT event_id, date, status, text FROM root WHERE user_id={chat_id} AND isdel=0;", column_names=True)
            file_writer = csv.writer(file)
            [file_writer.writerows([[str(event_id), event_date, str(event_status), NoHTML(event_text)]])
             for event_id, event_date, event_status, event_text in res]
            file.seek(0)
            try:
                bot.send_document(chat_id=chat_id, document=InputFile(file))
            except ApiTelegramException as e:
                print(f"[main.py -> command_handler -> \"/save_to_csv\"] ApiTelegramException \"{e}\"")
                bot.send_message(chat_id=chat_id, text=get_translate("file_is_too_big", settings.lang))
        else:
            bot.send_message(chat_id=chat_id, text=get_translate("export_csv", settings.lang).format(t=t // 60))

    elif message_text.startswith("/version"):
        bot.send_message(chat_id=chat_id,
                         text=f'Version {config.__version__}')

    elif message_text.startswith("/setuserstatus") and is_admin_id(chat_id):
        if len(message_text.split(" ")) == 3:
            user_id, user_status = message_text.split(" ")[1:]
            try:
                SQL(f"UPDATE settings SET user_status = '{user_status}' WHERE user_id = {user_id};", commit=True)
                if not set_commands(settings, user_id, user_status):
                    raise KeyError
            except IndexError: # Если user_id не существует
                text = "Ошибка: id не существует"
            except Error as e: # Ошибка sqlite3
                text = f'Ошибка базы данных: "{e}"'
            except ApiTelegramException as e:
                text = f'Ошибка telegram api: "{e}"'
            except KeyError:
                text = f'Ошибка user_status'
            else:
                text = 'Успешно изменено'
        else:
            text = "SyntaxError\n/setuserstatus {id} {status}"

        bot.reply_to(message=message, text=text)

    elif message_text.startswith("/id"):
        bot.reply_to(message=message,
                     text=f"@{message.from_user.username}\n"
                          f"Your id <code>{chat_id}</code>")

def callback_handler(settings: UserSettings, chat_id: int, message_id: int, message_text: str,
                     call_data: str, call_id: int, message: Message):
    """
    Отвечает за реакцию бота на нажатия на кнопку
    """
    if call_data == "event_add":
        clear_state(chat_id)
        msg_date = message_text[:10]

        # Проверяем будет ли превышен лимит для пользователя, если добавить 1 событие с 1 символом
        if is_exceeded_limit(chat_id, msg_date, list(limits.values())[int(settings.user_status)], (1, 1)):
            bot.answer_callback_query(callback_query_id=call_id, show_alert=True,
                                      text=get_translate("exceeded_limit", settings.lang))
            return

        SQL(f"UPDATE settings SET add_event_date='{msg_date},{message_id}' WHERE user_id={chat_id};", commit=True)
        bot.answer_callback_query(callback_query_id=call_id,
                                  text=get_translate("send_event_text", settings.lang))
        bot.edit_message_text(f'{ToHTML(message_text)}\n\n0.0.⬜\n{get_translate("send_event_text", settings.lang)}',
                              chat_id, message_id, reply_markup=backmarkup)

    elif call_data == "/calendar":
        bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id,
                              reply_markup=mycalendar(chat_id, settings.timezone, settings.lang))

    elif call_data.startswith("back"):
        # не вызываем await clear_state(chat_id) так как она после очистки вызывает сегодняшнее сообщение
        add_event_date = SQL(f"SELECT add_event_date FROM settings WHERE user_id={chat_id};")[0][0]
        if add_event_date:
            add_event_message_id = add_event_date.split(",")[1]
            if int(message_id) == int(add_event_message_id):
                SQL(f"UPDATE settings SET add_event_date=0 WHERE user_id={chat_id};", commit=True)
        msg_date = message_text[:10]
        if call_data.endswith("bin"):
            deleted(settings=settings, chat_id=chat_id).edit(chat_id=chat_id, message_id=message_id)

        elif len(msg_date.split('.')) == 3:
            try: # Пытаемся изменить сообщение
                generated = today_message(settings=settings, chat_id=chat_id, date=msg_date)
                generated.edit(chat_id=chat_id, message_id=message_id)
            except ApiTelegramException: # Если сообщение не изменено, то шлём календарь
                YY_MM = [int(x) for x in msg_date.split('.')[1:]][::-1] # 'dd.mm.yyyy' -> [yyyy, mm]
                bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id,
                                      reply_markup=mycalendar(chat_id, settings.timezone, settings.lang, YY_MM))

    elif call_data == "message_del":
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException:
            bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

    elif call_data == "set database" and is_admin_id(chat_id):
        try:
            with open(config.database_path, 'rb') as file:
                bot.send_document(chat_id, file,
                                  caption=f'{now_time_strftime(settings.timezone)}\n'
                                          f'На данный момент база выглядит так.',
                                  reply_markup=databasemarkup)
        except ApiTelegramException:
            bot.send_message(chat_id, 'Отправить файл не получилось')

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(f"{message.document.file_name}", "wb") as new_file:
            new_file.write(downloaded_file)
        bot.reply_to(message, 'Файл записан')

    elif call_data == "confirm change":
        text = ToHTML(message_text.split('\n', maxsplit=2)[-1])
        msg_date, *_, event_id = message_text.split("\n", maxsplit=1)[0].split(" ") # TODO изменить парсинг переменных
        try:
            SQL(f"""
                UPDATE root SET text='{text}'
                WHERE user_id={chat_id} AND event_id={event_id}
                AND date='{msg_date}';""", commit=True)
        except Error as e:
            print(f"[main.py -> callback_handler -> \"confirm change\"] Error \"{e}\"")
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("error", settings.lang))
        today_message(settings=settings, chat_id=chat_id, date=msg_date).edit(chat_id=chat_id, message_id=message_id)

    elif call_data in ('event_edit', 'event_status', 'event_del', "event_del bin", "event_recover bin"):
        events_list: list[str, ...] = message_text.split('\n\n')[1:]
        if events_list[0].startswith("👀") or events_list[0].startswith("🕸"):
            return # Заглушка если событий нет

        msg_date = message_text[:10]

        if len(events_list) == 1: # Если событие одно
            event_id = events_list[0].split('.', maxsplit=2)[1]
            if call_data.endswith('bin'): # TODO изменить парсинг переменных
                event_id = events_list[0].split('.', maxsplit=4)[-2]
            try:
                SQL(f"""
                    SELECT text FROM root 
                    WHERE event_id={event_id} AND user_id={chat_id}
                    {'AND isdel!=0' if call_data.endswith('bin') else ''};""")[0][0]
            except IndexError: # Если этого события уже нет
                callback_handler(settings, chat_id, message_id, message_text, "update", call_id, message)
                return
            if call_data == "event_status":
                callback_handler(settings, chat_id, message_id, message_text, f"edit_page_status {event_id} {msg_date}", call_id, message)
                return
            if call_data == "event_del":
                callback_handler(settings, chat_id, message_id, message_text, f"before del {msg_date} {event_id} _", call_id, message)
                return
            elif call_data == "event_del bin":
                event_date, event_id = events_list[0][:10], events_list[0].split('.', maxsplit=4)[-2] # TODO изменить парсинг переменных
                callback_handler(settings, chat_id, message_id, message_text, f"del {event_date} {event_id} bin delete", call_id, message)
                return
            elif call_data == "event_recover bin":
                event_date, event_id = events_list[0][:10], events_list[0].split('.', maxsplit=4)[-2] # TODO изменить парсинг переменных
                callback_handler(settings, chat_id, message_id, message_text, f"recover {event_date} {event_id}", call_id, message)
                return

        markup = InlineKeyboardMarkup()
        for event in events_list:
            if call_data.endswith("bin"):
                event_id = event.split('.', maxsplit=4)[-2] # TODO изменить парсинг переменных
            else:
                event_id = event.split('.', maxsplit=2)[-2]

            try: # Проверяем существование события
                SQL(f"""
                    SELECT text FROM root 
                    WHERE event_id={event_id} AND user_id={chat_id}
                    AND isdel{"!" if call_data.endswith("bin") else ""}=0;""")[0][0]
            except IndexError:
                continue

            if call_data == "event_edit":
                try:
                    # Получаем текст события и убираем html экранирование
                    event_text = NoHTML(
                        SQL(f"SELECT text FROM root WHERE event_id={event_id} AND user_id={chat_id};")[0][0]
                    )
                except Error as e:
                    print(f"[main.py -> callback_handler -> \"event_edit\"] Error \"{e}\"")
                    return
                markup.row(
                    InlineKeyboardButton(text=f"{event}{callbackTab * 20}",
                                         switch_inline_query_current_chat=f"Edit message({event_id}, {msg_date}, "
                                                                          f"{message.id})\n{event_text}"))
            elif call_data == "event_status":
                markup.row(InlineKeyboardButton(f"{event}{callbackTab * 20}",
                                                callback_data=f"edit_page_status {event_id} {msg_date}"))
            elif call_data == "event_del":
                button_title = event.replace('\n', ' ')[:41]
                markup.row(InlineKeyboardButton(f"{button_title}{callbackTab * 20}",
                                                callback_data=f"before del {msg_date} {event_id} _"))
            elif call_data == "event_del bin":
                event_date, event_id = event[:10], event.split('.', maxsplit=4)[-2] # TODO изменить парсинг переменных
                button_title = f"{event_date} {event_id} " + event.split('\n', maxsplit=1)[-1][:50]
                markup.row(InlineKeyboardButton(f"{button_title}{callbackTab * 20}", callback_data=f"del {event_date} {event_id} bin delete")) # before -delete
            elif call_data == "event_recover bin":
                event_date, event_id = event[:10], event.split('.', maxsplit=4)[-2] # TODO изменить парсинг переменных
                button_title = event_date + " " + event_id + " " + event.split('\n')[-1]
                markup.row(InlineKeyboardButton(f"{button_title}{callbackTab * 20}", callback_data=f"recover {event_date} {event_id}"))

        if not markup.to_dict()["inline_keyboard"]:
            callback_handler(settings, chat_id, message_id, message_text, "update", call_id, message)
            return
        markup.row(InlineKeyboardButton("🔙", callback_data="back" if not call_data.endswith("bin") else "back bin"))

        if call_data == 'event_edit': text = f'{msg_date}\n{get_translate("select_event_to_edit", settings.lang)}'
        elif call_data == "event_status": text = f'{msg_date}\n{get_translate("select_event_to_change_status", settings.lang)}'
        elif call_data == 'event_del': text = f'{msg_date}\n{get_translate("select_event_to_delete", settings.lang)}'
        else: text = f'{msg_date}\n{get_translate("choose_event", settings.lang)}'
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("recover"):
        event_date, event_id = call_data.split(maxsplit=2)[1:]
        SQL(f"""
            UPDATE root SET isdel=0
            WHERE user_id={chat_id} AND event_id={event_id}
            AND date='{event_date}';""", commit=True)
        callback_handler(settings, chat_id, message_id, message_text, "back bin", call_id, message)

    elif call_data.startswith('edit_page_status'):
        msg_date = message_text[:10]
        _, event_id, event_date = call_data.split(' ')
        markup = InlineKeyboardMarkup()
        [markup.row(InlineKeyboardButton(f"{status1}{callbackTab * 20}", callback_data=f"set_status {status1.split(maxsplit=1)[0]} {event_id} {event_date}"),
                    InlineKeyboardButton(f"{status2}{callbackTab * 20}", callback_data=f"set_status {status2.split(maxsplit=1)[0]} {event_id} {event_date}"))
         for status1, status2 in get_translate("status_list", settings.lang)]
        markup.row(InlineKeyboardButton("🔙", callback_data="back"))
        text, status = SQL(f"""
            SELECT text, status FROM root
            WHERE user_id={chat_id} AND event_id="{event_id}"
            AND isdel=0 AND date="{event_date}";""")[0]
        bot.edit_message_text(f'{msg_date}\n'
                              f'<b>{get_translate("select_status_to_event", settings.lang)}\n'
                              f'{msg_date}.{event_id}.{status}</b>\n'
                              f'{markdown(text, status, settings.sub_urls)}',
                              chat_id, message_id, reply_markup=markup)

    elif call_data.startswith('set_status'):
        _, status, event_id, event_date = call_data.split()
        SQL(f"""
            UPDATE root SET status='{status}' 
            WHERE user_id={chat_id} AND event_id={event_id} 
            AND date='{event_date}';""", commit=True)
        callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)

    elif call_data.startswith('before del '):
        event_date, event_id, back_to_bin = call_data.split()[2:]
        try:
            text, status = SQL(f"""
                SELECT text, status FROM root
                WHERE user_id={chat_id} AND event_id={event_id} AND date='{event_date}' AND
                isdel{'!' if back_to_bin == 'bin' else ''}0;""")[0]
        except IndexError as e:
            print(f"[main.py -> callback_handler -> \"before del\"] IndexError \"{e}\"")
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("error", settings.lang))
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return
        predelmarkup = generate_buttons([
            {"🔙": "back" if back_to_bin != "bin" else
             "back bin", "❌ "+get_translate("delete_permanently", settings.lang): f"{call_data.split(maxsplit=1)[-1]} delete"}])

        if (list(limits.keys())[int(settings.user_status)] in ("premium", "admin") and back_to_bin != "bin") or is_admin_id(chat_id):
            predelmarkup.row(InlineKeyboardButton("🗑 "+get_translate("trash_bin", settings.lang), callback_data=f"{call_data.split(maxsplit=1)[-1]} to_bin"))

        end_text = get_translate("/deleted", settings.lang) if (list(limits.keys())[int(settings.user_status)] in ("premium", "admin") or is_admin_id(chat_id)) else ""
        day = DayInfo(settings, event_date)
        bot.edit_message_text(f'<b>{event_date}.{event_id}.</b>{status} <u><i>{day.str_date}  {day.week_date}</i> {day.relatively_date}</u>\n'
                              f'<b>{get_translate("are_you_sure", settings.lang)}:</b>\n'
                              f'{text[:3800]}\n\n'
                              f'{end_text}', chat_id, message_id,
                              reply_markup=predelmarkup)

    elif call_data.startswith('del '):
        event_date, event_id, where, mode = call_data.split(maxsplit=4)[1:]
        try:
            if (list(limits.keys())[int(settings.user_status)] in ("premium", "admin") or is_admin_id(chat_id)) and mode == "to_bin":
                SQL(f"""
                    UPDATE root SET isdel='{now_time_strftime(settings.timezone)}' 
                    WHERE user_id={chat_id} AND date='{event_date}' AND event_id={event_id};""", commit=True)
            else:
                SQL(f"""
                    DELETE FROM root 
                    WHERE user_id={chat_id} AND date='{event_date}' AND event_id={event_id};""", commit=True)
        except Error as e:
            print(f"[main.py -> callback_handler -> \"del\"] Error \"{e}\"")
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("error", settings.lang))
        callback_handler(settings, chat_id, message_id, message_text, "back" if where != "bin" else "back bin", call_id, message)

    elif call_data.startswith('|'): # Список id событий на странице
        page, id_list = call_data.split("|")[1:]
        id_list = id_list.split(",")
        try:
            if message_text.startswith("🔍 "): # Поиск
                query = ToHTML(message_text.split('\n', maxsplit=1)[0].split(maxsplit=2)[-1][:-1])
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
                    generated = recurring(settings=settings, date=msg_date, chat_id=chat_id, id_list=id_list, page=page[1:])
                else:
                    generated = today_message(settings=settings, chat_id=chat_id, date=msg_date, id_list=id_list, page=page)
                generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

            elif message_text.startswith("🔔"): # Будильник
                notifications(user_id_list=[chat_id], id_list=id_list, page=page, message_id=message_id, markup=message.reply_markup)

        except ApiTelegramException as e:
            print(f"[main.py -> callback_handler -> \"|\"] ApiTelegramException \"{e}\"")
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("already_on_this_page", settings.lang))

    elif call_data.startswith('generate month calendar '):
        sleep(0.5)  # Задержка
        YY = int(call_data.split()[-1])
        if 1980 <= YY <= 3000:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id,
                                          reply_markup=generate_month_calendar(settings.timezone, settings.lang,
                                                                               chat_id, YY))
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data.startswith('generate calendar '):
        YY_MM = [int(i) for i in call_data.split()[-2:]]
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id,
                                      reply_markup=mycalendar(chat_id, settings.timezone, settings.lang, YY_MM))

    elif call_data == 'year now':
        try:
            markup = generate_month_calendar(settings.timezone, settings.lang,
                                             chat_id, now_time(settings.timezone).year)
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        except ApiTelegramException:
            callback_handler(settings, chat_id, message_id, message_text, '/calendar', call_id, message)

    elif call_data.startswith('settings'):
        par_name, par_val = call_data.split(' ', maxsplit=2)[1:]
        if isinstance(par_val, str):
            SQL(f"UPDATE settings SET {par_name}='{par_val}' WHERE user_id={chat_id};", commit=True)
        else:
            SQL(f"UPDATE settings SET {par_name}={par_val} WHERE user_id={chat_id};", commit=True)

        settings = UserSettings(chat_id)
        set_commands(settings, chat_id, settings.user_status)
        text, markup = settings.get_settings()
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        except ApiTelegramException:
            pass

    elif call_data.startswith('recurring'):
        generated = recurring(settings=settings, date=message_text[:10], chat_id=chat_id)
        generated.edit(chat_id=chat_id, message_id=message_id)

    elif call_data in ('<<<', '>>>'):
        msgdate = [int(i) for i in message_text.split(maxsplit=1)[0].split('.')]
        new_date = datetime(*msgdate[::-1])
        sleep(0.5)  # Задержка
        if 1980 < new_date.year < 3000:
            if call_data == '<<<': new_date -= timedelta(days=1)
            if call_data == '>>>': new_date += timedelta(days=1)
            new_date = '.'.join(f'{new_date}'.split(maxsplit=1)[0].split('-')[::-1])
            generated = today_message(settings=settings, chat_id=chat_id, date=new_date)
            generated.edit(chat_id=chat_id, message_id=message_id)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data in ('<<', '<', '⟳', '>', '>>'):
        # TODO Парсить из текста, а не из кнопок
        mydatatime = [int(i) for i in message.json["reply_markup"]['inline_keyboard'][0][0]["text"].split()[-3][1:-1].split('.')[::-1]]
        # получаем [2023, 4] [year, month]
        if call_data == '<': mydatatime = [mydatatime[0] - 1, 12] if mydatatime[1] == 1 else [mydatatime[0], mydatatime[1] - 1]
        if call_data == '>': mydatatime = [mydatatime[0] + 1, 1] if mydatatime[1] == 12 else [mydatatime[0], mydatatime[1] + 1]
        if call_data == '<<': mydatatime[0] -= 1
        if call_data == '>>': mydatatime[0] += 1
        if call_data == '⟳': mydatatime = new_time_calendar(settings.timezone)
        if 1980 <= mydatatime[0] <= 3000:
            sleep(0.5)  # Задержка
            try:
                bot.edit_message_reply_markup(chat_id=chat_id,
                                              message_id=message_id,
                                              reply_markup=mycalendar(chat_id,
                                                                      settings.timezone,
                                                                      settings.lang,
                                                                      mydatatime))
            except ApiTelegramException:  # Если нажата кнопка ⟳, но сообщение не изменено
                generated = today_message(settings=settings, chat_id=chat_id, date=now_time_strftime(settings.timezone))
                generated.edit(chat_id=chat_id, message_id=message_id)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif re_call_data_date.search(call_data):
        generated = today_message(settings=settings, chat_id=chat_id, date=call_data)
        generated.edit(chat_id=chat_id, message_id=message_id)

    elif call_data == "update":
        if message_text.startswith('🔍 '):  # Поиск
            query = ToHTML(message_text.split('\n', maxsplit=1)[0].split(maxsplit=2)[-1][:-1])
            generated = search(settings=settings, chat_id=chat_id, query=query)
            generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

        elif message_text.startswith('📆'):  # Если /week_event_list
            generated = week_event_list(settings=settings, chat_id=chat_id)
            generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

        elif message_text.startswith('🗑'):  # Корзина
            generated = deleted(settings=settings, chat_id=chat_id)
            generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)

        elif re_date.match(message_text) is not None:
            msg_date = re_date.match(message_text)[0]
            generated = today_message(settings=settings, chat_id=chat_id, date=msg_date)
            generated.edit(chat_id=chat_id, message_id=message_id, markup=message.reply_markup)


@bot.message_handler(commands=[*COMMANDS])
@execution_time
def message_handler(message: Message):
    """
    Ловит команды от пользователей
    """
    chat_id, message_text = message.chat.id, message.text
    settings = UserSettings(chat_id)
    main_log(user_status=settings.user_status, chat_id=chat_id, text=message_text, action="send   ")
    command_handler(settings, chat_id, message_text, message)

@bot.callback_query_handler(func=lambda call: True)
@execution_time
def callback_query_handler(call: CallbackQuery):
    """
    Ловит нажатия на кнопки
    """
    chat_id, message_id, call_data, message_text = call.message.chat.id, call.message.id, call.data, call.message.text
    settings = UserSettings(chat_id)
    main_log(user_status=settings.user_status, chat_id=chat_id, text=call_data, action="pressed")
    if call.data == 'None':
        return 0
    callback_handler(settings, chat_id, message_id, call.message.text, call.data, call.id, call.message)

@bot.message_handler(func=lambda m: m.text.startswith('#'))
@execution_time
def get_search_message(message: Message):
    """
    Ловит сообщения поиска
    """
    query = ToHTML(message.text[1:].replace("--", '').replace("\n", ' '))
    chat_id = message.chat.id
    settings = UserSettings(user_id=chat_id)
    main_log(user_status=settings.user_status, chat_id=chat_id, text=message.text, action="search ")
    generated = search(settings=settings, chat_id=chat_id, query=query)
    generated.send(chat_id=chat_id)

@bot.message_handler(func=lambda m: m.text.startswith(f'@{BOT_USERNAME} Edit message(') and re_edit_message.search(m.text))
@execution_time
def get_edit_message(message: Message):
    """
    Ловит сообщения для изменения событий
    """
    chat_id = message.chat.id
    edit_message_id = message.id
    settings = UserSettings(chat_id)
    res = re_edit_message.search(message.text)[0]
    event_id = int(re.findall(r"\((\d+)", res)[0])
    msg_date = re.findall(r" (\d{1,2}\.\d{1,2}\.\d{4}),", res)[0]
    message_id = int(re.findall(r", (\d+)\)", res)[0])
    text = message.text.split('\n', maxsplit=1)[-1].strip("\n") # ВАЖНО!
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(f"{event_id} {text[:20]}{callbackTab * 20}",
                                    switch_inline_query_current_chat=f"{message.text.split(maxsplit=1)[-1]}"))
    markup.row(InlineKeyboardButton("✖", callback_data="message_del"))
    tag_len_max = len(text) > 3800
    tag_limit_exceeded = is_exceeded_limit(chat_id, msg_date, list(limits.values())[int(settings.user_status)], (len(text), 0))
    tag_len_less = len(text) < len(SQL(f"""
        SELECT text FROM root
        WHERE user_id={chat_id} AND event_id='{event_id}'
        AND date='{msg_date}' AND isdel=0;""")[0][0])

    if tag_len_max:
        bot.reply_to(message, get_translate("message_is_too_long", settings.lang), reply_markup=markup)
    elif tag_limit_exceeded and not tag_len_less:
        bot.reply_to(message, get_translate("exceeded_limit", settings.lang), reply_markup=markup)
    else:
        try:
            day = DayInfo(settings, msg_date)
            bot.edit_message_text((f"""
{msg_date} <u><i>{day.str_date}  {day.week_date}</i> {day.relatively_date}</u> {event_id}
<b>{get_translate("are_you_sure_edit", settings.lang)}</b>
<i>{ToHTML(text)}</i>
"""), chat_id, message_id, reply_markup=generate_buttons([{"🔙": "back", "✅": 'confirm change'}]))
        except ApiTelegramException as e:
            print(f"[main.py -> get_edit_message] ApiTelegramException \"{e}\"")
            return
    try:
        bot.delete_message(chat_id, edit_message_id)
    except ApiTelegramException:
        bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

@bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.text.startswith('⚙️') and m.from_user.id != BOT_ID)
@execution_time
def get_search_message(message: Message):
    """
    Ловит сообщения ответ на сообщение бота с настройками
    Изменение города пользователя
    """
    chat_id, message_id = message.chat.id, message.id
    settings = UserSettings(chat_id)
    callback_handler(settings, chat_id, message.reply_to_message.id, message.text, f'settings city {message.text[:25]}', 0, message.reply_to_message)
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
    chat_id, message_id, message_text = message.chat.id, message.message_id, message.text
    msg_date = SQL(f"SELECT add_event_date FROM settings WHERE user_id={chat_id};")[0][0].split(",")[0]
    settings = UserSettings(chat_id)

    # Если сообщение команда то проигнорировать
    if message_text.lower().split("@")[0][1:] in COMMANDS:
        return

    # Если сообщение длиннее 3800 символов, то ошибка
    if len(message_text) >= 3800:
        bot.reply_to(message, get_translate("message_is_too_long", settings.lang), reply_markup=delmarkup)

    # Пытаемся создать событие
    if create_event(chat_id, msg_date, ToHTML(message_text)):
        clear_state(chat_id)
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException: # Если в группе у бота нет прав для удаления сообщений
            bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)
    else:
        bot.reply_to(message, get_translate("error", settings.lang), reply_markup=delmarkup)
        clear_state(chat_id)


def schedule_loop():
    # link = "link"
    # headers = {
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    #                   "Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.42"
    # }
    while True:
        while_time = now_time(config.hours_difference)
        if while_time.minute == 0:
            notifications()
        # if while_time.minute in (0, 30):
        #     print(log_time_strftime(), link, get(link, headers=headers).status_code)
        sleep(60)

if __name__ == "__main__":
    if config.notifications:
        Thread(target=schedule_loop, daemon=True).start()
    bot.infinity_polling()
