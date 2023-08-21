import re
from io import StringIO
from time import sleep
from sqlite3 import Error

from telebot.apihelper import ApiTelegramException
from telebot.types import (
    Message,
    InputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import config
import logging
from lang import get_translate
from bot import bot, set_bot_commands
from message_generator import NoEventMessage, CallBackAnswer
from time_utils import now_time_strftime, now_time, new_time_calendar
from bot_actions import (
    delete_message_action,
    press_back_action,
    update_message_action,
    re_date,
    before_del_message,
)
from buttons_utils import (
    create_monthly_calendar_keyboard,
    generate_buttons,
    delmarkup,
    edit_button_attrs,
    backmarkup,
    create_yearly_calendar_keyboard,
)
from bot_messages import (
    search_message,
    week_event_list_message,
    trash_can_message,
    daily_message,
    notifications_message,
    recurring_events_message,
    settings_message,
    start_message,
    help_message,
    monthly_calendar_message,
    account_message,
)
from utils import (
    fetch_weather,
    fetch_forecast,
    write_table_to_str,
    markdown,
    is_secure_chat,
    parse_message,
)
from todoapi.api import User
from todoapi.types import db, UserSettings
from todoapi.utils import (
    is_admin_id,
    is_premium_user,
    to_html_escaping,
    remove_html_escaping,
)

re_call_data_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}\Z")


def command_handler(user: User, message: Message) -> None:
    """
    Отвечает за реакцию бота на команды
    Метод message.text.startswith("")
    используется и для групп (в них сообщение приходит в формате /command{bot.username})
    """
    settings: UserSettings = user.settings
    chat_id, message_text = message.chat.id, message.text

    if message_text.startswith("/calendar"):
        generated = monthly_calendar_message(settings, chat_id)
        generated.send(chat_id)

    elif message_text.startswith("/start"):
        set_bot_commands(chat_id, settings.user_status, settings.lang)
        settings.update_userinfo(bot)

        generated = start_message(settings)
        generated.send(chat_id)

    elif message_text.startswith("/deleted"):
        if is_premium_user(user):
            generated = trash_can_message(settings, chat_id)
            generated.send(chat_id)
        else:
            set_bot_commands(chat_id, settings.user_status, settings.lang)
            generated = NoEventMessage(
                get_translate("deleted", settings.lang), delmarkup
            )
            generated.send(chat_id)

    elif message_text.startswith("/week_event_list"):
        generated = week_event_list_message(settings, chat_id)
        generated.send(chat_id)

    elif message_text.startswith("/weather") or message_text.startswith("/forecast"):
        # Проверяем есть ли аргументы
        if message_text not in (
            "/weather",
            f"/weather@{bot.username}",
            "/forecast",
            f"/forecast@{bot.username}",
        ):
            nowcity = message_text.split(maxsplit=1)[-1]
        else:
            nowcity = settings.city

        try:
            if message_text.startswith("/weather"):
                text = fetch_weather(settings, nowcity)
            else:  # forecast
                text = fetch_forecast(settings, nowcity)
        except KeyError:
            if message_text.startswith("/weather"):
                text = get_translate("weather_invalid_city_name", settings.lang)
            else:  # forecast
                text = get_translate("forecast_invalid_city_name", settings.lang)

        if isinstance(text, int):
            text = (
                "Погоду запрашивали слишком часто...\n" f"Подождите ещё {text} секунд"
            )

        generated = NoEventMessage(text, delmarkup)
        generated.send(chat_id)

    elif message_text.startswith("/search"):
        text = message_text.removeprefix("/search").strip()
        query = to_html_escaping(text).replace("\n", " ").replace("--", "")
        generated = search_message(settings, chat_id, query)
        generated.send(chat_id)

    elif message_text.startswith("/dice"):
        value = bot.send_dice(chat_id).json["dice"]["value"]
        sleep(4)
        NoEventMessage(value).send(chat_id)

    elif message_text.startswith("/help"):
        generated = help_message(settings)
        generated.send(chat_id)

    elif message_text.startswith("/settings"):
        generated = settings_message(settings)
        generated.send(chat_id)

    elif message_text.startswith("/today"):
        message_date = now_time_strftime(settings.timezone)
        generated = daily_message(settings, chat_id, message_date)
        new_message = generated.send(chat_id)

        # Изменяем уже существующую клавиатуру если событие в сообщение только одно.
        if len(generated.event_list) == 1:
            event = generated.event_list[0]
            edit_button_attrs(
                markup=generated.reply_markup,
                row=0,
                column=1,
                old="callback_data",
                new="switch_inline_query_current_chat",
                val=f"event({event.date}, {event.event_id}, {new_message.message_id}).text\n"
                f"{remove_html_escaping(event.text)}",
            )

            try:
                generated.edit(chat_id, new_message.message_id, only_markup=True)
            except ApiTelegramException:  # message is not modified
                pass

    elif message_text.startswith("/sqlite") and is_secure_chat(message):
        bot.send_chat_action(chat_id, "upload_document")

        try:
            with open(config.DATABASE_PATH, "rb") as file:
                bot.send_document(
                    chat_id,
                    file,
                    caption=now_time_strftime(settings.timezone),
                )
        except ApiTelegramException:
            NoEventMessage("Отправить файл не получилось").send(chat_id)

    elif message_text.startswith("/SQL ") and is_secure_chat(message):
        # Выполнение запроса от админа к базе данных и красивый вывод результатов
        query = message_text[5:].strip()

        if not query.lower().startswith("select"):
            print(query.lower())
            bot.send_chat_action(chat_id, "typing")
            try:
                db.execute(query, commit=message_text.endswith("\n--commit=True"))
            except Error as e:
                NoEventMessage(f'Error "{e}"').reply(message)
            else:
                NoEventMessage("ok").reply(message)
            return

        bot.send_chat_action(chat_id, "upload_document")

        file = StringIO()
        file.name = "table.txt"

        try:
            write_table_to_str(file, query=query)
        except Error as e:
            bot.reply_to(message, f'[handlers.py -> "/SQL"] Error "{e}"')
        else:
            bot.send_document(
                chat_id,
                InputFile(file),
                message.message_id,
                f"<code>/SQL {query}</code>",
            )
        finally:
            file.close()

    elif message_text.startswith("/bell"):
        notifications_message([chat_id], from_command=True)

    elif message_text.startswith("/save_to_csv"):
        response, error_text = user.export_data(
            f"ToDoList {message.from_user.username} "
            f"({now_time_strftime(settings.timezone)}).csv"
        )

        if response:
            bot.send_chat_action(chat_id, "upload_document")

            try:
                bot.send_document(chat_id, InputFile(response))
            except ApiTelegramException as e:
                logging.info(f'save_to_csv ApiTelegramException "{e}"')
                big_file_translate = get_translate("file_is_too_big", settings.lang)
                bot.send_message(chat_id=chat_id, text=big_file_translate)
        else:
            export_error = get_translate("export_csv", settings.lang)
            generated = NoEventMessage(export_error.format(t=error_text.split(" ")[1]))
            generated.send(chat_id)

    elif message_text.startswith("/version"):
        NoEventMessage(f"Version {config.__version__}").send(chat_id)

    elif message_text.startswith("/setuserstatus") and is_secure_chat(message):
        message_text = message_text.removeprefix("/setuserstatus ")
        res = re.compile(r"\A(\d+) (-1|0|1|2)\Z").findall(message_text)
        if res:
            user_id, user_status = [int(x) for x in res[0]]

            response, error_text = user.set_user_status(user_id, user_status)

            match error_text:
                case "":
                    text = f"Успешно изменено\n{user_id} -> {user_status}"
                case "User Not Exist":
                    text = "Пользователь не найден."
                case "Invalid status":
                    text = "Неверный status\nstatus должен быть в (-1, 0, 1, 2)"
                case "Not Enough Authority":
                    text = "Недостаточно прав."
                case "Cannot be reduced in admin rights":
                    text = "Нельзя понизить администратора."
                case _:
                    text = f'Ошибка базы данных: "{error_text}"'

            if not set_bot_commands(user_id, user_status, UserSettings(user_id).lang):
                text = "Ошибка при обновлении команд."
        else:
            text = """
SyntaxError
/setuserstatus {id} {status}

| -1 | ban
|  0 | default
|  1 | premium
|  2 | admin
"""

        NoEventMessage(text).reply(message)

    elif message_text.startswith("/idinfo ") and is_secure_chat(message):
        if len(message_text.split(" ")) == 2:
            user_id = int(message_text.removeprefix("/idinfo "))
            _settings = UserSettings(user_id)
            chat = bot.get_chat(user_id)
            text = f"""
type: <code>{chat.type}</code>
title: <code>{chat.title}</code>
username: <code>{chat.username}</code>
first_name: <code>{chat.first_name}</code>
last_name: <code>{chat.last_name}</code>
id: <code>{chat.id}</code>

lang: {_settings.lang}
timezone: {_settings.timezone}
city: {_settings.city}
notifications: {_settings.notifications}
notifications_time: {_settings.notifications_time}
direction: {_settings.direction}
sub_urls: {_settings.sub_urls}

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
        NoEventMessage(text).reply(message)

    elif message_text.startswith("/idinfo") and is_secure_chat(message):
        try:
            message.text = "/SQL SELECT * FROM settings;"
            command_handler(user, message)
        except ApiTelegramException:
            pass

    elif message_text.startswith("/id"):
        NoEventMessage(f"Your id <code>{chat_id}</code>").reply(message)

    elif message_text.startswith("/deleteuser") and is_admin_id(chat_id):
        message_text = message_text.removeprefix("/deleteuser ")
        res = re.compile(r"(\d+)").findall(message_text)
        response = None

        if res:
            user_id = int(res[0])
            response, error_text = user.delete_user(user_id)

            match error_text:
                case "":
                    text = "Пользователь успешно удалён"
                case "User Not Exist":
                    text = "Пользователь не найден."
                case "Not Enough Authority":
                    text = "Недостаточно прав."
                case "Unable To Remove Administrator":
                    text = (
                        "Нельзя удалить администратора.\n"
                        "<code>/setuserstatus {user_id} 0</code>"
                    )
                case "Error":
                    text = "Не получилось получить csv файл."
                case _:
                    text = "Ошибка при удалении."
        else:
            text = "SyntaxError\n/deleteuser {id}"

        try:
            if response:
                bot.send_document(
                    chat_id,
                    InputFile(response),
                    message.message_id,
                    text,
                )
            else:
                NoEventMessage(text).reply(message)
        except ApiTelegramException:
            pass

    elif message_text.startswith("/account"):
        account_message(settings, chat_id, message_text)

    elif message_text.startswith("/commands"):  # TODO перевод
        # /account - Ваш аккаунт (просмотр лимитов)
        text = """
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
""" + (
            """
/version - Версия бота
/bell - Сообщение с уведомлением
/sqlite - Бекап базы данных
/files - Сохранить все файлы
/SQL {...} - Выполнить sql запрос к базе данных
/idinfo {id}/None - Получить файл с id всех пользователей или информацию о id
/setuserstatus {id} {status} - Поставить пользователю id команды для статуса status
/deleteuser {id} - Удалить пользователя
"""
            if is_admin_id(chat_id)
            else ""
        )
        NoEventMessage(text).send(chat_id)


def callback_handler(
    user: User,
    settings: UserSettings,
    chat_id: int,
    message_id: int,
    message_text: str,
    call_data: str,
    call_id: int | None,
    message: Message | None,
):
    """
    Отвечает за реакцию бота на нажатия на кнопку
    "event_add" - Добавить событие. Бот входит в режим ожидания получения события.
    "/calendar" - Изменить сообщение на календарь дней
    "back" -
    "message_del" - Пытается удалить сообщение. При ошибке шлёт сообщение с просьбой выдать права.
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
    "status delete" - Удаляет статус для события
    "before del" - Подтверждение удаления события.
    "del" - Удаление события.
    "|" - Меняет страничку.
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
        if user.check_limit(date, event_count=1, symbol_count=1):
            text = get_translate("exceeded_limit", settings.lang)
            CallBackAnswer(text).answer(call_id, True)
            return

        db.execute(
            """
UPDATE settings
   SET add_event_date = ?
 WHERE user_id = ?;
""",
            params=(f"{date},{message_id}", chat_id),
            commit=True,
        )

        text = get_translate("send_event_text", settings.lang)
        CallBackAnswer(text).answer(call_id)

        text = f"{message.html_text}\n\n<b>?.?.</b>⬜\n{text}"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=backmarkup)

    elif call_data == "/calendar":
        generated = monthly_calendar_message(settings, chat_id)
        generated.edit(chat_id, message_id)

    elif call_data == "calendar":
        YY_MM = [int(x) for x in message_text[:10].split(".")[1:]][::-1]
        text = get_translate("choose_date", settings.lang)
        markup = create_monthly_calendar_keyboard(
            chat_id, settings.timezone, settings.lang, YY_MM
        )
        NoEventMessage(text, markup).edit(chat_id, message_id)

    elif call_data.startswith("back"):
        press_back_action(settings, call_data, chat_id, message_id, message_text)

    elif call_data == "message_del":
        delete_message_action(settings, message)

    elif call_data == "confirm change":
        first_line, _, raw_text = message_text.split("\n", maxsplit=2)
        text = to_html_escaping(raw_text)  # Получаем изменённый текст
        event_id = first_line.split(" ", maxsplit=2)[1]

        response, error_text = user.edit_event(event_id, text)
        if not response:
            logging.info(f'user.edit_event "{error_text}"')
            error = get_translate("error", settings.lang)
            CallBackAnswer(error).answer(call_id, True)
            return

        update_message_action(settings, chat_id, message_id, message_text)

    elif call_data.startswith("select event "):
        # TODO переписать с использованием функции parse_message
        # action: Literal["edit", "status", "delete", "delete bin", "recover bin", "open"]
        action = call_data[13:]

        events_list = parse_message(message_text)
        msg_date = message_text[:10]

        # Заглушка если событий нет
        if len(events_list) == 0:
            no_events = get_translate("no_events_to_interact", settings.lang)
            CallBackAnswer(no_events).answer(call_id, True)
            return

        # Если событие одно, то оно сразу выбирается
        if len(events_list) == 1:
            event = events_list[0]
            if not user.check_event(event.event_id, action.endswith("bin")):
                update_message_action(settings, chat_id, message_id, message_text)
                return

            if action in ("status", "delete", "delete bin", "recover bin", "open"):
                match action:
                    case "status":
                        new_call_data = f"status_home_page {event.event_id} {event.date}"
                    case "delete":
                        new_call_data = f"before del {event.date} {event.event_id} _"
                    case "delete bin":
                        new_call_data = f"del {event.date} {event.event_id} bin delete"
                    case  "recover bin":
                        new_call_data = f"recover {event.date} {event.event_id}"
                    case _:  # "select event open"
                        new_call_data = f"{event.date}"

                callback_handler(
                    user=user,
                    settings=settings,
                    chat_id=chat_id,
                    message_id=message_id,
                    message_text=message_text,
                    call_data=new_call_data,
                    call_id=call_id,
                    message=message,
                )
                return

        markup = InlineKeyboardMarkup()
        for event in events_list:
            # Проверяем существование события
            response = user.get_event(event.event_id, action.endswith("bin"))[0]
            if response:
                event.text = response.text
            else:
                continue

            button_title = (f"{event.date}.{event.event_id}.{event.status} "
                            f"{event.text}{config.callbackTab * 20}")[:60]
            button_title2 = (f"{event.event_id}.{event.status} "
                             f"{event.text}{config.callbackTab * 20}")[:60]

            if action == "edit":
                callback_data = (
                    f"event({event.date}, {event.event_id}, {message.message_id}).text\n"
                    f"{remove_html_escaping(event.text)}"
                )
                button = InlineKeyboardButton(button_title2, switch_inline_query_current_chat=callback_data)

            elif action in ("status", "delete"):  # Действия в обычном дне
                if action == "status":
                    callback_data = f"status_home_page {event.event_id} {event.date}"
                else:  # "delete"
                    callback_data = f"before del {event.date} {event.event_id} _"

                button = InlineKeyboardButton(button_title2, callback_data=callback_data)

            elif action in ("delete bin", "recover bin"):  # Действия в корзине
                if action == "delete bin":
                    callback_data = f"del {event.date} {event.event_id} bin delete"
                else:  # "recover bin"
                    callback_data = f"recover {event.date} {event.event_id}"

                button = InlineKeyboardButton(button_title, callback_data=callback_data)

            elif action == "open":
                callback_data = f"{event.date}"
                button = InlineKeyboardButton(button_title, callback_data=callback_data)

            else:
                continue

            markup.row(button)

        if not markup.to_dict()["inline_keyboard"]:  # Созданный markup пустой
            update_message_action(settings, chat_id, message_id, message_text)
            return

        markup.row(
            InlineKeyboardButton(
                "🔙", callback_data="back" if not action.endswith("bin") else "back bin"
            )
        )

        if action == "edit":
            select_event = get_translate("select_event_to_edit", settings.lang)
            text = f"{msg_date}\n{select_event}"

        elif action == "status":
            select_event = get_translate("select_event_to_change_status", settings.lang)
            text = f"{msg_date}\n{select_event}"

        elif action == "delete":
            select_event = get_translate("select_event_to_delete", settings.lang)
            text = f"{msg_date}\n{select_event}"

        elif action == "delete bin":
            basket = get_translate("basket", settings.lang)
            select_event = get_translate("select_event_to_delete", settings.lang)
            text = f"{basket}\n{select_event}"

        elif action == "recover bin":
            basket = get_translate("basket", settings.lang)
            select_event = get_translate("select_event_to_recover", settings.lang)
            text = f"{basket}\n{select_event}"

        elif message_text.startswith("🔍 "):
            first_line = message_text.split("\n", maxsplit=1)[0]
            raw_query = first_line.split(maxsplit=2)[-1][:-1]
            query = to_html_escaping(raw_query)
            translate_search = get_translate("search", settings.lang)
            choose_event = get_translate("choose_event", settings.lang)
            text = f"🔍 {translate_search} {query}:\n{choose_event}"

        else:
            choose_event = get_translate("choose_event", settings.lang)
            text = f"{msg_date}\n{choose_event}"

        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("recover"):
        event_date, event_id = call_data.split(maxsplit=2)[1:]
        event_id = int(event_id)
        response, error_text = user.recover_event(event_id)
        if not response:
            logging.info(f'user.recover_event "{error_text}"')
            error = get_translate("error", settings.lang)
            CallBackAnswer(error).answer(call_id, True)
            return  # такого события нет

        callback_handler(
            user=user,
            settings=settings,
            chat_id=chat_id,
            message_id=message_id,
            message_text=message_text,
            call_data="back bin",
            call_id=call_id,
            message=message,
        )

    elif any([call_data.startswith(s) for s in ("status_home_page", "status page ")]):
        # Парсим данные
        if call_data.startswith("status_home_page"):
            event_id, event_date = call_data.split(" ")[1:]
        else:  # status page
            args = message_text.split("\n", maxsplit=3)
            event_date, event_id = args[0], args[2].split(".", maxsplit=4)[3]

        # Проверяем наличие события
        event = user.get_event(event_id)[0]

        if event is False:  # Если этого события нет
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

        text, status = event.text, event.status

        if call_data.startswith("status_home_page"):
            sl = status.split(",")
            sl.extend([""] * (5 - len(sl)))
            markup = generate_buttons(
                [
                    *[
                        {f"{title}{config.callbackTab * 20}": f"{data}"}
                        for title, data in get_translate(
                            "status_home_page", settings.lang
                        ).items()
                    ],
                    {
                        f"{i}"
                        if i
                        else " " * n: f"status delete {i} {event_id} {event_date}"
                        if i
                        else "None"
                        for n, i in enumerate(sl)
                    }
                    if status != "⬜️"
                    else {},
                    {"🔙": "back"},
                ]
            )
        else:  # status page
            buttons_data = get_translate(call_data, settings.lang)
            markup = generate_buttons(
                [
                    *[
                        {
                            f"{row}{config.callbackTab * 20}": (
                                f"status set "
                                f"{row.split(maxsplit=1)[0]} "
                                f"{event_id} "
                                f"{event_date}"
                            )
                            for row in status_column
                        }
                        if len(status_column) > 1
                        else {
                            f"{status_column[0]}{config.callbackTab * 20}": (
                                f"status set "
                                f"{status_column[0].split(maxsplit=1)[0]} "
                                f"{event_id} "
                                f"{event_date}"
                            )
                        }
                        for status_column in buttons_data
                    ],
                    {"🔙": f"status_home_page {event_id} {event_date}"},
                ]
            )

        bot.edit_message_text(
            f"{event_date}\n"
            f"<b>{get_translate('select_status_to_event', settings.lang)}\n"
            f"{event_date}.{event_id}.{status}</b>\n"
            f"{markdown(text, status, settings.sub_urls)}",
            chat_id,
            message_id,
            reply_markup=markup,
        )

    elif call_data.startswith("status set"):
        new_status, event_id, event_date = call_data.split()[2:]
        event_id = int(event_id)

        # Если события нет, то обновляем сообщение
        response, error_text = user.get_event(event_id)

        if not response:
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

        old_status = response.status

        if new_status == "⬜️" == old_status:
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

        if old_status == "⬜️":
            res_status = new_status

        elif new_status == "⬜️":
            res_status = "⬜️"

        else:
            res_status = f"{old_status},{new_status}"

        response, error_text = user.set_status(event_id, res_status)

        match error_text:
            case "":
                text = ""
            case "Status Conflict":
                text = get_translate("conflict_statuses", settings.lang)
            case "Status Length Exceeded":
                text = get_translate("more_5_statuses", settings.lang)
            case "Status Repeats":
                text = get_translate("status_already_posted", settings.lang)
            case _:
                text = get_translate("error", settings.lang)

        if text:
            CallBackAnswer(text).answer(call_id, True)

        if new_status == "⬜️":
            press_back_action(settings, call_data, chat_id, message_id, message_text)
        else:
            callback_handler(
                user=user,
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data=f"status_home_page {event_id} {event_date}",
                call_id=call_id,
                message=message,
            )

    elif call_data.startswith("status delete"):
        status, event_id, event_date = call_data.split()[2:]
        event_id = int(event_id)

        # Если события нет, то обновляем сообщение
        response, error_text = user.get_event(event_id)

        if not response:
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

        text, old_status = response.text, response.status

        if status == "⬜️" or old_status == "⬜️":
            return

        res_status = (
            old_status.replace(f",{status}", "")
            .replace(f"{status},", "")
            .replace(f"{status}", "")
        )

        if not res_status:
            res_status = "⬜️"

        user.set_status(event_id, res_status)

        callback_handler(
            user=user,
            settings=settings,
            chat_id=chat_id,
            message_id=message_id,
            message_text=message_text,
            call_data=f"status_home_page {event_id} {event_date}",
            call_id=call_id,
            message=message,
        )

    elif call_data.startswith("before del "):
        event_date, event_id, back_to_bin = call_data.split()[2:]
        event_id = int(event_id)

        before_del_message(
            user,
            call_id,
            call_data,
            chat_id,
            message_id,
            message_text,
            event_id,
            back_to_bin == "bin",
        )

    elif call_data.startswith("del "):
        event_date, event_id, where, mode = call_data.split(maxsplit=4)[1:]
        event_id = int(event_id)

        to_bin = mode == "to_bin" and (
            settings.user_status in (1, 2) or is_admin_id(chat_id)
        )

        response = user.delete_event(event_id, to_bin)[0]

        if not response:
            error = get_translate("error", settings.lang)
            CallBackAnswer(error).answer(call_id)

        press_back_action(
            settings,
            "back" if where != "bin" else "back bin",
            chat_id,
            message_id,
            message_text,
        )

    elif call_data.startswith("|"):  # Список id событий на странице
        page, id_list = call_data.split("|")[1:]
        id_list = id_list.split(",")

        try:
            if message_text.startswith("🔍 "):  # Поиск
                first_line = message_text.split("\n", maxsplit=1)[0]
                raw_query = first_line.split(maxsplit=2)[-1][:-1]
                query = to_html_escaping(raw_query)
                generated = search_message(settings, chat_id, query, id_list, int(page))
                generated.edit(chat_id, message_id, markup=message.reply_markup)

            elif message_text.startswith("📆"):  # Если /week_event_list
                generated = week_event_list_message(
                    settings, chat_id, id_list, int(page)
                )
                generated.edit(chat_id, message_id, markup=message.reply_markup)

            elif message_text.startswith("🗑"):  # Корзина
                generated = trash_can_message(settings, chat_id, id_list, int(page))
                generated.edit(chat_id, message_id, markup=message.reply_markup)

            elif re_date.match(message_text):
                msg_date = re_date.match(message_text)[0]
                if page.startswith("!"):
                    generated = recurring_events_message(
                        settings, msg_date, chat_id, id_list, int(page[1:])
                    )
                else:
                    generated = daily_message(
                        settings, chat_id, msg_date, id_list, int(page), message_id
                    )

                # Изменяем кнопку изменения текста события на актуальную
                markup = message.reply_markup

                if len(generated.event_list) == 1:
                    event = generated.event_list[0]
                    edit_button_attrs(
                        markup=markup,
                        row=0,
                        column=1,
                        old="callback_data",
                        new="switch_inline_query_current_chat",
                        val=f"event({event.date}, {event.event_id}, {message_id}).text\n"
                        f"{remove_html_escaping(event.text)}",
                    )
                else:
                    edit_button_attrs(
                        markup=markup,
                        row=0,
                        column=1,
                        old="switch_inline_query_current_chat",
                        new="callback_data",
                        val="select event edit",
                    )

                generated.edit(chat_id, message_id, markup=markup)

            elif message_text.startswith("🔔"):  # Будильник
                notifications_message(
                    [chat_id], id_list, int(page), message_id, message.reply_markup
                )

        except ApiTelegramException:
            text = get_translate("already_on_this_page", settings.lang)
            CallBackAnswer(text).answer(call_id)

    elif call_data.startswith("generate calendar months "):
        sleep(0.5)
        year = call_data.split()[-1]

        if year == "now":
            YY = now_time(settings.timezone).year
        else:
            YY = int(year)

        if 1980 <= YY <= 3000:
            markup = create_yearly_calendar_keyboard(
                settings.timezone, settings.lang, chat_id, YY
            )
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
            except ApiTelegramException:  # Сообщение не изменено
                callback_handler(
                    user=user,
                    settings=settings,
                    chat_id=chat_id,
                    message_id=message_id,
                    message_text=message_text,
                    call_data="/calendar",
                    call_id=call_id,
                    message=message,
                )
        else:
            CallBackAnswer("🤔").answer(call_id)

    elif call_data.startswith("generate calendar days "):
        sleep(0.5)
        if call_data.split()[-1] == "now":
            YY_MM = new_time_calendar(settings.timezone)
        else:
            YY_MM = [int(i) for i in call_data.split()[-2:]]

        if 1980 <= YY_MM[0] <= 3000:
            markup = create_monthly_calendar_keyboard(
                chat_id, settings.timezone, settings.lang, YY_MM
            )
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
            except (
                ApiTelegramException
            ):  # Если нажата кнопка ⟳, но сообщение не изменено
                date = now_time_strftime(settings.timezone)
                generated = daily_message(
                    settings, chat_id, date, message_id=message_id
                )
                generated.edit(chat_id, message_id)
        else:
            CallBackAnswer("🤔").answer(call_id)

    elif call_data.startswith("settings"):
        par_name, par_val = call_data.split(" ", maxsplit=2)[1:]

        if par_name not in [
            "user_id",
            "userinfo",
            "registration_date",
            "lang",
            "sub_urls",
            "city",
            "timezone",
            "direction",
            "user_status",
            "notifications",
            "notifications_time",
            "user_max_event_id",
            "add_event_date",
        ]:
            return

        user.set_settings(**{par_name: par_val})

        settings = UserSettings(chat_id)
        set_bot_commands(chat_id, settings.user_status, settings.lang)
        generated = settings_message(settings)
        try:
            generated.edit(chat_id, message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("recurring"):
        generated = recurring_events_message(settings, message_text[:10], chat_id)
        generated.edit(chat_id, message_id)

    elif re_call_data_date.search(call_data):
        year = int(call_data[-4:])
        sleep(0.3)
        if 1980 < year < 3000:
            generated = daily_message(
                settings,
                chat_id,
                call_data,
                message_id=message_id,
            )
            generated.edit(chat_id, message_id)
        else:
            CallBackAnswer("🤔").answer(call_id)

    elif call_data == "update":
        update_message_action(settings, chat_id, message_id, message_text, call_id)

    elif call_data.startswith("help"):
        try:
            generated = help_message(settings, call_data)
            markup = None if call_data.startswith("help page") else message.reply_markup
            generated.edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("already_on_this_page", settings.lang)
            CallBackAnswer(text).answer(call_id)

    elif call_data == "clean_bin":
        res = user.clear_basket()[0]
        if not res:
            error = get_translate("error", settings.lang)
            CallBackAnswer(error).answer(call_id)
            return

        update_message_action(settings, chat_id, message_id, message_text)

    elif call_data == "restore_to_default":
        user.set_settings("ru", 1, "Москва", 3, "DESC", 0, 0, "08:00")

        if user.settings.lang != settings.lang:
            set_bot_commands(chat_id, settings.user_status, settings.lang)

        generated = settings_message(settings)
        try:
            generated.edit(chat_id, message_id)
        except ApiTelegramException:
            pass

        sleep(1)
        CallBackAnswer("✅").answer(call_id)


def clear_state(chat_id: int | str):
    """
    Очищает состояние приёма сообщения у пользователя
    и изменяет сообщение по id из add_event_date
    """
    add_event_date = db.execute(
        """
SELECT add_event_date
  FROM settings
 WHERE user_id = ?;
""",
        params=(chat_id,),
    )[0][0]

    if add_event_date:
        msg_date, message_id = add_event_date.split(",")
        db.execute(
            """
UPDATE settings
   SET add_event_date = 0
 WHERE user_id = ?;
""",
            params=(chat_id,),
            commit=True,
        )
        update_message_action(UserSettings(chat_id), chat_id, message_id, msg_date)
