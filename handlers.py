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
from bot import bot
from db.db import SQL
from lang import get_translate
from limits import create_image, is_exceeded_limit
from user_settings import UserSettings
from time_utils import (
    now_time_strftime,
    now_time,
    DayInfo,
    new_time_calendar,
    convert_date_format,
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
from messages.message_generators import (
    search,
    week_event_list,
    deleted,
    daily_message,
    notifications,
    recurring,
    settings_message,
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
re_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}")
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
        text = get_translate("choose_date", settings.lang)
        markup = create_monthly_calendar_keyboard(
            chat_id, settings.timezone, settings.lang
        )
        bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

    elif message_text.startswith("/start"):
        bot.set_commands(settings)
        markup = generate_buttons(
            [
                {"/calendar": "/calendar"},
                {
                    get_translate("add_bot_to_group", settings.lang): {
                        "url": f"https://t.me/{bot.username}?startgroup=AddGroup"
                    }
                },
            ]
        )
        bot.send_message(
            chat_id=chat_id,
            text=get_translate("start", settings.lang),
            reply_markup=markup,
        )

    elif message_text.startswith("/deleted"):
        if settings.user_status in (1, 2) or is_admin_id(chat_id):
            generated = deleted(settings=settings, chat_id=chat_id)
            generated.send(chat_id=chat_id)
        else:
            bot.set_commands(settings)
            bot.send_message(
                chat_id=chat_id,
                text=get_translate("deleted", settings.lang),
                reply_markup=delmarkup,
            )

    elif message_text.startswith("/week_event_list"):
        generated = week_event_list(settings=settings, chat_id=chat_id)
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
        generated = search(settings=settings, chat_id=chat_id, query=query)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/dice"):
        value = bot.send_dice(chat_id=chat_id).json["dice"]["value"]
        sleep(4)
        bot.send_message(chat_id=chat_id, text=value)

    elif message_text.startswith("/help"):  # TODO Удалить "help" из lang.py
        text, keyboard = get_translate("help page 1", settings.lang)
        bot.send_message(
            chat_id=chat_id,
            text=f"{get_translate('help title', settings.lang)}\n{text}",
            reply_markup=generate_buttons(keyboard),
        )

    elif message_text.startswith("/settings"):
        generated = settings_message(settings)
        generated.send(chat_id=chat_id)

    elif message_text.startswith("/today"):
        message_date = now_time_strftime(settings.timezone)
        generated = daily_message(settings=settings, chat_id=chat_id, date=message_date)
        new_message = generated.send(chat_id=chat_id)

        # Чтобы не создавать новый `generated`, изменяем уже существующее, если в сообщение событие только одно.
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
                generated.edit(
                    chat_id=chat_id, message_id=new_message.message_id, only_markup=True
                )
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
                file=file, query=query, commit=message_text.endswith("\n--commit=True")
            )
        except Error as e:
            bot.reply_to(message, text=f'[handlers.py -> "/SQL"] Error "{e}"')
        else:
            file.seek(0)
            bot.send_document(
                chat_id=chat_id,
                document=InputFile(file),
                caption=f"<code>/SQL {query}</code>",
                reply_to_message_id=message.message_id,
            )
        finally:
            file.close()

    elif message_text.startswith("/bell"):
        notifications(user_id_list=[chat_id], from_command=True)

    elif message_text.startswith("/save_to_csv"):
        response, t = CSVCooldown.check(key=chat_id, update_dict=False)

        if response:
            bot.send_chat_action(chat_id=chat_id, action="upload_document")
            file = StringIO()
            file.name = f"ToDoList {message.from_user.username} ({now_time_strftime(settings.timezone)}).csv"
            table = SQL(
                f"""
SELECT event_id, date, status, text FROM events
WHERE user_id={chat_id} AND isdel=0;
""",
                column_names=True,
            )
            file_writer = csv.writer(file)
            [
                file_writer.writerows(
                    [
                        [
                            str(event_id),
                            event_date,
                            str(event_status),
                            remove_html_escaping(event_text),
                        ]
                    ]
                )
                for event_id, event_date, event_status, event_text in table
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
            user_id, user_status = message_text.split(" ")[1:]

            try:
                if user_status not in (-1, 0, 1, 2):
                    raise ValueError

                SQL(
                    f"UPDATE settings SET user_status='{user_status}' WHERE user_id={user_id};",
                    commit=True,
                )

                if not bot.set_commands(settings):
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
        bot.reply_to(
            message=message,
            text=f"@{message.from_user.username}\n" f"Your id <code>{chat_id}</code>",
        )

    elif message_text.startswith("/deleteuser") and is_admin_id(chat_id):
        if len(message_text.split(" ")) == 2:
            user_id = int(message_text.removeprefix("/deleteuser "))
            if not is_admin_id(user_id):
                try:
                    # TODO присылать sql файл для восстановления
                    SQL(f"DELETE FROM events   WHERE user_id={user_id};", commit=True)
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
        if message_text == "/account":
            date = now_time(settings.timezone)
        else:
            str_date = message_text[9:]
            if re_call_data_date.search(str_date):
                try:
                    date = convert_date_format(str_date)
                except ValueError:
                    bot.send_message(chat_id, get_translate("error", settings.lang))
                    return
            else:
                bot.send_message(chat_id, get_translate("error", settings.lang))
                return

            if not 1980 < date.year < 3000:
                bot.send_message(chat_id, get_translate("error", settings.lang))
                return

        bot.send_photo(
            chat_id,
            create_image(settings, date.year, date.month, date.day),
            reply_markup=delmarkup,
        )

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
            f"UPDATE settings SET add_event_date='{date},{message_id}'"
            f"WHERE user_id={chat_id};",
            commit=True,
        )

        text = get_translate("send_event_text", settings.lang)
        bot.answer_callback_query(call_id, text)

        text = f"{message.html_text}\n\n<b>?.?.</b>⬜\n{text}"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=backmarkup)

    elif call_data == "/calendar":
        text = get_translate("choose_date", settings.lang)
        markup = create_monthly_calendar_keyboard(
            chat_id, settings.timezone, settings.lang
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("back"):
        # не вызываем await clear_state(chat_id) так как она после очистки вызывает сегодняшнее сообщение
        add_event_date = SQL(
            f"SELECT add_event_date FROM settings WHERE user_id={chat_id};"
        )[0][0]

        if add_event_date:
            add_event_message_id = add_event_date.split(",")[1]
            if int(message_id) == int(add_event_message_id):
                SQL(
                    f"UPDATE settings SET add_event_date=0 WHERE user_id={chat_id};",
                    commit=True,
                )

        msg_date = message_text[:10]

        if call_data.endswith("bin"):  # Корзина
            generated = deleted(settings=settings, chat_id=chat_id)
            generated.edit(chat_id=chat_id, message_id=message_id)

        elif message_text.startswith("🔍 "):  # Поиск
            first_line = message_text.split("\n", maxsplit=1)[0]
            raw_query = first_line.split(maxsplit=2)[-1][:-1]
            query = to_html_escaping(raw_query)
            generated = search(settings=settings, chat_id=chat_id, query=query)
            generated.edit(chat_id=chat_id, message_id=message_id)

        elif len(msg_date.split(".")) == 3:  # Проверка на дату
            try:  # Пытаемся изменить сообщение
                generated = daily_message(
                    settings=settings,
                    chat_id=chat_id,
                    date=msg_date,
                    message_id=message_id,
                )
                generated.edit(chat_id=chat_id, message_id=message_id)
            except ApiTelegramException:
                # Если сообщение не изменено, то шлём календарь
                # "dd.mm.yyyy" -> [yyyy, mm]
                YY_MM = [int(x) for x in msg_date.split(".")[1:]][::-1]
                text = get_translate("choose_date", settings.lang)
                markup = create_monthly_calendar_keyboard(
                    chat_id, settings.timezone, settings.lang, YY_MM
                )
                bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data == "message_del":
        try:
            bot.delete_message(chat_id, message_id)
        except ApiTelegramException:
            text = get_translate("get_admin_rules", settings.lang)
            bot.reply_to(message=message, text=text, reply_markup=delmarkup)

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
        raw_text = message_text.split("\n", maxsplit=2)[-1]
        text = to_html_escaping(raw_text)  # Получаем изменённый текст
        first_line = message_text.split("\n", maxsplit=1)[0]
        msg_date, event_id = first_line.split(" ", maxsplit=2)[:2]

        try:
            SQL(
                f"""
UPDATE events SET text='{text}'
WHERE user_id={chat_id} AND event_id={event_id}
AND date='{msg_date}';
""",
                commit=True,
            )
        except Error as e:
            logging.info(
                f'[handlers.py -> callback_handler -> "confirm change"] Error "{e}"'
            )
            error = get_translate("error", settings.lang)
            bot.answer_callback_query(call_id, error)

        callback_handler(
            settings=UserSettings(chat_id),
            chat_id=chat_id,
            message_id=message_id,
            message_text=msg_date,
            call_data="update",
            call_id=None,
            message=None,
        )

    elif call_data.startswith("select event "):
        # action: Literal["edit", "status", "delete", "delete bin", "recover bin", "open"]
        action = call_data[13:]

        events_list = message_text.split("\n\n")[1:]

        # Заглушка если событий нет
        if events_list[0].startswith("👀") or events_list[0].startswith("🕸"):
            no_events_to_interact = get_translate("no_events_to_interact", settings.lang)
            bot.answer_callback_query(call_id, no_events_to_interact, True)
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
SELECT text FROM events 
WHERE event_id={event_id} AND user_id={chat_id}
{"AND isdel!=0" if action.endswith("bin") else ""};
"""
                )[0][0]
            except IndexError:  # Если этого события не существует
                callback_handler(
                    settings=settings,
                    chat_id=chat_id,
                    message_id=message_id,
                    message_text=message_text,
                    call_data="update",
                    call_id=call_id,
                    message=message,
                )
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
SELECT text FROM events 
WHERE event_id={event_id} AND user_id={chat_id}
AND isdel{"!" if action.endswith("bin") else ""}=0;
"""
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
            callback_handler(
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data="update",
                call_id=call_id,
                message=message,
            )
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
            search = get_translate("search", settings.lang)
            choose_event = get_translate("choose_event", settings.lang)
            text = f"🔍 {search} {query}:\n{choose_event}"

        else:
            choose_event = get_translate("choose_event", settings.lang)
            text = f"{msg_date}\n{choose_event}"

        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("recover"):
        event_date, event_id = call_data.split(maxsplit=2)[1:]

        try:
            event_len = SQL(
                f"""
SELECT LENGTH(text) FROM events
WHERE user_id={chat_id} AND event_id={event_id}
AND date='{event_date}' AND isdel!=0;
"""
            )[0][0]
        except IndexError:
            error = get_translate("error", settings.lang)
            bot.answer_callback_query(call_id, error, True)
            return  # такого события нет

        if is_exceeded_limit(settings, event_date, event_count=1, symbol_count=event_len):
            exceeded_limit = get_translate("exceeded_limit", settings.lang)
            bot.answer_callback_query(call_id, exceeded_limit, True)
            return

        SQL(
            f"""
UPDATE events SET isdel=0
WHERE user_id={chat_id} AND event_id={event_id}
AND date='{event_date}';
""",
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
                f"""
SELECT text, status FROM events
WHERE user_id={chat_id} AND event_id='{event_id}'
AND isdel=0 AND date='{event_date}';
"""
            )[0]
        except IndexError:  # Если этого события уже нет
            callback_handler(
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data="back",
                call_id=call_id,
                message=message,
            )
            return

        if call_data.startswith("status_home_page"):
            sl = status.split(",")
            sl.extend([""] * (5 - len(sl)))
            markup = generate_buttons(
                [
                    *[
                        {
                            f"{title}{config.callbackTab * 20}": (
                                f"{data}"
                                if data
                                else f"status set {title.split(maxsplit=1)[0]} {event_id} {event_date}"
                            )
                        }
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

            # Если статус равен ⬜️, то удалить первую строчку с предложением обнулить все статусы.
            if status == "⬜️":
                # Убираем первую строку клавиатуры
                markup.keyboard = markup.keyboard[1:]
        else:  # status page
            buttons_data = get_translate(call_data, settings.lang)
            markup = generate_buttons(
                [
                    *[
                        {
                            f"{row}{config.callbackTab * 20}": f"status set {row.split(maxsplit=1)[0]} {event_id} {event_date}"
                            for row in status_column
                        }
                        if len(status_column) > 1
                        else {
                            f"{status_column[0]}{config.callbackTab * 20}": f"status set {status_column[0].split(maxsplit=1)[0]} {event_id} {event_date}"
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
                f"""
SELECT text, status FROM events
WHERE user_id={chat_id} AND event_id='{event_id}'
AND isdel=0 AND date='{event_date}';
"""
            )[0]
        except IndexError:
            callback_handler(
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data="back",
                call_id=call_id,
                message=message,
            )
            return

        if new_status == "⬜️" == old_status:
            callback_handler(
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data="back",
                call_id=call_id,
                message=message,
            )
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

        elif ("🔗" in old_status or "❌🔗" in old_status) and new_status in ("🔗", "❌🔗"):
            text = get_translate("conflict_statuses", settings.lang) + " 🔗, ❌🔗"
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
                f"""
UPDATE events SET status='{res_status}'
WHERE user_id={chat_id} AND event_id={event_id}
AND date='{event_date}';
""",
                commit=True,
            )

        if new_status == "⬜️":
            callback_handler(
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data="back",
                call_id=call_id,
                message=message,
            )
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
                f"""
SELECT text, status FROM events
WHERE user_id={chat_id} AND event_id='{event_id}'
AND isdel=0 AND date='{event_date}';
"""
            )[0]
        except IndexError:
            callback_handler(
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data="back",
                call_id=call_id,
                message=message,
            )
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
            f"""
UPDATE events SET status='{res_status}' 
WHERE user_id={chat_id} AND event_id={event_id} 
AND date='{event_date}';
""",
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
SELECT text, status FROM events
WHERE user_id={chat_id} AND event_id={event_id} AND date='{event_date}' AND
isdel{"!" if back_to_bin == "bin" else ""}=0;
"""
            )[0]
        except IndexError as e:
            logging.info(
                f'[handlers.py -> callback_handler -> "before del"] IndexError "{e}"'
            )
            error = get_translate("error", settings.lang)
            bot.answer_callback_query(call_id, error)
            callback_handler(
                settings=settings,
                chat_id=chat_id,
                message_id=message_id,
                message_text=message_text,
                call_data="back",
                call_id=call_id,
                message=message,
            )
            return

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
                    f"""
UPDATE events SET isdel='{now_time_strftime(settings.timezone)}' 
WHERE user_id={chat_id} AND date='{event_date}' AND event_id={event_id};
""",
                    commit=True,
                )
            else:
                SQL(
                    f"""
DELETE FROM events 
WHERE user_id={chat_id} AND date='{event_date}' AND event_id={event_id};
""",
                    commit=True,
                )
        except Error as e:
            logging.info(f'[handlers.py -> callback_handler -> "del"] Error "{e}"')
            error = get_translate("error", settings.lang)
            bot.answer_callback_query(call_id, error)

        callback_handler(
            settings=settings,
            chat_id=chat_id,
            message_id=message_id,
            message_text=message_text,
            call_data="back" if where != "bin" else "back bin",
            call_id=call_id,
            message=message,
        )

    elif call_data.startswith("|"):  # Список id событий на странице
        page, id_list = call_data.split("|")[1:]
        id_list = id_list.split(",")

        try:
            if message_text.startswith("🔍 "):  # Поиск
                first_line = message_text.split("\n", maxsplit=1)[0]
                raw_query = first_line.split(maxsplit=2)[-1][:-1]
                query = to_html_escaping(raw_query)
                generated = search(
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
                generated = week_event_list(
                    settings=settings, chat_id=chat_id, id_list=id_list, page=page
                )
                generated.edit(
                    chat_id=chat_id, message_id=message_id, markup=message.reply_markup
                )

            elif message_text.startswith("🗑"):  # Корзина
                generated = deleted(
                    settings=settings, chat_id=chat_id, id_list=id_list, page=page
                )
                generated.edit(
                    chat_id=chat_id, message_id=message_id, markup=message.reply_markup
                )

            elif re_date.match(message_text):
                msg_date = re_date.match(message_text)[0]
                if page.startswith("!"):
                    generated = recurring(
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
                notifications(
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
        if isinstance(par_val, str):
            par_val = f"'{par_val}'"

        SQL(
            f"UPDATE settings SET {par_name}={par_val} WHERE user_id={chat_id};",
            commit=True,
        )

        settings = UserSettings(chat_id)
        bot.set_commands(settings)
        generated = settings_message(settings)
        try:
            generated.edit(chat_id=chat_id, message_id=message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("recurring"):
        generated = recurring(
            settings=settings, date=message_text[:10], chat_id=chat_id
        )
        generated.edit(chat_id=chat_id, message_id=message_id)

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
        if message_text.startswith("🔍 "):  # Поиск
            first_line = message_text.split("\n", maxsplit=1)[0]
            raw_query = first_line.split(maxsplit=2)[-1][:-1]
            query = to_html_escaping(raw_query)
            generated = search(settings=settings, chat_id=chat_id, query=query)

        elif message_text.startswith("📆"):  # Если /week_event_list
            generated = week_event_list(settings=settings, chat_id=chat_id)

        elif message_text.startswith("🗑"):  # Корзина
            generated = deleted(settings=settings, chat_id=chat_id)

        elif re_date.match(message_text) is not None:
            msg_date = re_date.match(message_text)[0]
            generated = daily_message(
                settings=settings, chat_id=chat_id, date=msg_date, message_id=message_id
            )

        else:
            return

        try:
            generated.edit(chat_id=chat_id, message_id=message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("help"):
        try:
            translate = get_translate(call_data, settings.lang)
            title = get_translate("help title", settings.lang)
            if call_data.startswith("help page"):
                text, keyboard = translate
                bot.edit_message_text(
                    f"{title}\n{text}",
                    chat_id,
                    message_id,
                    reply_markup=generate_buttons(keyboard),
                )
            else:
                bot.edit_message_text(
                    f"{title}\n{translate}",
                    chat_id,
                    message_id,
                    reply_markup=message.reply_markup,
                )
        except ApiTelegramException:
            bot.answer_callback_query(
                callback_query_id=call_id,
                text=get_translate("already_on_this_page", settings.lang),
            )

    elif call_data == "clean_bin":
        SQL(
            f"""
DELETE FROM events WHERE user_id={chat_id} AND isdel!=0;
""",
            commit=True,
        )
        callback_handler(
            settings=settings,
            chat_id=chat_id,
            message_id=message_id,
            message_text=message_text,
            call_data="update",
            call_id=call_id,
            message=message,
        )


def clear_state(chat_id: int | str):
    """
    Очищает состояние приёма сообщения у пользователя и изменяет сообщение по id из add_event_date
    """
    add_event_date = SQL(
        f"SELECT add_event_date FROM settings WHERE user_id={chat_id};"
    )[0][0]

    if add_event_date:
        msg_date, message_id = add_event_date.split(",")
        SQL(
            f"UPDATE settings SET add_event_date=0 WHERE user_id={chat_id};",
            commit=True,
        )
        callback_handler(
            settings=UserSettings(chat_id),
            chat_id=chat_id,
            message_id=message_id,
            message_text=msg_date,
            call_data="update",
            call_id=None,
            message=None,
        )
