import re
import csv
from io import StringIO
from time import sleep
from sqlite3 import Error

from telebot.apihelper import ApiTelegramException
from telebot.types import (
    Message,
    InputMediaDocument,
    InputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import config
import logging
from db.db import SQL
from lang import get_translate
from bot import bot, set_bot_commands
from bot_actions import delete_message_action, press_back_action, update_message_action, re_date
from limits import is_exceeded_limit
from messages.message_generator import NoEventMessage
from user_settings import UserSettings
from time_utils import (
    now_time_strftime,
    now_time,
    DayInfo,
    new_time_calendar,
)
from buttons_utils import (
    create_monthly_calendar_keyboard,
    generate_buttons,
    delmarkup,
    edit_button_attrs,
    databasemarkup,
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
    is_admin_id,
    fetch_weather,
    fetch_forecast,
    to_html_escaping,
    remove_html_escaping,
    write_table_to_str,
    markdown,
    Cooldown,
)

CSVCooldown = Cooldown(30 * 60, {})
re_call_data_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}\Z")


def command_handler(
    settings: UserSettings, chat_id: int, message_text: str, message: Message
) -> None:
    """
    Отвечает за реакцию бота на команды
    Метод message.text.startswith("")
    используется и для групп (в них сообщение приходит в формате /command{bot.username})
    """
    if message_text.startswith("/calendar"):
        generated = monthly_calendar_message(settings, chat_id)
        generated.send(chat_id)

    elif message_text.startswith("/start"):
        set_bot_commands(chat_id, settings.user_status, settings.lang)
        settings.update_userinfo(bot)

        generated = start_message(settings)
        generated.send(chat_id)

    elif message_text.startswith("/deleted"):
        if settings.user_status in (1, 2) or is_admin_id(chat_id):
            generated = trash_can_message(settings=settings, chat_id=chat_id)
            generated.send(chat_id=chat_id)
        else:
            set_bot_commands(chat_id, settings.user_status, settings.lang)
            generated = NoEventMessage(
                get_translate("deleted", settings.lang),
                delmarkup
            )
            generated.send(chat_id)

    elif message_text.startswith("/week_event_list"):
        generated = week_event_list_message(settings=settings, chat_id=chat_id)
        generated.send(chat_id=chat_id)

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
                weather = fetch_weather(settings=settings, city=nowcity)
            else:  # forecast
                weather = fetch_forecast(settings=settings, city=nowcity)

            bot.send_message(chat_id=chat_id, text=weather, reply_markup=delmarkup)
        except KeyError:
            if message_text.startswith("/weather"):
                bot.send_message(
                    chat_id=chat_id,
                    text=get_translate("weather_invalid_city_name", settings.lang),
                )
            else:  # forecast
                bot.send_message(
                    chat_id=chat_id,
                    text=get_translate("forecast_invalid_city_name", settings.lang),
                )

    elif message_text.startswith("/search"):
        text = message_text.removeprefix("/search").strip()
        query = to_html_escaping(text).replace("\n", " ").replace("--", "")
        generated = search_message(settings=settings, chat_id=chat_id, query=query)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/dice"):
        value = bot.send_dice(chat_id=chat_id).json["dice"]["value"]
        sleep(4)
        bot.send_message(chat_id=chat_id, text=value)

    elif message_text.startswith("/help"):
        generated = help_message(settings)
        generated.send(chat_id)

    elif message_text.startswith("/settings"):
        generated = settings_message(settings)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/today"):
        message_date = now_time_strftime(settings.timezone)
        generated = daily_message(settings=settings, chat_id=chat_id, date=message_date)
        new_message = generated.send(chat_id=chat_id)

        # Изменяем уже существующую клавиатуру если событие в сообщение только одно.
        if len(generated.event_list) == 1:
            event = generated.event_list[0]
            edit_button_attrs(
                markup=generated.reply_markup,
                row=0,
                column=1,
                old="callback_data",
                new="switch_inline_query_current_chat",
                val=f"event({event.date}, {event.event_id}, {new_message.message_id}).edit\n"
                f"{remove_html_escaping(event.text)}",
            )

            try:
                generated.edit(chat_id, new_message.message_id, only_markup=True)
            except ApiTelegramException:  # message is not modified
                pass

    elif (
        message_text.startswith("/sqlite")
        and is_admin_id(chat_id)
        and message.chat.type == "private"
    ):
        bot.send_chat_action(chat_id=chat_id, action="upload_document")

        try:
            with open(config.DATABASE_PATH, "rb") as file:
                bot.send_document(
                    chat_id=chat_id,
                    document=file,
                    caption=f"{now_time_strftime(settings.timezone)}",
                    reply_markup=databasemarkup,
                )
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text="Отправить файл не получилось")

    elif (
        message_text.startswith("/files")
        and is_admin_id(chat_id)
        and message.chat.type == "private"
    ):
        bot.send_chat_action(chat_id=chat_id, action="upload_document")
        tag_log = True if message_text.endswith(" +log") else False

        class _:
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        try:
            with (
                open(config.LOG_FILE, "rb") if tag_log else _() as log_file,
                open("config.py", "rb") as config_file,
                open("lang.py", "rb") as lang_file,
                open("func.py", "rb") as func_file,
                open("main.py", "rb") as main_file,
                open(config.DATABASE_PATH, "rb") as db_file,
            ):
                bot.send_media_group(
                    chat_id=chat_id,
                    media=[
                        InputMediaDocument(log_file, caption="Файл лога")
                        if tag_log
                        else None,
                        InputMediaDocument(config_file, caption="Файл настроек"),
                        InputMediaDocument(lang_file, caption="Языковой файл"),
                        InputMediaDocument(func_file, caption="Файл с функциями"),
                        InputMediaDocument(main_file, caption="Основной файл"),
                        InputMediaDocument(
                            db_file,
                            caption=f"База данных\n\nВерсия от {config.__version__}",
                        ),
                    ],
                )
        except ApiTelegramException:
            bot.send_message(chat_id=chat_id, text="Отправить файл не получилось")

    elif (
        message_text.startswith("/SQL ")
        and is_admin_id(chat_id)
        and message.chat.type == "private"
    ):
        bot.send_chat_action(chat_id=chat_id, action="upload_document")
        # Выполнение запроса от админа к базе данных и красивый вывод результатов
        query = message_text[5:].strip()
        file = StringIO()
        file.name = "table.txt"

        try:
            write_table_to_str(
                file,
                query=query,
                commit=message_text.endswith("\n--commit=True"),
            )
        except Error as e:
            bot.reply_to(message, text=f'[handlers.py -> "/SQL"] Error "{e}"')
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
        notifications_message(user_id_list=[chat_id], from_command=True)

    elif message_text.startswith("/save_to_csv"):
        response, t = CSVCooldown.check(key=chat_id, update_dict=False)

        if response:
            bot.send_chat_action(chat_id=chat_id, action="upload_document")
            file = StringIO()
            file.name = f"ToDoList {message.from_user.username} ({now_time_strftime(settings.timezone)}).csv"
            table = SQL(
                """
SELECT event_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 WHERE user_id = ? AND 
       removal_time = 0;
""",
                params=(chat_id,),
                column_names=True,
            )
            file_writer = csv.writer(file)
            [
                file_writer.writerows(
                    [
                        [
                            str(event_id),
                            event_date,
                            remove_html_escaping(event_text),
                            event_status,
                            event_removal_time,
                            event_adding_time,
                            event_recent_changes_time,
                        ]
                    ]
                )
                for (
                    event_id,
                    event_date,
                    event_text,
                    event_status,
                    event_removal_time,
                    event_adding_time,
                    event_recent_changes_time,
                ) in table
            ]

            file.seek(0)
            try:
                bot.send_document(chat_id=chat_id, document=InputFile(file))
            except ApiTelegramException as e:
                logging.info(
                    f'[handlers.py -> command_handler -> "/save_to_csv"] ApiTelegramException "{e}"'
                )
                bot.send_message(
                    chat_id=chat_id,
                    text=get_translate("file_is_too_big", settings.lang),
                )
        else:
            bot.send_message(
                chat_id=chat_id,
                text=get_translate("export_csv", settings.lang).format(t=t // 60),
            )

    elif message_text.startswith("/version"):
        bot.send_message(chat_id=chat_id, text=f"Version {config.__version__}")

    elif (
        message_text.startswith("/setuserstatus")
        and is_admin_id(chat_id)
        and message.chat.type == "private"
    ):
        if len(message_text.split(" ")) == 3:
            user_id, user_status = [int(i) for i in message_text.split(" ")[1:]]

            try:
                if user_status not in (-1, 0, 1, 2):
                    raise ValueError

                SQL(
                    """
UPDATE settings
   SET user_status = ?
 WHERE user_id = ?;
""",
                    params=(user_status, user_id),
                    commit=True,
                )

                if not set_bot_commands(
                    user_id, user_status, UserSettings(user_id).lang
                ):
                    raise KeyError
            except IndexError:  # Если user_id не существует
                text = "Ошибка: id не существует"
            except Error as e:  # Ошибка sqlite3
                text = f'Ошибка базы данных: "{e}"'
            except ApiTelegramException as e:
                text = f'Ошибка telegram api: "{e}"'
            except KeyError:
                text = "Ошибка user_status"
            except ValueError:
                text = "Неверный status\nstatus должен быть в (-1, 0, 1, 2)"
            else:
                text = f"Успешно изменено\n{user_id} -> {user_status}"
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

    elif (
        message_text.startswith("/idinfo ")
        and is_admin_id(chat_id)
        and message.chat.type == "private"
    ):
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
        bot.reply_to(message=message, text=text)

    elif (
        message_text.startswith("/idinfo")
        and is_admin_id(chat_id)
        and message.chat.type == "private"
    ):
        try:
            command_handler(
                settings=settings,
                chat_id=chat_id,
                message_text="/SQL SELECT user_id as chat_id FROM settings;",
                message=message,
            )
        except ApiTelegramException:
            pass

    elif message_text.startswith("/id"):
        NoEventMessage(f"Your id <code>{chat_id}</code>").reply(message)

    elif message_text.startswith("/deleteuser") and is_admin_id(chat_id):
        if len(message_text.split(" ")) == 2:
            user_id = int(message_text.removeprefix("/deleteuser "))
            if not is_admin_id(user_id):
                try:
                    # TODO присылать sql файл для восстановления
                    SQL(
                        """
DELETE FROM events
      WHERE user_id = ?;
""",
                        params=(user_id,),
                        commit=True,
                    )
                    SQL(
                        """
DELETE FROM settings
      WHERE user_id = ?;
""",
                        params=(user_id,),
                        commit=True,
                    )
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
        account_message(settings, chat_id, message_text)

    elif message_text.startswith("/commands"):  # TODO перевод
        # /account - Ваш аккаунт (просмотр лимитов)
        bot.send_message(
            chat_id,
            """
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
"""
            + (
                ""
                if not is_admin_id(chat_id)
                else """
/version - Версия бота
/bell - Сообщение с уведомлением
/sqlite - Бекап базы данных
/files - Сохранить все файлы
/SQL {...} - Выполнить sql запрос к базе данных
/idinfo {id}/None - Получить файл с id всех пользователей или информацию о id
/setuserstatus {id} {status} - Поставить пользователю id команды для статуса status
/deleteuser {id} - Удалить пользователя
"""
            ),
        )


def callback_handler(
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
        if is_exceeded_limit(settings, date, event_count=1, symbol_count=1):
            text = get_translate("exceeded_limit", settings.lang)
            bot.answer_callback_query(call_id, text, True)
            return

        SQL(
            """
UPDATE settings
   SET add_event_date = ?
 WHERE user_id = ?;
""",
            params=(f"{date},{message_id}", chat_id),
            commit=True,
        )

        text = get_translate("send_event_text", settings.lang)
        bot.answer_callback_query(call_id, text)

        text = f"{message.html_text}\n\n<b>?.?.</b>⬜\n{text}"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=backmarkup)

    elif call_data == "/calendar":
        generated = monthly_calendar_message(settings, chat_id)
        generated.edit(chat_id, message_id)

    elif call_data.startswith("back"):
        press_back_action(settings, call_data, chat_id, message_id, message_text)

    elif call_data == "message_del":
        delete_message_action(settings, chat_id, message_id, message)

    elif call_data == "set database" and is_admin_id(chat_id):
        try:
            with open(config.DATABASE_PATH, "rb") as file:
                text = (
                    f"{now_time_strftime(settings.timezone)}\n"
                    f"На данный момент база выглядит так."
                )
                bot.send_document(
                    chat_id=chat_id,
                    document=file,
                    caption=text,
                    reply_markup=databasemarkup,
                )
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
        first_line, _, raw_text = message_text.split("\n", maxsplit=3)
        text = to_html_escaping(raw_text)  # Получаем изменённый текст
        msg_date, event_id = first_line.split(" ", maxsplit=2)[:2]

        try:
            SQL(
                """
UPDATE events
   SET text = ?,
       recent_changes_time = DATETIME() 
 WHERE user_id = ? AND 
       event_id = ? AND 
       date = ?;
""",
                params=(text, chat_id, event_id, msg_date),
                commit=True,
            )
        except Error as e:
            logging.info(
                f'[handlers.py -> callback_handler -> "confirm change"] Error "{e}"'
            )
            error = get_translate("error", settings.lang)
            bot.answer_callback_query(call_id, error)
            return

        update_message_action(settings, chat_id, message_id, message_text)

    elif call_data.startswith("select event "):
        # action: Literal["edit", "status", "delete", "delete bin", "recover bin", "open"]
        action = call_data[13:]

        events_list = message_text.split("\n\n")[1:]

        # Заглушка если событий нет
        if events_list[0].startswith("👀") or events_list[0].startswith("🕸"):
            no_events = get_translate("no_events_to_interact", settings.lang)
            bot.answer_callback_query(call_id, no_events, True)
            return

        msg_date = message_text[:10]

        # Если событие одно, то оно сразу выбирается
        if len(events_list) == 1:
            event_id = events_list[0].split(".", maxsplit=2)[1]

            if action.endswith("bin"):
                event_id = events_list[0].split(".", maxsplit=4)[-2]
            try:
                SQL(
                    f"""
SELECT text
  FROM events
 WHERE event_id = ? AND 
       user_id = ?
       {"AND removal_time != 0" if action.endswith("bin") else ""};
""",
                    params=(event_id, chat_id),
                )[0][0]
            except IndexError:  # Если этого события не существует
                update_message_action(settings, chat_id, message_id, message_text)
                return

            if action in ("status", "delete", "delete bin", "recover bin", "open"):
                event_date = events_list[0][:10]
                if action == "status":
                    new_call_data = f"status_home_page {event_id} {msg_date}"
                elif action == "delete":
                    new_call_data = f"before del {msg_date} {event_id} _"
                elif action == "delete bin":
                    new_call_data = f"del {event_date} {event_id} bin delete"
                elif action == "recover bin":
                    new_call_data = f"recover {event_date} {event_id}"
                else:
                    new_call_data = f"{event_date}"  # "select event open"

                callback_handler(
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
            # Парсим данные
            if action.endswith("bin") or message_text.startswith("🔍 "):
                event_id = event.split(".", maxsplit=4)[-2]
            else:
                event_id = event.split(".", maxsplit=2)[-2]

            # Проверяем существование события
            try:
                event_text = SQL(
                    f"""
SELECT text
  FROM events
 WHERE event_id = ? AND 
       user_id = ? AND
       removal_time {"!" if action.endswith("bin") else ""}= 0;
""",
                    params=(event_id, chat_id),
                )[0][0]
            except IndexError:
                continue

            if action == "edit":
                markup.row(
                    InlineKeyboardButton(
                        text=f"{event}{config.callbackTab * 20}",
                        switch_inline_query_current_chat=f"event({msg_date}, {event_id}, {message.message_id}).edit\n"
                        f"{remove_html_escaping(event_text)}",
                    )
                )

            elif action in ("status", "delete"):  # Действия в обычном дне
                button_title = event.replace("\n", " ")[:50]
                if action == "status":
                    callback_data = f"status_home_page {event_id} {msg_date}"
                else:  # "delete"
                    callback_data = f"before del {msg_date} {event_id} _"

                markup.row(
                    InlineKeyboardButton(
                        text=f"{button_title}{config.callbackTab * 20}",
                        callback_data=callback_data,
                    )
                )

            elif action in ("delete bin", "recover bin"):  # Действия в корзине
                event_date = event[:10]
                button_title = (
                    event.split(" ", maxsplit=1)[0]
                    + " "
                    + event.split("\n", maxsplit=1)[-1][:50]
                )
                if action == "delete bin":
                    callback_data = f"del {event_date} {event_id} bin delete"
                else:  # "recover bin"
                    callback_data = f"recover {event_date} {event_id}"

                markup.row(
                    InlineKeyboardButton(
                        f"{button_title}{config.callbackTab * 20}",
                        callback_data=callback_data,
                    )
                )

            elif action == "open":
                event_text = event.split("\n", maxsplit=1)[-1]
                text = f"{event.split(' ', maxsplit=1)[0]} {event_text}{config.callbackTab * 20}"
                button = InlineKeyboardButton(text=text, callback_data=f"{event[:10]}")
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

        try:
            event_len = SQL(
                """
SELECT LENGTH(text) 
  FROM events
 WHERE user_id = ? AND 
       event_id = ? AND 
       date = ? AND 
       removal_time != 0;
""",
                params=(chat_id, event_id, event_date),
            )[0][0]
        except IndexError:
            error = get_translate("error", settings.lang)
            bot.answer_callback_query(call_id, error, True)
            return  # такого события нет

        if is_exceeded_limit(
            settings, event_date, event_count=1, symbol_count=event_len
        ):
            exceeded_limit = get_translate("exceeded_limit", settings.lang)
            bot.answer_callback_query(call_id, exceeded_limit, True)
            return

        SQL(
            """
UPDATE events
   SET removal_time = 0
 WHERE user_id = ? AND 
       event_id = ? AND 
       date = ?;
""",
            params=(chat_id, event_id, event_date),
            commit=True,
        )
        callback_handler(
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
        try:  # Если события нет, то обновляем сообщение
            text, status = SQL(
                """
SELECT text,
       status
  FROM events
 WHERE user_id = ? AND 
       event_id = ? AND 
       removal_time = 0 AND 
       date = ?;
""",
                params=(chat_id, event_id, event_date),
            )[0]
        except IndexError:  # Если этого события уже нет
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

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

        try:  # Если события нет, то обновляем сообщение
            text, old_status = SQL(
                """
SELECT text,
       status
  FROM events
 WHERE user_id = ? AND 
       event_id = ? AND 
       removal_time = 0 AND 
       date = ?;
""",
                params=(chat_id, event_id, event_date),
            )[0]
        except IndexError:
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

        if new_status == "⬜️" == old_status:
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

        elif new_status in old_status:
            text = get_translate("status_already_posted", settings.lang)
            bot.answer_callback_query(call_id, text, True)

        elif len(old_status.split(",")) > 4 and new_status != "⬜️":
            text = get_translate("more_5_statuses", settings.lang)
            bot.answer_callback_query(call_id, text, True)

        # Убираем конфликтующие статусы
        elif ("🔗" in old_status or "💻" in old_status) and new_status in ("🔗", "💻"):
            text = get_translate("conflict_statuses", settings.lang) + " 🔗, 💻"
            bot.answer_callback_query(call_id, text, True)

        elif ("🪞" in old_status or "💻" in old_status) and new_status in ("🪞", "💻"):
            text = get_translate("conflict_statuses", settings.lang) + " 🪞, 💻"
            bot.answer_callback_query(call_id, text, True)

        elif ("🔗" in old_status or "⛓" in old_status) and new_status in ("🔗", "⛓"):
            text = get_translate("conflict_statuses", settings.lang) + " 🔗, ⛓"
            bot.answer_callback_query(call_id, text, True)

        elif ("🧮" in old_status or "🗒" in old_status) and new_status in ("🧮", "🗒"):
            text = get_translate("conflict_statuses", settings.lang) + " 🧮, 🗒"
            bot.answer_callback_query(call_id, text, True)

        else:
            if old_status == "⬜️":
                res_status = new_status

            elif new_status == "⬜️":
                res_status = "⬜️"

            else:
                res_status = f"{old_status},{new_status}"

            SQL(
                """
UPDATE events
   SET status = ?
 WHERE user_id = ? AND 
       event_id = ? AND 
       date = ?;
""",
                params=(res_status, chat_id, event_id, event_date),
                commit=True,
            )

        if new_status == "⬜️":
            press_back_action(settings, call_data, chat_id, message_id, message_text)
        else:
            callback_handler(
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

        try:  # Если события нет, то обновляем сообщение
            text, old_status = SQL(
                """
SELECT text,
       status
  FROM events
 WHERE user_id = ? AND 
       event_id = ? AND 
       removal_time = 0 AND 
       date = ?;
""",
                params=(chat_id, event_id, event_date),
            )[0]
        except IndexError:
            press_back_action(settings, call_data, chat_id, message_id, message_text)
            return

        if status == "⬜️":
            return

        res_status = (
            old_status.replace(f",{status}", "")
            .replace(f"{status},", "")
            .replace(f"{status}", "")
        )

        if not res_status:
            res_status = "⬜️"

        SQL(
            """
UPDATE events
   SET status = ?
 WHERE user_id = ? AND 
       event_id = ? AND 
       date = ?;
""",
            params=(res_status, chat_id, event_id, event_date),
            commit=True,
        )

        callback_handler(
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

        try:
            text, status = SQL(
                f"""
SELECT text,
       status
  FROM events
 WHERE user_id = ? AND 
       event_id = ? AND 
       date = ? AND 
       removal_time {"!" if back_to_bin == "bin" else ""}= 0;
""",
                params=(chat_id, event_id, event_date),
            )[0]
        except IndexError:
            # Проверяем на случай отсутствия call_id
            try:
                error = get_translate("error", settings.lang)
                bot.answer_callback_query(call_id, error)
                press_back_action(settings, call_data, chat_id, message_id, message_text)
            except ApiTelegramException:
                pass

            return 1

        delete_permanently = get_translate("delete_permanently", settings.lang)
        trash_bin = get_translate("trash_bin", settings.lang)
        split_data = call_data.split(maxsplit=1)[-1]

        is_wastebasket_available = (
            settings.user_status in (1, 2) and back_to_bin != "bin"
        ) or is_admin_id(chat_id)

        predelmarkup = generate_buttons(
            [
                {
                    "🔙": "back" if back_to_bin != "bin" else "back bin",
                    f"❌ {delete_permanently}": f"{split_data} delete",
                    **(
                        {f"🗑 {trash_bin}": f"{split_data} to_bin"}
                        if is_wastebasket_available
                        else {}
                    ),
                },
            ]
        )

        day = DayInfo(settings, event_date)
        sure_text = get_translate("are_you_sure", settings.lang)
        end_text = (
            get_translate("/deleted", settings.lang)
            if (settings.user_status in (1, 2) or is_admin_id(chat_id))
            else ""
        )
        text = (
            f"<b>{event_date}.{event_id}.</b>{status} <u><i>{day.str_date}  {day.week_date}</i> {day.relatively_date}</u>\n"
            f"<b>{sure_text}:</b>\n{text[:3800]}\n\n{end_text}"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=predelmarkup)

    elif call_data.startswith("del "):
        event_date, event_id, where, mode = call_data.split(maxsplit=4)[1:]

        try:
            if (
                settings.user_status in (1, 2) or is_admin_id(chat_id)
            ) and mode == "to_bin":
                SQL(
                    """
UPDATE events
   SET removal_time = DATE() 
 WHERE user_id = ? AND 
       date = ? AND 
       event_id = ?;
""",
                    params=(chat_id, event_date, event_id),
                    commit=True,
                )
            else:
                SQL(
                    """
DELETE FROM events
      WHERE user_id = ? AND 
            date = ? AND 
            event_id = ?;
""",
                    params=(chat_id, event_date, event_id),
                    commit=True,
                )
        except Error as e:
            logging.info(f'[handlers.py -> callback_handler -> "del"] Error "{e}"')
            error = get_translate("error", settings.lang)
            bot.answer_callback_query(call_id, error)

        press_back_action(settings, "back" if where != "bin" else "back bin", chat_id, message_id, message_text)

    elif call_data.startswith("|"):  # Список id событий на странице
        page, id_list = call_data.split("|")[1:]
        id_list = id_list.split(",")

        try:
            if message_text.startswith("🔍 "):  # Поиск
                first_line = message_text.split("\n", maxsplit=1)[0]
                raw_query = first_line.split(maxsplit=2)[-1][:-1]
                query = to_html_escaping(raw_query)
                generated = search_message(
                    settings=settings,
                    chat_id=chat_id,
                    query=query,
                    id_list=id_list,
                    page=page,
                )
                generated.edit(
                    chat_id=chat_id, message_id=message_id, markup=message.reply_markup
                )

            elif message_text.startswith("📆"):  # Если /week_event_list
                generated = week_event_list_message(
                    settings=settings, chat_id=chat_id, id_list=id_list, page=page
                )
                generated.edit(
                    chat_id=chat_id, message_id=message_id, markup=message.reply_markup
                )

            elif message_text.startswith("🗑"):  # Корзина
                generated = trash_can_message(
                    settings=settings, chat_id=chat_id, id_list=id_list, page=page
                )
                generated.edit(
                    chat_id=chat_id, message_id=message_id, markup=message.reply_markup
                )

            elif re_date.match(message_text):
                msg_date = re_date.match(message_text)[0]
                if page.startswith("!"):
                    generated = recurring_events_message(
                        settings=settings,
                        date=msg_date,
                        chat_id=chat_id,
                        id_list=id_list,
                        page=page[1:],
                    )
                else:
                    generated = daily_message(
                        settings=settings,
                        chat_id=chat_id,
                        date=msg_date,
                        id_list=id_list,
                        page=page,
                        message_id=message_id,
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
                        val=f"event({event.date}, {event.event_id}, {message_id}).edit\n"
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

                generated.edit(chat_id=chat_id, message_id=message_id, markup=markup)

            elif message_text.startswith("🔔"):  # Будильник
                notifications_message(
                    user_id_list=[chat_id],
                    id_list=id_list,
                    page=page,
                    message_id=message_id,
                    markup=message.reply_markup,
                )

        except ApiTelegramException:
            bot.answer_callback_query(
                callback_query_id=call_id,
                text=get_translate("already_on_this_page", settings.lang),
            )

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
                bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=markup
                )
            except ApiTelegramException:  # Сообщение не изменено
                callback_handler(
                    settings=settings,
                    chat_id=chat_id,
                    message_id=message_id,
                    message_text=message_text,
                    call_data="/calendar",
                    call_id=call_id,
                    message=message,
                )
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

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
                bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=markup
                )
            except (
                ApiTelegramException
            ):  # Если нажата кнопка ⟳, но сообщение не изменено
                date = now_time_strftime(settings.timezone)
                generated = daily_message(
                    settings=settings, chat_id=chat_id, date=date, message_id=message_id
                )
                generated.edit(chat_id=chat_id, message_id=message_id)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data.startswith("settings"):
        par_name, par_val = call_data.split(" ", maxsplit=2)[1:]

        # TODO par_name проверять из словаря
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

        SQL(
            f"""
UPDATE settings
   SET {par_name} = ?
 WHERE user_id = ?;
""",
            params=(par_val, chat_id),
            commit=True,
        )

        settings = UserSettings(chat_id)
        set_bot_commands(chat_id, settings.user_status, settings.lang)
        generated = settings_message(settings)
        try:
            generated.edit(chat_id=chat_id, message_id=message_id)
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
                settings=settings,
                chat_id=chat_id,
                date=call_data,
                message_id=message_id,
            )
            generated.edit(chat_id=chat_id, message_id=message_id)
        else:
            bot.answer_callback_query(callback_query_id=call_id, text="🤔")

    elif call_data == "update":
        update_message_action(settings, chat_id, message_id, message_text, call_id)

    elif call_data.startswith("help"):
        try:
            generated = help_message(settings, call_data)
            markup = None if call_data.startswith("help page") else message.reply_markup
            generated.edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("already_on_this_page", settings.lang)
            bot.answer_callback_query(call_id, text)

    elif call_data == "clean_bin":
        SQL(
            """
DELETE FROM events
      WHERE user_id = ? AND 
            removal_time != 0;
""",
            params=(chat_id,),
            commit=True,
        )
        update_message_action(settings, chat_id, message_id, message_text)


def clear_state(chat_id: int | str):
    """
    Очищает состояние приёма сообщения у пользователя и изменяет сообщение по id из add_event_date
    """
    add_event_date = SQL(
        """
SELECT add_event_date
  FROM settings
 WHERE user_id = ?;
""",
        params=(chat_id,),
    )[0][0]

    if add_event_date:
        msg_date, message_id = add_event_date.split(",")
        SQL(
            """
UPDATE settings
   SET add_event_date = 0
 WHERE user_id = ?;
""",
            params=(chat_id,),
            commit=True,
        )
        update_message_action(UserSettings(chat_id), chat_id, message_id, msg_date)

