from io import StringIO
from time import sleep
import csv

from telebot import TeleBot
from telebot.types import CallbackQuery, Message, InputFile
from telebot.types import BotCommandScopeChat    # Команды для определённого чата
from telebot.types import BotCommandScopeDefault # Дефолтные команды для всех остальных
from telebot.types import InputMediaDocument     # Команда /files шлёт все файлы бота в одном сообщении
from telebot.apihelper import ApiTelegramException

from func import * # InlineKeyboardMarkup, InlineKeyboardButton, re, config импортируются из func


"""Для цветных логов (Выполнять только для Windows)"""
if Windows := 0:
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
    return (f"{val!s:<5}" if keylist[key] == str(val) else f"\033[31m{val!s:<5}\033[0m{indent}"
            ) if key in keylist else f"{val}" # \033[32m{}\033[0m{indent}

print(f"+{'-'*59}+\n"+''.join(f'| {k: >27} = {check(k, v): <27} |\n' for k, v in Me.to_dict().items())+f"+{'-'*59}+")

bot.disable_web_page_preview = True
bot.parse_mode = "html"

def send(self, chat_id: int) -> None:
    bot.send_message(chat_id=chat_id, text=self.text, reply_markup=self.reply_markup)

def edit(self, *, chat_id: int, message_id: int, only_markup: bool = False, only_text: InlineKeyboardMarkup = None) -> None:
    if only_markup:
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=self.reply_markup)
    else:
        if only_text is not None:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=self.text, reply_markup=only_text)
        else:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=self.text, reply_markup=self.reply_markup)

MyMessage.send = send
MyMessage.edit = edit

def set_commands(settings: UserSettings, chat_id: int, user_status: int | str = 0) -> bool:
    """
    Ставит список команд для пользователя chat_id
    """
    target = f"{user_status}_command_list"
    lang = settings.lang
    try:
        return bot.set_my_commands(commands=get_translate(target, lang), scope=BotCommandScopeChat(chat_id=chat_id))
    except (ApiTelegramException, KeyError) as e:
        print(f'Ошибка set_commands: "{e}"')
        return False

# Ставим дефолтные команды для всех пользователей при запуске бота
bot.set_my_commands(commands=get_translate("0_command_list", "ru"), scope=BotCommandScopeDefault())

def command_handler(settings: UserSettings,
                    chat_id: int,
                    message_text: str,
                    message: Message) -> None:
    """
    Отвечает за реакцию бота на команды
    Метод message.text.startswith("") используется для групп (в них сообщение приходит в формате /command{BOT_USERNAME})
    """
    if message_text.startswith('/calendar'):
        bot.send_message(chat_id, 'Выберите дату',
                         reply_markup=mycalendar(chat_id, settings.timezone, settings.lang))

    elif message_text.startswith('/start'):
        set_commands(settings, chat_id, settings.user_status)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("/calendar", callback_data="/calendar"))
        markup.row(InlineKeyboardButton(get_translate("add_bot_to_group", settings.lang),
                                        url=f'https://t.me/{BOT_USERNAME}?startgroup=AddGroup'))
        markup.row(InlineKeyboardButton(get_translate("game_bot", settings.lang), url='https://t.me/EgorGameBot'))
        bot.send_message(chat_id=chat_id, text=get_translate("start", settings.lang), reply_markup=markup)

    elif message_text.startswith('/deleted'):
        if list(limits.keys())[int(settings.user_status)] in ("premium", "admin") or is_admin_id(chat_id):
            generated = deleted(settings=settings, chat_id=chat_id)
            generated.send(chat_id=chat_id)
        else:
            set_commands(settings, chat_id, int(settings.user_status))
            bot.send_message(chat_id=chat_id, text=get_translate("deleted", settings.lang), reply_markup=delmarkup)

    elif message_text.startswith('/week_event_list'):
        generated = week_event_list(settings=settings, chat_id=chat_id)
        generated.send(chat_id=chat_id)

    elif message_text.startswith('/weather'):
        if message_text not in ('/weather', f'/weather@{BOT_USERNAME}'):  # Проверяем есть ли аргументы
            nowcity = message_text.split(maxsplit=1)[-1]
        else:
            nowcity = UserSettings(user_id=chat_id).city
        try:
            weather = weather_in(settings=settings, city=nowcity)
            bot.send_message(chat_id=chat_id, text=weather, reply_markup=delmarkup)
        except KeyError:
            bot.send_message(chat_id=chat_id, text=get_translate("weather_invalid_city_name", settings.lang))

    elif message_text.startswith('/forecast'):
        if message_text not in ('/forecast', f'/forecast@{BOT_USERNAME}'):  # Проверяем есть ли аргументы
            nowcity = message_text.split(maxsplit=1)[-1]
        else:
            nowcity = UserSettings(user_id=chat_id).city
        try:
            weather = forecast_in(settings=settings, city=nowcity)
            bot.send_message(chat_id=chat_id, text=weather, reply_markup=delmarkup)
        except KeyError:
            bot.send_message(chat_id=chat_id, text=get_translate("forecast_invalid_city_name", settings.lang))

    elif message_text.startswith('/search'):
        query = ToHTML(message_text[len("/search "):]).replace("--", '').replace("\n", ' ')
        generated = search(settings=settings, chat_id=chat_id, query=query)
        generated.send(chat_id=chat_id)

    elif message_text.startswith('/dice'):
        value = bot.send_dice(chat_id=chat_id).json['dice']['value']
        sleep(4)
        bot.send_message(chat_id=chat_id, text=value)

    elif message_text.startswith('/help'):
        bot.send_message(chat_id=chat_id, text=get_translate("help", settings.lang),
                         reply_markup=delmarkup)

    elif message_text.startswith('/settings'):
        settings_lang, sub_urls, city, timezone_, direction, markup = settings.get_settings_markup()
        text = get_translate("settings", settings.lang).format(settings_lang, bool(sub_urls), city, timezone_, direction)
        bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

    elif message_text.startswith('/today'):
        generated = today_message(settings=settings, chat_id=chat_id, date=now_time_strftime(settings.timezone))
        generated.send(chat_id=chat_id)

    elif message_text.startswith('/sqlite') and is_admin_id(chat_id):
        try:
            with open(config.database_path, 'rb') as file:
                bot.send_document(chat_id=chat_id, document=file,
                                  caption=f'{now_time_strftime(settings.timezone)}', reply_markup=databasemarkup)
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text='Отправить файл не получилось')

    elif message_text.startswith('/files') and is_admin_id(chat_id):
        try:
            with open(__file__,       'rb') as main_file,\
                    open("func.py",   'rb') as func_file,\
                    open("config.py", 'rb') as config_file,\
                    open("lang.py",   'rb') as lang_file, \
                    open(config.database_path, 'rb') as db_file:
                bot.send_media_group(chat_id=chat_id,
                                     media=[
                                         InputMediaDocument(main_file,   caption=f'Основной файл'),
                                         InputMediaDocument(func_file,   caption=f'Файл с функциями'),
                                         InputMediaDocument(config_file, caption=f'Файл настроек'),
                                         InputMediaDocument(lang_file,   caption=f'Языковой файл'),
                                         InputMediaDocument(db_file,     caption=f'База данных\n\n'
                                                                                 f'Версия от {config.__version__}')
                                     ])
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text='Отправить файл не получилось')

    elif message_text.startswith('/SQL ') and is_admin_id(chat_id) and message.chat.type == "private":
        # TODO Выполнение запроса от админа к базе данных и красивый вывод результатов
        # query = message_text[5:].strip()
        # try:
        #     res = SQL(query, commit=message_text.endswith("\ncommit=True"))
        #     # Возможно сделать вывод в виде таблицы
        #     # Если ширина или высоты больше чем сообщение, то вывод в .txt файле
        #     res = str_table(res)
        # except Error as e:
        #     res = f'Ошибка: "{e}"'
        #
        res = "Not added yet 🫤"
        bot.reply_to(message, text=res)

    elif message_text.startswith('/bell') and is_admin_id(chat_id): # TODO уведомления
        # bot.send_message(chat_id=chat_id, text=check_bells(settings, chat_id), reply_markup=delmarkup)
        bot.send_message(chat_id=chat_id, text="Not added yet 🫤")

    elif message_text.startswith('/save_to_csv'):
        try:
            response, t = CSVCooldown.check(key=chat_id)
            if response:
                bot.send_chat_action(chat_id=message.chat.id, action='upload_document')
                res = SQL(f'SELECT event_id, date, status, text FROM root WHERE user_id={chat_id} AND isdel=0;')
                file = StringIO()
                file.name = f'ToDoList {message.from_user.username} ({now_time_strftime(settings.timezone)}).csv'
                file_writer = csv.writer(file)
                file_writer.writerows([['event_id', 'date', 'status', 'text']])
                [file_writer.writerows([[str(event_id), date, str(status), NoHTML(text)]]) for event_id, date, status, text in res]
                file.seek(0)
                bot.send_document(chat_id=chat_id, document=InputFile(file))
            else:
                bot.send_message(chat_id=chat_id, text=get_translate("export_csv", settings.lang).format(t=t//60))
        except ApiTelegramException as e:
            print(f'/save_to_csv "{e}"')
            bot.send_message(chat_id=chat_id, text=get_translate("file_is_too_big", settings.lang))

    elif message_text.startswith('/version'):
        bot.send_message(chat_id=chat_id,
                         text=f'Version {config.__version__}')

    elif message_text.startswith('/setuserstatus') and is_admin_id(chat_id):
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

def callback_handler(settings: UserSettings,
                     chat_id: int,
                     message_id: int,
                     message_text: str,
                     call_data: str,
                     call_id: int,
                     message: Message):
    """
    Отвечает за реакцию бота на нажатия на кнопку
    """
    if call_data == "event_add":
        bot.clear_step_handler_by_chat_id(chat_id)
        message_date = message_text.split(maxsplit=1)[0]
        if is_exceeded_limit(chat_id, message_date, list(limits.values())[int(settings.user_status)], (1, 1)):
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("exceeded_limit", settings.lang), show_alert=True)
            return 0
        bot.edit_message_text(f'{ToHTML(message_text)}\n\n0.0.⬜\n{get_translate("send_event_text", settings.lang)}',
                              chat_id, message_id, reply_markup=backmarkup)

        def add_event(message2):
            if message2.text.lower().split("@")[0] not in COMMANDS:
                if len(message2.text) <= 3800:
                    if create_event(message2.chat.id, message_date, ToHTML(message2.text)):
                        generated2 = today_message(settings=settings, chat_id=chat_id, date=message_date)
                        generated2.edit(chat_id=chat_id, message_id=message_id)
                        try:
                            bot.delete_message(message2.chat.id, message2.message_id)
                        except ApiTelegramException:
                            bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)
                    else:
                        bot.reply_to(message, get_translate("error", settings.lang), reply_markup=delmarkup)
                else:
                    bot.reply_to(message, get_translate("message_is_too_long", settings.lang), reply_markup=delmarkup)

        bot.register_next_step_handler(message, add_event)

    elif call_data == '/calendar':
        bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id,
                              reply_markup=mycalendar(chat_id, settings.timezone, settings.lang))

    elif call_data.startswith('back'):
        bot.clear_step_handler_by_chat_id(chat_id)
        msg_date = message_text[:10] # .split(maxsplit=1)[0]
        if call_data.endswith("bin"):
            deleted(settings=settings, chat_id=chat_id).edit(chat_id=chat_id, message_id=message_id)

        elif len(msg_date.split('.')) == 3:
            try:
                generated = today_message(settings=settings, chat_id=chat_id, date=msg_date)
                generated.edit(chat_id=chat_id, message_id=message_id)
            except ApiTelegramException:
                YY_MM = [int(x) for x in msg_date.split('.')[1:]][::-1]
                bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id,
                                      reply_markup=mycalendar(chat_id, settings.timezone, settings.lang, YY_MM))

    elif call_data == "message_del":
        bot.clear_step_handler_by_chat_id(chat_id)
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException:
            bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

    elif call_data == "set database":
        DATE = now_time_strftime(settings.timezone)
        try:
            with open(config.database_path, 'rb') as file:
                bot.send_document(chat_id, file, caption=f'{DATE}\nНа данный момент база выглядит так.', reply_markup=databasemarkup)
        except ApiTelegramException:
            bot.send_message(chat_id, 'Отправить файл не получилось')

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(f"{message.document.file_name}", "wb") as new_file:
            new_file.write(downloaded_file)
        bot.reply_to(message, 'Файл записан')

    elif call_data == 'Edit Edit':
        text = ToHTML(message_text.split('\n', maxsplit=2)[-1])
        msg_date, *_, event_id = message_text.split("\n", maxsplit=1)[0].split(" ")
        try:
            SQL(f"UPDATE root SET text = '{text}' "
                f"WHERE user_id={chat_id} AND event_id={event_id} AND date='{msg_date}';", commit=True)
        except Error as e:
            print(e)
        else:
            generated = today_message(settings=settings, chat_id=chat_id, date=msg_date)
            generated.edit(chat_id=chat_id, message_id=message_id)

    elif call_data in ('event_edit', 'event_status', 'event_del', "event_del bin", "event_recover bin"):
        bot.clear_step_handler_by_chat_id(chat_id)
        res = message_text.split('\n\n')[1:]
        if res[0].startswith("👀") or res[0].startswith("🕸"):
            return 0
        markup = InlineKeyboardMarkup()
        msg_date = message_text.split(maxsplit=1)[0]
        for i in res:
            event_id = i.split('.', maxsplit=2)[1]
            if call_data == 'event_edit':
                try:
                    event_text = NoHTML(SQL(f"SELECT text FROM root "
                                            f"WHERE event_id={event_id} AND user_id={chat_id};")[0][0])
                except Error as e:
                    return print(f'Произошла ошибка в "Изменить сообщение": "{e}"')
                markup.row(InlineKeyboardButton(f"{i}{callbackTab * 20}", switch_inline_query_current_chat=f"Edit message({event_id}, {msg_date}, {message.id})\n{event_text}"))
            if call_data == "event_status":
                markup.row(InlineKeyboardButton(f"{i}{callbackTab * 20}", callback_data=f"edit_page_status {event_id} {msg_date}"))
            if call_data == "event_del":
                Btitle = i.replace('\n', ' ')[:41]
                markup.row(InlineKeyboardButton(f"{Btitle}{callbackTab * 20}", callback_data=f"PRE DEL {msg_date} {event_id} _"))
            elif call_data == "event_del bin":
                event_date = i[:10]
                event_id = i.split('.', maxsplit=4)[-2]
                Btitle = event_date + " " + event_id + " " + i.split('\n')[-1]
                markup.row(InlineKeyboardButton(f"{Btitle}{callbackTab * 20}", callback_data=f"DEL {event_date} {event_id} bin delete")) # PRE -delete
            elif call_data == "event_recover bin":
                event_date = i[:10]
                event_id = i.split('.', maxsplit=4)[-2]
                Btitle = event_date + " " + event_id + " " + i.split('\n')[-1]
                markup.row(InlineKeyboardButton(f"{Btitle}{callbackTab * 20}", callback_data=f"recover {event_date} {event_id}"))

        markup.row(InlineKeyboardButton("🔙", callback_data="back" if not call_data.endswith("bin") else "back bin"))

        if call_data == 'event_edit': text = f'{msg_date}\n{get_translate("select_event_to_edit", settings.lang)}'
        elif call_data == "event_status": text = f'{msg_date}\n{get_translate("select_event_to_change_status", settings.lang)}'
        elif call_data == 'event_del': text = f'{msg_date}\n{get_translate("select_event_to_delete", settings.lang)}'
        else: text = f'{msg_date}\n{get_translate("choose_event", settings.lang)}'
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("recover"):
        event_date, event_id = call_data.split(maxsplit=2)[1:]
        SQL(f"UPDATE root SET isdel = 0 "
            f"WHERE user_id = {chat_id} AND date = '{event_date}' AND event_id = {event_id};", commit=True)
        callback_handler(settings, chat_id, message_id, message_text, "back bin", call_id, message)

    elif call_data.startswith('edit_page_status'):
        _, event_id, event_date = call_data.split(' ')
        markup = InlineKeyboardMarkup()
        status_list = get_translate("status_list", settings.lang)
        [markup.row(InlineKeyboardButton(f"{status1}{callbackTab * 20}", callback_data=f"set_status {status1.split(maxsplit=1)[0]} {event_id} {event_date}"),
                    InlineKeyboardButton(f"{status2}{callbackTab * 20}", callback_data=f"set_status {status2.split(maxsplit=1)[0]} {event_id} {event_date}"))
         for status1, status2 in status_list]
        markup.row(InlineKeyboardButton("🔙", callback_data="back"))
        text, status = SQL(f'SELECT text, status FROM root '
                           f'WHERE event_id="{event_id}" AND user_id = {chat_id} AND date = "{event_date}" AND isdel == 0;')[0]
        bot.edit_message_text(f'{message_text.split(maxsplit=1)[0]}\n<b>{get_translate("select_status_to_event", settings.lang)}\n'
                              f'{event_id}.</b>{status}\n{markdown(text, status, settings.sub_urls)}',
                              chat_id, message_id, reply_markup=markup)

    elif call_data.startswith('set_status'):
        _, status, event_id, event_date = call_data.split()
        SQL(f"UPDATE root SET status = '{status}' "
            f"WHERE user_id = {chat_id} AND event_id = {event_id} AND date = '{event_date}';", commit=True)
        callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)

    elif call_data.startswith('PRE DEL '):
        event_date, event_id, back_to_bin = call_data.split()[2:]
        try:
            text, status = SQL(f"SELECT text, status FROM root "
                               f"WHERE isdel {'==' if back_to_bin != 'bin' else '!='} 0 AND user_id = {chat_id} "
                               f"AND date = '{event_date}' AND event_id = {event_id};")[0]
        except Error as e:
            print(f'Ошибка SQL в PRE DEL : "{e}"')
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return
        predelmarkup = generate_buttons([{"🔙": "back" if back_to_bin != "bin" else "back bin", "❌ "+get_translate("delete_permanently", settings.lang): f"{call_data[4:]} delete"}])
        if list(limits.keys())[int(settings.user_status)] in ("premium", "admin") and back_to_bin != "bin":
            predelmarkup.row(InlineKeyboardButton("🗑 "+get_translate("trash_bin", settings.lang), callback_data=f"{call_data[4:]} to_bin"))

        end_text = get_translate("/deleted", settings.lang) if list(limits.keys())[int(settings.user_status)] in ("premium", "admin") else ""
        day = DayInfo(settings, event_date)
        bot.edit_message_text(f'<b>{event_date}.{event_id}.</b>{status} <u><i>{day.str_date}  {day.week_date}</i> {day.relatively_date}</u>\n'
                              f'<b>{get_translate("are_you_sure", settings.lang)}:</b>\n'
                              f'{text[:3800]}\n\n'
                              f'{end_text}', chat_id, message_id,
                              reply_markup=predelmarkup)

    elif call_data.startswith('DEL '):
        event_date, event_id, where, mode = call_data.split(maxsplit=4)[1:]
        try:
            if list(limits.keys())[int(settings.user_status)] in ("premium", "admin") and mode == "to_bin":
                SQL(f"UPDATE root SET isdel = '{now_time_strftime(settings.timezone)}' "
                    f"WHERE user_id = {chat_id} AND date = '{event_date}' AND event_id = {event_id};", commit=True)
            else:
                SQL(f"DELETE FROM root "
                    f"WHERE user_id = {chat_id} AND date = '{event_date}' AND event_id = {event_id};", commit=True)
        except Error as e:
            print(e)
            bot.edit_message_text(f'{event_date}\n{get_translate("error", settings.lang)}', chat_id, message_id,
                                  reply_markup=backmarkup)
            return
        callback_handler(settings, chat_id, message_id, message_text, "back" if where != "bin" else "back bin", call_id, message)

    elif call_data.startswith('|'):
        id_list = call_data[1:].split(",")
        try:
            if message_text.startswith('🔍 '): # Поиск
                query = message_text.split('\n', maxsplit=1)[0].split(maxsplit=2)[-1][:-1]
                generated = search(settings=settings, chat_id=chat_id, query=query, id_list=id_list)
                generated.edit(chat_id=chat_id, message_id=message_id, only_text=message.reply_markup)

            elif message_text.startswith('📆'): # Если /week_event_list
                generated = week_event_list(settings=settings, chat_id=chat_id, id_list=id_list)
                generated.edit(chat_id=chat_id, message_id=message_id, only_text=message.reply_markup)

            elif message_text.startswith('🗑'): # Корзина
                generated = deleted(settings=settings, chat_id=chat_id, id_list=id_list)
                generated.edit(chat_id=chat_id, message_id=message_id, only_text=message.reply_markup)

            elif (res := re_date.match(message_text)) is not None:
                msg_date, result_text = res[0], ''
                generated = today_message(settings=settings, chat_id=chat_id, date=msg_date, id_list=id_list)
                generated.edit(chat_id=chat_id, message_id=message_id, only_text=message.reply_markup)
        except ApiTelegramException as e:
            print(f'| ошибка "{e}"')
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("already_on_this_page", settings.lang))

    elif call_data.startswith('generate_month_calendar '):
        sleep(0.5)  # Задержка
        YY = int(call_data.split(' ')[-1])
        if 1980 <= YY <= 3000:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id,
                                          reply_markup=generate_month_calendar(settings.timezone, settings.lang,
                                                                               chat_id, YY))
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data.startswith('generate_calendar '):
        # sleep(0.5)  # Задержка
        YY_MM = [int(i) for i in call_data.split()[1:]]
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
            SQL(f"UPDATE settings SET {par_name}='{par_val}' WHERE user_id = {chat_id};", commit=True)
        else:
            SQL(f"UPDATE settings SET {par_name}={par_val} WHERE user_id = {chat_id};", commit=True)

        settings = UserSettings(chat_id)
        set_commands(settings, chat_id, settings.user_status)
        settings_lang, sub_urls, city, timezone_, direction,  markup = settings.get_settings_markup()
        text = get_translate("settings", settings.lang)
        try:
            bot.edit_message_text(text.format(settings_lang, bool(sub_urls), city, timezone_, direction), chat_id, message_id, reply_markup=markup)
        except ApiTelegramException:
            pass

    elif call_data.startswith('!birthday'):
        msg_date = message_text.split(maxsplit=1)[0]
        generated = MyMessage(settings=settings, date=msg_date, reply_markup=backmarkup)
        generated.get_data(WHERE=f"""
        isdel = 0 AND user_id = {chat_id} AND 
        ((date LIKE '{msg_date[:-5]}.____' AND status IN ('🎉', '🎊', '📆')) OR
        (strftime('%w', {sqlite_format_date('date')}) = 
        CAST(strftime('%w', '{sqlite_format_date2(msg_date)}') as TEXT) AND status IN ('🗞')))
        """,
                           direction={"⬇️": "DESC", "⬆️": "ASC"}[settings.direction],
                           prefix="!")
        generated.format(title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n",
                         args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                         if_empty=get_translate("nothing_found", settings.lang))
        generated.edit(chat_id=chat_id, message_id=message_id)

    elif call_data.startswith("!"):
        msg_date = message_text.split(maxsplit=1)[0]
        generated = MyMessage(settings=settings, date=msg_date, reply_markup=backmarkup)
        generated.get_events(WHERE=f'date LIKE "{msg_date[:-5]}.____" AND isdel = 0 AND user_id = {chat_id} AND status IN ("🎉", "🎊")',
                             values=call_data[1:].split(","))
        generated.format(title="{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n",
                         args="<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
                         if_empty=get_translate("nothing_found", settings.lang))
        try:
            generated.edit(chat_id=chat_id, message_id=message_id, only_text=message.reply_markup)
        except ApiTelegramException as e:
            print(f'| ошибка "{e}"')
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("already_on_this_page", settings.lang))

    elif call_data in ('<<<', '>>>'):
        bot.clear_step_handler_by_chat_id(chat_id)
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


@bot.message_handler(commands=[*COMMANDS])
def message_handler(message: Message):
    """
    Ловит команды от пользователей
    """
    chat_id, message_text = message.chat.id, message.text
    settings = UserSettings(chat_id)
    main_log(user_status=settings.user_status, chat_id=chat_id, text=message_text, action="send   ")
    command_handler(settings, chat_id, message_text, message)

@bot.callback_query_handler(func=lambda call: True)
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
    tag_len_less = len(text) < len(SQL(f'SELECT text FROM root WHERE event_id="{event_id}" AND user_id = {chat_id} AND date = "{msg_date}" AND isdel == 0;')[0][0])

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
"""), chat_id, message_id, reply_markup=generate_buttons([{"🔙": "back", "✅": 'Edit Edit'}]))
        except Error as e:
            print(e)
            return
    try:
        bot.delete_message(chat_id, edit_message_id)
    except ApiTelegramException:
        bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

@bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.text.startswith('⚙️') and m.from_user.id != BOT_ID)
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

if __name__ == "__main__":
    bot.infinity_polling()
