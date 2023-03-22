from io import StringIO
from time import sleep

from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery, Message, InputFile
from telebot import TeleBot
import csv

from func import * # InlineKeyboardMarkup, InlineKeyboardButton, re, config импортируются из func


"""Для цветных логов (Выполнять только для Windows)"""
if Windows := 0:
    from ctypes import windll
    (lambda k: k.SetConsoleMode(k.GetStdHandle(-11), 7))(windll.kernel32)

bot = TeleBot(config.bot_token)
Me = bot.get_me()
BOT_ID = Me.id
BOT_USERNAME = Me.username
COMMAND_LIST = (
    'calendar', 'start', 'deleted', 'version', 'forecast',
    'week_event_list', 'weather', 'search', 'bell',
    'dice', 'help', 'settings', 'today', 'sqlite', 'file', 'SQL', 'save_to_csv'
)
print(f"+{'-'*59}+")
[print(f"| {k: >27} = {v!s: <27} |") for k, v in Me.to_dict().items()]
print(f"+{'-'*59}+")
print('Запустился')

def create_message(settings: UserSettings, chat_id, date: str, message_id: int = False, result_text=''):
    WHERE = f"""user_id = {chat_id} AND isdel = 0 AND date = '{date}'"""
    SELECT = """event_id, text, status"""
    start_id, end_id, newmarkup = get_diapason(WHERE=WHERE, reply_markup=allmarkup, MAXLEN=2500)
    sql_res = get_text_in_diapason(settings, start_id, end_id, SELECT=SELECT, WHERE=WHERE)
    if start_id and end_id:
        for n, (event_id, text, status) in enumerate(sql_res):
            text = markdown(text, status, settings.sub_urls)
            result_text += f'<b>{n + 1}.{event_id}.{status}</b>\n{text}\n\n'
    else:
        result_text = get_translate("nodata", settings.lang)
    text = f"{date} {day_info(settings, date)}\n\n{result_text}"[:4090]
    if message_id:
        bot.edit_message_text(text, chat_id, message_id,
                              reply_markup=newmarkup, parse_mode='html', disable_web_page_preview=True)
    else:
        bot.send_message(chat_id, text, reply_markup=newmarkup, parse_mode='html', disable_web_page_preview=True)

def command_handler(settings: UserSettings, chat_id: int, message_id: int, message_text: str, message: Message):
    """
    Отвечает за реакцию бота на команды
    метод message.text.startswith("") используется для групп (в них сообщение приходит в формате /command{BOT_USERNAME})
    """
    if message.text.startswith('/calendar'):
        bot.send_message(chat_id, 'Выберите дату',
                         reply_markup=mycalendar(settings, new_time_calendar(settings), chat_id))

    if message.text.startswith('/start'):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("/calendar", callback_data="/calendar"))
        markup.row(InlineKeyboardButton(get_translate("add_bot_to_group", settings.lang), url=f'https://t.me/{BOT_USERNAME}?startgroup=AddGroup'))
        markup.row(InlineKeyboardButton(get_translate("game_bot", settings.lang), url='https://t.me/EgorGameBot'))
        text = get_translate("start", settings.lang)
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='html')

    if message.text.startswith('/deleted'):
        if list(limits.keys())[int(settings.user_status)] in ("premium", "admin"):
            text, newmarkup = deleted(settings, chat_id)
            bot.send_message(chat_id, text, reply_markup=newmarkup, parse_mode='html', disable_web_page_preview=True)
        else:
            bot.send_message(chat_id, get_translate("deleted", settings.lang), reply_markup=delmarkup)

    if message.text.startswith('/week_event_list'):
        text, newmarkup = week_event_list(settings, chat_id)
        bot.send_message(chat_id, text, reply_markup=newmarkup, parse_mode='HTML', disable_web_page_preview=True)

    if message.text.startswith('/weather'):
        if message.text not in ('/weather', f'/weather@{BOT_USERNAME}'):  # Проверяем есть ли аргументы
            nowcity = message.text.split(maxsplit=1)[-1]
        else:
            nowcity = UserSettings(chat_id).city
        try:
            weather = weather_in(settings, nowcity)
            bot.send_message(chat_id, weather, parse_mode='html', reply_markup=delmarkup)
        except KeyError:
            bot.send_message(chat_id, get_translate("weather_invalid_city_name", settings.lang))

    if message.text.startswith('/forecast'):
        if message.text not in ('/forecast', f'/forecast@{BOT_USERNAME}'):  # Проверяем есть ли аргументы
            nowcity = message.text.split(maxsplit=1)[-1]
        else:
            nowcity = UserSettings(chat_id).city
        try:
            weather = forecast_in(settings, nowcity)
            bot.send_message(chat_id, weather, parse_mode='html', reply_markup=delmarkup)
        except KeyError:
            bot.send_message(chat_id, get_translate("forecast_invalid_city_name", settings.lang))

    if message.text.startswith('/search'):
        query = ToHTML(message.text[len("/search "):]).replace("--", '').replace("\n", ' ')
        text, markup = search(settings, chat_id, query)
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='html', disable_web_page_preview=True)

    if message.text.startswith('/dice'):
        value = bot.send_dice(chat_id).json['dice']['value']
        sleep(4)
        bot.send_message(message.chat.id, value)

    if message.text.startswith('/help'):
        text = get_translate("help", settings.lang)
        bot.send_message(message.chat.id, text, parse_mode='markdown', reply_markup=delmarkup)

    if message.text.startswith('/settings'):
        settings_lang, sub_urls, city, timezone_, direction, markup = settings.get_settings_markup()
        text = get_translate("settings", settings.lang)
        bot.send_message(message.chat.id, text.format(settings_lang, bool(sub_urls), city, timezone_, direction), parse_mode='html', reply_markup=markup, disable_web_page_preview=True)

    if message.text.startswith('/today'):
        create_message(settings, chat_id,
                       now_time_strftime(settings))

    if message.text.startswith('/sqlite') and is_admin_id(chat_id):
        try:
            DATE = now_time_strftime(settings)
            markup = generate_buttons([{'Применить базу данных': 'set database'}])
            with open(config.database_path, 'rb') as file:
                bot.send_document(chat_id, file, caption=f'{DATE}', reply_markup=markup)
        except ApiTelegramException:
            bot.send_message(chat_id, 'Отправить файл не получилось')

    if message.text.startswith('/file') and is_admin_id(chat_id):
        DATE = now_time_strftime(settings)
        try:
            with open(__file__, 'rb') as file:
                bot.send_document(chat_id, file, caption=f'{DATE}\nФайл_бота.py')
        except ApiTelegramException:
            bot.send_message(chat_id, 'Отправить файл не получилось')

    if message.text.startswith('/SQL ') and is_admin_id(chat_id): pass

    if message.text.startswith('/bell') and is_admin_id(chat_id):
        text = check_bells(settings, chat_id)
        bot.send_message(chat_id, text, parse_mode='html', reply_markup=delmarkup, disable_web_page_preview=True)

    if message.text.startswith('/save_to_csv'):
        try:
            response, t = CSVCooldown.check(chat_id)
            if response:
                res = SQL(f"""SELECT event_id, date, status, text FROM root
                                  WHERE user_id="{chat_id}" AND isdel=0;""")
                file = StringIO()
                date = now_time_strftime(settings)
                file.name = f'ToDoList {message.from_user.username} ({date}).csv'
                file_writer = csv.writer(file)
                file_writer.writerows([['event_id', 'date', 'status', 'text']])
                [file_writer.writerows([[str(event_id), date, str(status), NoHTML(text)]]) for event_id, date, status, text in res]
                file.seek(0)
                bot.send_document(chat_id, InputFile(file))
            else:
                bot.send_message(chat_id, get_translate("export_csv", settings.lang).format(t=t//60), parse_mode='html')
        except ApiTelegramException as e:
            print(f'/save_to_csv "{e}"')
            bot.send_message(chat_id, get_translate("file_is_too_big", settings.lang))

    if message.text.startswith('/version'):
        bot.reply_to(message,
                     f'Version {config.__version__}')


def callback_handler(settings: UserSettings, chat_id: int, message_id: int, message_text: str, call_data: str, call_id: int, message: Message):

    if call_data == "event_add":
        bot.clear_step_handler_by_chat_id(chat_id)
        message_date = message_text.split(maxsplit=1)[0]
        if is_exceeded_limit(chat_id, message_date, list(limits.values())[int(settings.user_status)], (1, 1)):
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("exceeded_limit", settings.lang), show_alert=True)
            return 0
        bot.edit_message_text(f'{message_text}\n\n0.0.⬜️\n{get_translate("send_event_text", settings.lang)}', chat_id, message_id,
                              reply_markup=backmarkup, disable_web_page_preview=True)

        def add_event(message2):
            if message2.text.lower().split("@")[0] not in COMMAND_LIST:
                if create_event(message2.chat.id, message_date, ToHTML(message2.text[:4050])):
                    create_message(settings, chat_id, message_date, message_id)
                    try:
                        bot.delete_message(message2.chat.id, message2.message_id)
                    except ApiTelegramException:
                        bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)
                else: pass

        bot.register_next_step_handler(message, add_event)

    if call_data == '/calendar':
        bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id, reply_markup=mycalendar(
            settings, new_time_calendar(settings), chat_id), disable_web_page_preview=True)

    if call_data == 'back':
        bot.clear_step_handler_by_chat_id(chat_id)
        DATE = message_text.split(maxsplit=1)[0]
        if len(DATE.split('.')) == 3:
            try: create_message(settings, chat_id, DATE, message_id)
            except ApiTelegramException:
                bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id,
                                      reply_markup=mycalendar(settings, [int(x) for x in DATE.split('.')[1:]][::-1], chat_id),
                                      disable_web_page_preview=True)
            else: return 0

    if call_data == "message_del":
        bot.clear_step_handler_by_chat_id(chat_id)
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException:
            bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

    if call_data == "set database":
        DATE = now_time_strftime(settings)
        markup = generate_buttons([{'Применить базу данных': 'set database'}])
        try:
            with open(config.database_path, 'rb') as file:
                bot.send_document(chat_id, file, caption=f'{DATE}\nНа данный момент база выглядит так.', reply_markup=markup)
        except ApiTelegramException:
            bot.send_message(chat_id, 'Отправить файл не получилось')

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(f"{message.document.file_name}", "wb") as new_file:
            new_file.write(downloaded_file)
        bot.reply_to(message, 'Файл записан')
        return 0

    if call_data == 'Edit Edit':
        text = ToHTML(message_text.split('\n', maxsplit=2)[-1])
        date, *_, event_id = message_text.split("\n", maxsplit=1)[0].split(" ")
        try:
            SQL(f"UPDATE root SET text = '{text}' WHERE event_id = {event_id} AND date = '{date}';", commit=True)
        except Error as e:
            print(e)
        else:
            create_message(settings, chat_id, date, message_id)

    if call_data in ('event_edit', 'event_status', 'event_del'):
        bot.clear_step_handler_by_chat_id(chat_id)
        res = message_text.split('\n\n')[1:]
        if res[0].startswith("👀"):
            return 0
        markup = InlineKeyboardMarkup()
        date = message_text.split(maxsplit=1)[0]
        for i in res:
            event_id = i.split('.', maxsplit=2)[1]
            if call_data == 'event_edit':
                try:
                    event_text = NoHTML(SQL(f"""SELECT text FROM root WHERE event_id={event_id} AND user_id = {chat_id};""")[0][0])
                except Error as e:
                    return print(f'Произошла ошибка в "Изменить сообщение": "{e}"')
                markup.row(InlineKeyboardButton(f"{i}{callbackTab * 20}", switch_inline_query_current_chat=f"Edit message({event_id}, {date}, {message.id})\n{event_text}"))
            if call_data == "event_status":
                markup.row(InlineKeyboardButton(f"{i}{callbackTab * 20}", callback_data=f"edit_page_status {event_id} {date}"))
            if call_data == 'event_del':
                Btitle = i.replace('\n', ' ')[:41]
                markup.row(InlineKeyboardButton(f"{Btitle}{callbackTab * 20}", callback_data=f"PRE DEL {date} {event_id}"))
        markup.row(InlineKeyboardButton("🔙", callback_data="back"))
        if call_data == 'event_edit': text = f'{date}\n{get_translate("select_event_to_edit", settings.lang)}'
        elif call_data == "event_status": text = f'{date}\n{get_translate("select_event_to_change_status", settings.lang)}'
        elif call_data == 'event_del': text = f'{date}\n{get_translate("select_event_to_delete", settings.lang)}'
        else: text = f'{date}\n{get_translate("choose_event", settings.lang)}'
        bot.edit_message_text(text, chat_id, message_id, parse_mode='html', reply_markup=markup, disable_web_page_preview=True)

    if call_data.startswith('edit_page_status'):
        _, event_id, date = call_data.split(' ')
        markup = InlineKeyboardMarkup()
        status_list = get_translate("status_list", settings.lang)
        [markup.row(InlineKeyboardButton(f"{status1}{callbackTab * 20}", callback_data=f"set_status {status1.split(maxsplit=1)[0]} {event_id} {date}"),
                    InlineKeyboardButton(f"{status2}{callbackTab * 20}", callback_data=f"set_status {status2.split(maxsplit=1)[0]} {event_id} {date}"))
         for status1, status2 in status_list]
        markup.row(InlineKeyboardButton("🔙", callback_data="back"))
        text, status = SQL(f'SELECT text, status FROM root WHERE event_id="{event_id}" AND user_id = {chat_id} AND date = "{date}" AND isdel == 0;')[0]
        bot.edit_message_text(f'{message_text.split(maxsplit=1)[0]}\n<b>{get_translate("select_status_to_event", settings.lang)}\n'
                              f'{event_id}.</b>{status}\n{markdown(text, status, settings.sub_urls)}',
                              chat_id, message_id, reply_markup=markup, parse_mode='html', disable_web_page_preview=True)
        return

    if call_data.startswith('set_status'):
        'set_status 🗺 247 03.02.2023'
        _, status, event_id, event_date = call_data.split()

        SQL(f"UPDATE root SET status = '{status}' WHERE event_id = {event_id} AND date = '{event_date}';", commit=True)
        msg_date = message_text.split()[0]
        try:
            create_message(settings, chat_id, msg_date, message_id)
        except ApiTelegramException:
            bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id,
                                  reply_markup=mycalendar(settings, [int(x) for x in msg_date.split('.')[1:]][::-1], chat_id),
                                  disable_web_page_preview=True)
        return

    if call_data.startswith('PRE DEL '):
        date, event_id = call_data.split(maxsplit=4)[2:]
        try:
            text, status = SQL(f"""SELECT text, status FROM root WHERE isdel = 0
                                   AND user_id = {chat_id} AND date = '{date}'
                                   AND event_id = {event_id};""")[0]
        except Error as e:
            print(f'Ошибка SQL в PRE DEL : "{e}"')
            callback_handler(settings, chat_id, message_id, message_text, "back", call_id, message)
            return
        predelmarkup = generate_buttons([{"🔙": "back", "🗑": f"{call_data[4:]}"}])
        end_text = get_translate("/deleted", settings.lang) if list(limits.keys())[int(settings.user_status)] in ("premium", "admin") else ""
        bot.edit_message_text(f'<b>{date} {event_id}.</b>{status} <u>{day_info(settings, date)}</u>\n'
                              f'<b>{get_translate("are_you_sure", settings.lang)}:</b>\n'
                              f'{text}\n\n'
                              f'{end_text}', chat_id, message_id,
                              reply_markup=predelmarkup, disable_web_page_preview=True, parse_mode='html')
        return

    if call_data.startswith('DEL '):
        # call_data="DEL 00.00.0000 000 text"
        date, event_id = call_data.split(maxsplit=3)[1:]
        try:
            if list(limits.keys())[int(settings.user_status)] in ("premium", "admin"):
                SQL(f"""UPDATE root SET isdel = 1 WHERE user_id = {chat_id} AND date = '{date}' AND event_id = {event_id};""", commit=True)
            else:
                SQL(f"""DELETE FROM root          WHERE user_id = {chat_id} AND date = '{date}' AND event_id = {event_id};""", commit=True)
        except Error as e:
            print(e)
            bot.edit_message_text(f'{date}\n{get_translate("error", settings.lang)}', chat_id, message_id,
                                  reply_markup=backmarkup, disable_web_page_preview=True)
            return
        try:
            create_message(settings, chat_id, date, message_id)
        except ApiTelegramException:
            bot.edit_message_text(get_translate("choose_date", settings.lang), chat_id, message_id,
                                  reply_markup=mycalendar(settings, date, chat_id), disable_web_page_preview=True)
        return

    if call_data.startswith('get_page('):
        start_id, end_id = [int(x) for x in re.findall(r'get_page\((\d+), (\d+)\)', call_data)[0]]
        if message_text.startswith('🔍 '): # Поиск
            query = message_text.split('\n', maxsplit=1)[0].split(maxsplit=2)[-1][:-1]
            text = search(settings, chat_id, query, start_id, end_id)[0]

        elif message_text.startswith('📆'): # Если /week_event_list
            text = week_event_list(settings, chat_id, start_id, end_id)[0]

        elif message_text.startswith('🗑'): # Корзина
            text = deleted(settings, chat_id, start_id, end_id)[0]

        elif (res := re.match(r'\A(\d{1,2}\.\d{1,2}\.\d{4})', message_text)) is not None:
            date, result_text = res[0], ''
            WHERE = f"""user_id = {chat_id} AND isdel = 0 AND date = '{date}'"""
            SELECT = """event_id, text, status"""
            sql_res = get_text_in_diapason(settings, start_id, end_id, SELECT=SELECT, WHERE=WHERE)
            for n, (EVENTID, TEXT, STATUS) in enumerate(sql_res):
                TEXT = markdown(TEXT, STATUS, settings.sub_urls)
                result_text += f'<b>{n + 1}.{EVENTID}.{STATUS}</b>\n{TEXT}\n\n'
            text = f"{date} {day_info(settings, date)}\n\n{result_text}"[:4090]
        else:
            text = message_text
        try:
            bot.edit_message_text(text, chat_id, message_id,
                                  reply_markup=message.reply_markup, parse_mode='html', disable_web_page_preview=True)
        except ApiTelegramException as e:
            print(f'get_page( ошибка "{e}"')
            bot.answer_callback_query(callback_query_id=call_id, text=get_translate("already_on_this_page", settings.lang))
        return 0

    if call_data.startswith('generate_month_calendar '):
        sleep(0.5)  # Задержка
        YY = int(call_data.split(' ')[-1])
        if 1980 <= YY <= 3000:
            markup = generate_month_calendar(settings, chat_id, YY)
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")
        return 0

    if call_data.startswith('generate_calendar '):
        sleep(0.5)  # Задержка
        DATE = [int(i) for i in call_data.split()[1:]]
        markup = mycalendar(settings, DATE, chat_id)
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        return 0

    elif call_data == 'year now':
        try:
            markup = generate_month_calendar(settings, chat_id, now_time(settings).year)
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        except ApiTelegramException:
            callback_handler(settings, chat_id, message_id, message_text, '/calendar', call_id, message)
        return 0

    elif call_data.startswith('settings'):
        par_name, par_val = call_data.split(' ', maxsplit=2)[1:]
        if isinstance(par_val, str):
            SQL(f"""UPDATE settings SET {par_name}='{par_val}' WHERE user_id = {chat_id};""", commit=True)
        else:
            SQL(f"""UPDATE settings SET {par_name}={par_val} WHERE user_id = {chat_id};""", commit=True)
        settings = UserSettings(chat_id)
        settings_lang, sub_urls, city, timezone_, direction,  markup = settings.get_settings_markup()
        text = get_translate("settings", settings.lang)
        try:
            bot.edit_message_text(text.format(settings_lang, bool(sub_urls), city, timezone_, direction), chat_id, message_id,
                                  parse_mode='html', reply_markup=markup, disable_web_page_preview=True)
        except ApiTelegramException:
            pass
        return 0

    elif call_data in ('<<<', '<<', '<', '⟳', '>', '>>', '>>>') or re.search(r"\A\d{2}\.\d{2}\.\d{4}\Z", call_data):
        if call_data in ('<<<', '>>>'):
            bot.clear_step_handler_by_chat_id(chat_id)
            msgdate = [int(i) for i in message_text.split(maxsplit=1)[0].split('.')]
            new_date = datetime(*msgdate[::-1])
            sleep(0.5) # Задержка
            if 1980 < new_date.year < 3000:
                if call_data == '<<<': new_date -= timedelta(days=1)
                if call_data == '>>>': new_date += timedelta(days=1)
                DATE = '.'.join(f'{new_date}'.split(maxsplit=1)[0].split('-')[::-1])
                create_message(settings, chat_id, DATE, message_id)
            else:
                bot.answer_callback_query(callback_query_id=call_id, text="🤔")
        elif call_data in ('<<', '<', '⟳', '>', '>>'):
            mydatatime = [int(i) for i in message.json["reply_markup"]['inline_keyboard'][0][0]["text"].split()[-3][1:-1].split('.')[::-1]]
            # получаем [2023, 4] [year, month]
            if call_data == '<': mydatatime = [mydatatime[0] - 1, 12] if mydatatime[1] == 1  else [mydatatime[0], mydatatime[1] - 1]
            if call_data == '>': mydatatime = [mydatatime[0] + 1, 1]  if mydatatime[1] == 12 else [mydatatime[0], mydatatime[1] + 1]
            if call_data == '<<': mydatatime[0] -= 1
            if call_data == '>>': mydatatime[0] += 1
            if call_data == '⟳': mydatatime = new_time_calendar(settings)
            sleep(0.5)  # Задержка
            if 1980 <= mydatatime[0] <= 3000:
                try:
                    bot.edit_message_reply_markup(chat_id, message_id, reply_markup=mycalendar(settings, mydatatime, chat_id))
                except ApiTelegramException: # Если нажата кнопка ⟳, но сообщение не изменено
                    DATE = now_time_strftime(settings)
                    create_message(settings, chat_id, DATE, message_id)
            else:
                bot.answer_callback_query(callback_query_id=call_id, text="🤔")
        else:
            if len(call_data.split('.')) == 3:
                DATE = call_data
                create_message(settings, chat_id, DATE, message_id)


@bot.message_handler(commands=[*COMMAND_LIST])
def get_calendar(message: Message):
    chat_id, message_id, message_text = message.chat.id, message.id, message.text
    settings = UserSettings(chat_id)

    # print(f'{chat_id=} {message_id=}')
    log_chat_id = f"\033[21m{chat_id}\033[0m" if settings.user_status == 0 else (f"\033[21m\033[32m{chat_id}\033[0m" if settings.user_status == 1 else f"\033[21m\033[34m{chat_id}\033[0m")
    print(f'{log_time_strftime()} {log_chat_id.ljust(15)} send    {message_text.replace(f"{chr(92)}n", f"{chr(92)}{chr(92)}n")}') # {chr(92)} = \ (escape sequences)

    command_handler(settings, chat_id, message_id, message_text, message)

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call: CallbackQuery):
    # =ot.answer_callback_query(callback_query_id=call.id, text="Предупреждение", show_alert=True)
    chat_id, message_id, call_data, message_text = call.message.chat.id, call.message.id, call.data, call.message.text
    #print(f'{call.data=} {chat_id=} {message_id=}')
    settings = UserSettings(chat_id)
    log_chat_id = f"\033[21m{chat_id}\033[0m" if settings.user_status == 0 else (f"\033[21m\033[32m{chat_id}\033[0m" if settings.user_status == 1 else f"\033[21m\033[34m{chat_id}\033[0m")
    print(f'{log_time_strftime()} {log_chat_id.ljust(15)} pressed {call_data.replace(f"{chr(92)}n", f"{chr(92)}{chr(92)}n")}')  # {chr(92)} = \ (escape sequences)

    if call.data == 'None': return 0

    callback_handler(settings, chat_id, message_id, call.message.text, call.data, call.id, call.message)

@bot.message_handler(func=lambda m: m.text.startswith('#'))
def get_search_message(message: Message):
    query = ToHTML(message.text[1:]).replace("--", '').replace("\n", ' ')
    chat_id = message.chat.id
    settings = UserSettings(message.chat.id)
    log_chat_id = f"\033[21m{chat_id}\033[0m" if settings.user_status == 0 else (f"\033[21m\033[32m{chat_id}\033[0m" if settings.user_status == 1 else f"\033[21m\033[34m{chat_id}\033[0m")
    print(f'{log_time_strftime()} {log_chat_id.ljust(15)} search  {message.text.replace(f"{chr(92)}n", f"{chr(92)}{chr(92)}n")}')  # {chr(92)} = \ (escape sequences)
    text, markup = search(settings, chat_id, query)
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='html', disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.text.startswith(f'@{BOT_USERNAME} Edit message(') and re.search(r"message\((\d+), (\d{1,2}\.\d{1,2}\.\d{4}), (\d+)\)", m.text))
def get_edit_message(message: Message):
    chat_id = message.chat.id
    edit_message_id = message.id
    settings = UserSettings(chat_id)
    res = re.search(r"message\((\d+), (\d{1,2}\.\d{1,2}\.\d{4}), (\d+)\)", message.text)[0]
    event_id = int(re.findall(r"\((\d+)", res)[0])
    date = re.findall(r" (\d{1,2}\.\d{1,2}\.\d{4}),", res)[0]
    message_id = int(re.findall(r", (\d+)\)", res)[0])
    text = message.text.split('\n', maxsplit=1)[-1]
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(f"{event_id} {text[:20]}{callbackTab * 20}",
                                    switch_inline_query_current_chat=f"{message.text.split(maxsplit=1)[-1]}"))
    markup.row(InlineKeyboardButton("✖", callback_data="message_del"))
    tag_len_max = len(text) > 2000
    tag_limit_exceeded = is_exceeded_limit(chat_id, date, list(limits.values())[int(settings.user_status)], (len(text), 0))
    tag_len_less = len(text) < len(SQL(f'SELECT text FROM root WHERE event_id="{event_id}" AND user_id = {chat_id} AND date = "{date}" AND isdel == 0;')[0][0])

    if tag_len_max:
        bot.reply_to(message, get_translate("message_is_too_long", settings.lang), reply_markup=markup)
    elif tag_limit_exceeded and not tag_len_less:
        bot.reply_to(message, get_translate("exceeded_limit", settings.lang), reply_markup=markup)
    else:
        try:
            bot.edit_message_text((f"""
{date} {day_info(settings, date)} {event_id}
<b>{get_translate("are_you_sure_edit", settings.lang)}</b>
<i>{ToHTML(text)}</i>
"""), chat_id, message_id, reply_markup=generate_buttons([{"🔙": "back", "✅": 'Edit Edit'}]), parse_mode='html', disable_web_page_preview=True)
        except Error as e:
            print(e)
            return
    try:
        bot.delete_message(chat_id, edit_message_id)
    except ApiTelegramException:
        bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)


@bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.text.startswith('⚙️') and m.from_user.id != BOT_ID)
def get_search_message(message: Message):
    chat_id, message_id = message.chat.id, message.id
    settings = UserSettings(chat_id)
    callback_handler(settings, chat_id, message.reply_to_message.id, message.text, f'settings city {message.text[:25]}', 0, message.reply_to_message)
    try:
        bot.delete_message(chat_id, message_id)
    except ApiTelegramException:
        bot.reply_to(message, get_translate("get_admin_rules", settings.lang), reply_markup=delmarkup)

bot.infinity_polling()
