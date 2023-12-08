import re
import html
import logging
from time import sleep
from io import StringIO
from sqlite3 import Error
from ast import literal_eval

from telebot.apihelper import ApiTelegramException  # noqa
from telebot.types import (  # noqa
    Message,
    InputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from tgbot import config
from tgbot.queries import queries
from tgbot.request import request
from tgbot.bot import bot, set_bot_commands
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.message_generator import NoEventMessage, CallBackAnswer
from tgbot.time_utils import (
    now_time_strftime,
    now_time,
    new_time_calendar,
    convert_date_format,
    DayInfo,
)
from tgbot.bot_actions import (
    delete_message_action,
    press_back_action,
    update_message_action,
    re_date,
    before_move_message,
)
from tgbot.buttons_utils import (
    create_monthly_calendar_keyboard,
    delmarkup,
    edit_button_attrs,
    create_yearly_calendar_keyboard,
    create_twenty_year_calendar_keyboard,
)
from tgbot.bot_messages import (
    menu_message,
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
    limits_message,
    admin_message,
    group_message,
    account_message,
    user_message,
)
from tgbot.utils import (
    fetch_weather,
    fetch_forecast,
    write_table_to_str,
    add_status_effect,
    is_secure_chat,
    parse_message,
    re_call_data_date,
    html_to_markdown,
)
from todoapi.api import User
from todoapi.types import db, UserSettings
from todoapi.utils import (
    is_admin_id,
    is_premium_user,
    is_valid_year,
)
from telegram_utils.argument_parser import get_arguments
from telegram_utils.buttons_generator import generate_buttons
from telegram_utils.command_parser import parse_command, get_command_arguments


def command_handler(message: Message) -> None:
    """
    Отвечает за реакцию бота на команды
    Метод message.text.startswith("")
    используется и для групп (в них сообщение приходит в формате /command{bot.user.username})
    """
    user, chat_id = request.user, request.chat_id
    settings, message_text = user.settings, message.text
    parsed_command = parse_command(message_text, {"arg": "long str"})
    command_text, command_arguments = (
        parsed_command["command"],
        parsed_command["arguments"],
    )

    if command_text == "menu":
        generated = menu_message()
        generated.send(chat_id)

    elif command_text == "calendar":
        generated = monthly_calendar_message()
        generated.send(chat_id)

    elif command_text == "start":
        set_bot_commands()
        generated = start_message()
        generated.send(chat_id)

    elif command_text == "deleted":
        if is_premium_user(user):
            generated = trash_can_message()
            generated.send(chat_id)
        else:
            set_bot_commands()
            generated = NoEventMessage(get_translate("errors.deleted"), delmarkup())
            generated.send(chat_id)

    elif command_text == "week_event_list":
        generated = week_event_list_message()
        generated.send(chat_id)

    elif command_text in ("weather", "forecast"):
        # Проверяем есть ли аргументы
        nowcity = get_command_arguments(
            message_text, {"city": ("long str", settings.city)}
        )["city"]

        try:
            if command_text == "weather":
                text = fetch_weather(city=nowcity)
            else:  # forecast
                text = fetch_forecast(city=nowcity)
        except KeyError:
            if command_text == "weather":
                text = get_translate("errors.weather_invalid_city_name")
            else:  # forecast
                text = get_translate("errors.forecast_invalid_city_name")

        generated = NoEventMessage(text, delmarkup())
        generated.send(chat_id)

    elif command_text == "search":
        html_text = get_command_arguments(
            message.html_text, {"query": ("long str", "")}
        )["query"]
        query = html_to_markdown(html_text)
        generated = search_message(query)
        generated.send(chat_id)

    elif command_text == "dice":
        value = bot.send_dice(chat_id).json["dice"]["value"]
        sleep(4)
        NoEventMessage(value).send(chat_id)

    elif command_text == "help":
        generated = help_message()
        generated.send(chat_id)

    elif command_text == "settings":
        generated = settings_message()
        generated.send(chat_id)

    elif command_text == "today":
        message_date = now_time_strftime()
        generated = daily_message(message_date)
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
                val=f"event({event.event_id}, {new_message.message_id}).text\n"
                f"{event.text}",
            )

            try:
                generated.edit(chat_id, new_message.message_id, only_markup=True)
            except ApiTelegramException:  # message is not modified
                pass

    elif command_text == "sqlite" and is_secure_chat(message):
        bot.send_chat_action(chat_id, "upload_document")

        try:
            with open(config.DATABASE_PATH, "rb") as file:
                bot.send_document(
                    chat_id,
                    file,
                    caption=now_time_strftime(),
                )
        except ApiTelegramException:
            NoEventMessage("Отправить файл не получилось").send(chat_id)

    elif command_text == "SQL" and is_secure_chat(message):
        # Выполнение запроса от админа к базе данных и красивый вывод результатов
        query = html_to_markdown(message.html_text.removeprefix("/SQL ")).strip()

        if not query.lower().startswith("select"):
            bot.send_chat_action(chat_id, "typing")
            try:
                db.execute(
                    query.removesuffix("\nCOMMIT"), commit=query.endswith("\nCOMMIT")
                )
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

    elif command_text == "export":
        file_format = get_command_arguments(
            message_text,
            {"format": ("str", "csv")},
        )["format"].strip()

        if file_format not in ("csv", "xml", "json", "jsonl"):
            NoEventMessage(get_translate("errors.export_format")).reply(message)
            return

        api_response = user.export_data(
            f"events_{now_time().strftime('%Y-%m-%d_%H-%M-%S')}.{file_format}",
            f"{file_format}",
        )

        if api_response[0]:
            bot.send_chat_action(chat_id, "upload_document")

            try:
                bot.send_document(chat_id, InputFile(api_response[1]))
            except ApiTelegramException as e:
                logging.info(f'export ApiTelegramException "{e}"')
                big_file_translate = get_translate("errors.file_is_too_big")
                bot.send_message(chat_id=chat_id, text=big_file_translate)
        else:
            if re.match(r"Wait \d+ min", api_response[1]):
                export_error = get_translate("errors.export")
                generated = NoEventMessage(
                    export_error.format(t=api_response[1].split(" ")[1])
                )
            else:
                generated = NoEventMessage(get_translate("errors.error"))
            generated.send(chat_id)

    elif command_text == "version":
        NoEventMessage(f"Version {config.__version__}").send(chat_id)

    elif message_text.startswith("/idinfo ") and is_secure_chat(message):
        user_id = get_command_arguments(message_text, {"id": "int"})["id"]
        if user_id:
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
            command_handler(message)
        except ApiTelegramException:
            pass

    elif command_text == "id":
        if message.reply_to_message:
            NoEventMessage(
                f"Message id <code>{message.reply_to_message.id}</code>"
            ).reply(message)
        else:
            NoEventMessage(f"Chat id <code>{chat_id}</code>").reply(message)

    elif command_text == "limits":
        date = get_command_arguments(message_text, {"date": ("date", "now")})["date"]
        limits_message(date)

    elif command_text == "commands":  # TODO перевод
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
/export - Сохранить мои события в csv
/help - Помощь
/settings - Настройки
/search {...} - Поиск
/id - Получить свой Telegram id

/commands - Этот список
""" + (
            """
/version - Версия бота
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
    "select event move" - Если событий несколько, то предлагает выбрать конкретное для удаления или *перемещение в корзину. *в зависимости от прав пользователя
                  Если событие одно, то предлагает сразу для него удалить или *переместить в корзину. *в зависимости от прав пользователя
    "select event move bin" - Делает то же самое что и "select event delete", но после выполнения возвращает сообщение в корзину.
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
    "calendar_y" -
    "calendar_m" -
    "settings" - par_name, par_val - Изменить значение колонки par_name на par_val и обновить сообщение с новыми настройками
    "recurring" - Вызвать сообщение с повторяющимися событиями. Например, дни рождения за прошлые года.
    "<<<", ">>>" - Изменение на 1 день в сообщении на дату.
    r"\A\d{1,2}\.\d{1,2}\.\d{4}\Z" - Вызвать сообщение с текущей датой.
    "update" - Обновить сообщение в зависимости от типа. Поддерживает сообщения типа поиск, week_event_list, корзина, сообщение с датой.
    """
    user, chat_id = request.user, request.chat_id
    settings = user.settings

    if call_data == "menu":
        generated = menu_message()
        generated.edit(chat_id, message_id)

    elif call_data == "event_add":
        clear_state(chat_id)
        date = message_text[:10]

        # Проверяем будет ли превышен лимит для пользователя, если добавить 1 событие с 1 символом
        if user.check_limit(date, event_count=1, symbol_count=1)[1] is True:
            text = get_translate("errors.exceeded_limit")
            CallBackAnswer(text).answer(call_id, True)
            return

        db.execute(
            queries["update add_event_date"],
            params=(f"{date},{message_id}", chat_id),
            commit=True,
        )

        text = get_translate("send_event_text")
        CallBackAnswer(text).answer(call_id)

        text = f"{message.html_text}\n\n<b>?.?.</b>⬜\n{text}"
        backmarkup = generate_buttons([[{get_theme_emoji("back"): "back"}]])
        bot.edit_message_text(text, chat_id, message_id, reply_markup=backmarkup)

    elif call_data.startswith("back"):
        press_back_action(call_data, message_id, message.html_text)

    elif call_data == "message_del":
        delete_message_action(message)

    elif call_data == "confirm change":
        first_line, _, text = message_text.split("\n", maxsplit=2)
        event_id = first_line.split(" ", maxsplit=2)[1]

        api_response = user.edit_event_text(event_id, text)
        if not api_response[0]:
            logging.info(f'user.edit_event "{api_response[1]}"')
            error = get_translate("errors.error")
            CallBackAnswer(error).answer(call_id, True)
            return

        update_message_action(message_id, message.html_text)
        CallBackAnswer(get_translate("changes_saved")).answer(call_id)

    elif call_data.startswith("select event "):
        # action: Literal["edit", "status", "delete", "delete bin", "recover bin", "open"]
        action: str = call_data.removeprefix("select event ")

        events_list = parse_message(message_text)
        msg_date = message_text[:10]

        # Заглушка если событий нет
        if len(events_list) == 0:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)
            return

        # Если событие одно, то оно сразу выбирается
        if len(events_list) == 1:
            event = events_list[0]
            if not user.check_event(event.event_id, action.endswith("bin"))[1]:
                update_message_action(message_id, message.html_text)
                return

            if action in (
                "status",
                "move",
                "move bin",
                "recover bin",
            ) or action.startswith("open"):
                match action:
                    case "status":
                        new_call_data = (
                            f"status_home_page {event.event_id} {event.date}"
                        )
                    case "move":
                        new_call_data = f"before move {event.date} {event.event_id} _"
                    case "move bin":
                        new_call_data = f"move {event.date} {event.event_id} bin delete"
                    case "recover bin":
                        new_call_data = f"recover {event.date} {event.event_id}"
                    case _:  # "select event open"
                        new_call_data = f"{event.date}"

                callback_handler(
                    message_id=message_id,
                    message_text=message_text,
                    call_data=new_call_data,
                    call_id=call_id,
                    message=message,
                )
                return

        markup = InlineKeyboardMarkup()
        for event in events_list:
            api_response = user.get_event(event.event_id, action.endswith("bin"))

            if not api_response[0]:  # Проверяем существование события
                continue

            event.text = api_response[1].text
            button_title = (
                f"{event.date}.{event.event_id}.{event.status} "
                f"{event.text}{config.callbackTab * 20}"
            )[:60]
            button_title2 = (
                f"{event.event_id}.{event.status} "
                f"{event.text}{config.callbackTab * 20}"
            )[:60]

            if action == "edit":
                callback_data = (
                    f"event({event.event_id}, {message.message_id}).text\n"
                    f"{event.text}"
                )
                button = InlineKeyboardButton(
                    button_title2, switch_inline_query_current_chat=callback_data
                )

            elif action in ("status", "move"):  # Действия в обычном дне
                if action == "status":
                    callback_data = f"status_home_page {event.event_id} {event.date}"
                else:  # "delete"
                    callback_data = f"before move {event.date} {event.event_id} _"

                button = InlineKeyboardButton(
                    button_title2, callback_data=callback_data
                )

            elif action in ("move bin", "recover bin"):  # Действия в корзине
                if action == "move bin":
                    callback_data = f"move {event.date} {event.event_id} bin delete"
                else:  # "recover bin"
                    callback_data = f"recover {event.date} {event.event_id}"

                button = InlineKeyboardButton(button_title, callback_data=callback_data)

            elif action.startswith("open"):
                callback_data = f"{event.date}"
                button = InlineKeyboardButton(button_title, callback_data=callback_data)

            else:
                continue

            markup.row(button)

        if not markup.to_dict()["inline_keyboard"]:  # Созданный markup пустой
            update_message_action(message_id, message.html_text)
            return

        match action:
            case "open":
                back_data = "back"
            case x if x.startswith("open "):
                back_data = x.removeprefix("open ")
            case x if x.endswith("bin"):
                back_data = "back bin"
            case _:
                back_data = "back"

        markup.row(
            InlineKeyboardButton(get_theme_emoji("back"), callback_data=back_data)
        )

        if action == "edit":
            select_event = get_translate("select.event_to_edit")
            text = f"{msg_date}\n{select_event}"

        elif action == "status":
            select_event = get_translate("select.event_to_change_status")
            text = f"{msg_date}\n{select_event}"

        elif action == "move":
            select_event = get_translate("select.event_to_move")
            text = f"{msg_date}\n{select_event}"

        elif action == "move bin":
            basket = get_translate("messages.basket")
            select_event = get_translate("select.event_to_move")
            text = f"{basket}\n{select_event}"

        elif action == "recover bin":
            basket = get_translate("messages.basket")
            select_event = get_translate("select.event_to_recover")
            text = f"{basket}\n{select_event}"

        elif message_text.startswith("🔍 "):
            first_line = message.text.split("\n", maxsplit=1)[0]
            raw_query = first_line.split(maxsplit=2)[-1][:-1]
            query = html.escape(raw_query)
            translate_search = get_translate("messages.search")
            choose_event = get_translate("select.event_to_open")
            text = f"🔍 {translate_search} {query}:\n{choose_event}"

        elif action.startswith("open"):
            event_to_open = get_translate("select.event_to_open")
            text = f"{msg_date}\n{event_to_open}"  # ↖️

        else:
            choose_event = get_translate("select.event")
            text = f"{msg_date}\n{choose_event}"

        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

    elif call_data.startswith("recover"):
        event_date, event_id = call_data.split(maxsplit=2)[1:]
        event_id = int(event_id)

        if not user.recover_event(event_id)[0]:
            error = get_translate("errors.error")
            CallBackAnswer(error).answer(call_id, True)
            return  # такого события нет

        callback_handler(
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
        api_response = user.get_event(event_id)

        if not api_response[0]:  # Если этого события нет
            press_back_action(call_data, message_id, message.html_text)
            return

        event = api_response[1]
        text, status = event.text, event.status

        if call_data.startswith("status_home_page"):
            sl = status.split(",")
            sl.extend([""] * (5 - len(sl)))
            buttons_data = get_translate("buttons.status page.0")
            markup = generate_buttons(
                [
                    *[
                        [
                            {f"{title}{config.callbackTab * 20}": f"{data}"}
                            for (title, data) in row
                        ]
                        for row in buttons_data
                    ],
                    [
                        {
                            f"{i}"
                            if i
                            else " " * n: f"status delete {i} {event_id} {event_date}"
                            if i
                            else "None"
                        }
                        for n, i in enumerate(sl)
                    ]
                    if status != "⬜️"
                    else [],
                    [{get_theme_emoji("back"): "back"}],
                ]
            )
        else:  # status page
            buttons_data = get_translate(
                f"buttons.status page." + call_data.removeprefix("status page ")
            )
            markup = generate_buttons(
                [
                    *[
                        [
                            {
                                f"{row}{config.callbackTab * 20}": (
                                    f"status set "
                                    f"{row.split(maxsplit=1)[0]} "
                                    f"{event_id} "
                                    f"{event_date}"
                                )
                            }
                            for row in status_column
                        ]
                        for status_column in buttons_data
                    ],
                    [
                        {
                            get_theme_emoji(
                                "back"
                            ): f"status_home_page {event_id} {event_date}"
                        },
                    ],
                ]
            )

        bot.edit_message_text(
            f"{event_date}\n"
            f"<b>{get_translate('select.status_to_event')}\n"
            f"{event_date}.{event_id}.{status}</b>\n"
            f"{add_status_effect(text, status)}",
            chat_id,
            message_id,
            reply_markup=markup,
        )

    elif call_data.startswith("status set"):
        new_status, event_id, event_date = call_data.split()[2:]
        event_id = int(event_id)

        # Если события нет, то обновляем сообщение
        api_response = user.get_event(event_id)

        if not api_response[0]:
            press_back_action(call_data, message_id, message.html_text)
            return

        old_status = api_response[1].status

        if new_status == "⬜️" == old_status:
            press_back_action(call_data, message_id, message.html_text)
            return

        if old_status == "⬜️":
            res_status = new_status

        elif new_status == "⬜️":
            res_status = "⬜️"

        else:
            res_status = f"{old_status},{new_status}"

        api_response = user.edit_event_status(event_id, res_status)

        match api_response[1]:
            case "":
                text = ""
            case "Status Conflict":
                text = get_translate("errors.conflict_statuses")
            case "Status Length Exceeded":
                text = get_translate("errors.more_5_statuses")
            case "Status Repeats":
                text = get_translate("errors.status_already_posted")
            case _:
                text = get_translate("errors.error")

        if text:
            CallBackAnswer(text).answer(call_id, True)

        if new_status == "⬜️":
            press_back_action(call_data, message_id, message.html_text)
        else:
            callback_handler(
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
        api_response = user.get_event(event_id)

        if not api_response[0]:
            press_back_action(call_data, message_id, message.html_text)
            return

        event = api_response[1]
        text, old_status = event.text, event.status

        if status == "⬜️" or old_status == "⬜️":
            return

        statuses = old_status.split(",")
        statuses.remove(status)
        res_status = ",".join(statuses)

        if not res_status:
            res_status = "⬜️"

        user.edit_event_status(event_id, res_status)

        callback_handler(
            message_id=message_id,
            message_text=message_text,
            call_data=f"status_home_page {event_id} {event_date}",
            call_id=call_id,
            message=message,
        )

    elif call_data.startswith("before move "):
        event_date, event_id, back_to_bin = call_data.split()[2:]
        event_id = int(event_id)

        before_move_message(
            call_id,
            call_data,
            message_id,
            message_text,
            event_id,
            back_to_bin == "bin",
        )

    elif call_data.startswith("move "):
        event_date, event_id, where, mode = call_data.split(maxsplit=4)[1:]
        event_id = int(event_id)

        to_bin = mode == "to_bin" and (
            settings.user_status in (1, 2) or is_admin_id(chat_id)
        )

        if not user.delete_event(event_id, to_bin)[0]:
            error = get_translate("errors.error")
            CallBackAnswer(error).answer(call_id)

        press_back_action(
            "back" if where != "bin" else "back bin",
            message_id,
            message_text,
        )

    elif call_data.startswith("|"):  # Список id событий на странице
        page, id_list = call_data.split("|")[1:]
        id_list = id_list.split(",")

        try:
            if message_text.startswith("🔍 "):  # Поиск
                first_line = message.text.split("\n", maxsplit=1)[0]
                raw_query = first_line.split(maxsplit=2)[-1][:-1]
                query = html.escape(raw_query)
                generated = search_message(query, id_list, int(page))
                generated.edit(chat_id, message_id, markup=message.reply_markup)

            elif message_text.startswith("📆"):  # Если /week_event_list
                generated = week_event_list_message(id_list, int(page))
                generated.edit(chat_id, message_id, markup=message.reply_markup)

            elif message_text.startswith("🗑"):  # Корзина
                generated = trash_can_message(id_list, int(page))
                generated.edit(chat_id, message_id, markup=message.reply_markup)

            elif re_date.match(message_text):
                msg_date = re_date.match(message_text)[0]
                if page.startswith("!"):
                    generated = recurring_events_message(
                        msg_date, id_list, int(page[1:])
                    )
                else:
                    generated = daily_message(msg_date, id_list, int(page), message_id)

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
                        val=f"event({event.event_id}, {message_id}).text\n"
                        f"{html.unescape(event.text)}",
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
                    user_id_list=[chat_id],
                    id_list=id_list,
                    page=int(page),
                    message_id=message_id,
                    markup=message.reply_markup,
                    from_command=True,
                )

        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_data.startswith("calendar_t "):
        sleep(0.3)
        data: tuple = literal_eval(call_data.removeprefix("calendar_t "))
        command, back, decade = data

        if decade == "now":
            decade = int(str(now_time().year)[:3])
        else:
            decade = int(decade)

        if is_valid_year(int(str(decade) + "0")):
            markup = create_twenty_year_calendar_keyboard(decade, command, back)
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
            except ApiTelegramException:
                # Сообщение не изменено
                year = now_time().year
                markup = create_yearly_calendar_keyboard(year, command, back)
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        else:
            CallBackAnswer("🤔").answer(call_id)

    elif call_data.startswith("calendar_y "):
        sleep(0.5)
        data: tuple = literal_eval(call_data.removeprefix("calendar_y "))
        command, back, year = data

        if year == "now":
            year = now_time().year

        if is_valid_year(year):
            markup = create_yearly_calendar_keyboard(year, command, back)
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
            except ApiTelegramException:
                # Сообщение не изменено
                date = new_time_calendar()
                markup = create_monthly_calendar_keyboard(date, command, back)
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        else:
            CallBackAnswer("🤔").answer(call_id)

    elif call_data.startswith("calendar_m "):
        sleep(0.5)
        data: tuple = literal_eval(call_data.removeprefix("calendar_m "))
        command, back, date = data

        if date == "now":
            date = new_time_calendar()

        if is_valid_year(date[0]):
            markup = create_monthly_calendar_keyboard(date, command, back)
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
            except ApiTelegramException:
                # Если нажата кнопка ⟳, но сообщение не изменено
                now_date = now_time_strftime()

                if command is not None and back is not None:
                    call_data = f"{command} {now_date}"
                    callback_handler(
                        message_id, message_text, call_data, call_id, message
                    )
                    return

                generated = daily_message(now_date, message_id=message_id)
                generated.edit(chat_id, message_id)
        else:
            CallBackAnswer("🤔").answer(call_id)

    elif call_data.startswith("calendar"):
        if call_data == "calendar":
            generated = monthly_calendar_message()
            generated.edit(chat_id, message_id)
            return

        arguments = get_arguments(
            call_data.removeprefix("calendar"), {"year": "int", "month": "int"}
        )
        year, month = arguments["year"], arguments["month"]
        if not all((year, month)):
            return
        text = get_translate("select.date")
        markup = create_monthly_calendar_keyboard([year, month])
        NoEventMessage(text, markup).edit(chat_id, message_id)

    elif call_data.startswith("settings"):
        if call_data == "settings":
            generated = settings_message()

            try:
                generated.edit(chat_id, message_id)
            except ApiTelegramException:
                pass
            return

        par_name, par_val = call_data.split(" ", maxsplit=2)[1:]

        if par_name not in (
            "lang",
            "sub_urls",
            "city",
            "timezone",
            "direction",
            "user_status",
            "notifications",
            "notifications_time",
            "theme",
        ):
            return

        result = user.set_settings(**{par_name: par_val})
        if not result[0]:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
            logging.info(f"{par_name}={par_name} {result[1]}")

        settings = UserSettings(chat_id)
        request.user.settings = settings
        set_bot_commands()
        generated = settings_message()

        try:
            generated.edit(chat_id, message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("recurring"):
        generated = recurring_events_message(message_text[:10])
        generated.edit(chat_id, message_id)

    elif re_call_data_date.search(call_data):
        year = int(call_data[-4:])
        sleep(0.3)
        if is_valid_year(year):
            generated = daily_message(call_data, message_id=message_id)
            generated.edit(chat_id, message_id)
        else:
            CallBackAnswer("🤔").answer(call_id)

    elif call_data == "update":
        update_message_action(message_id, message.html_text, call_id)

    elif call_data.startswith("help"):
        if call_data == "help":
            generated = help_message()
            generated.edit(chat_id, message_id)
            return

        try:
            generated = help_message(call_data.removeprefix("help "))
            markup = None if call_data.startswith("help page") else message.reply_markup
            generated.edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_data == "clean_bin":
        if not user.clear_basket()[0]:
            error = get_translate("errors.error")
            CallBackAnswer(error).answer(call_id)
            return

        update_message_action(message_id, message.html_text)

    elif call_data == "restore_to_default":
        user.set_settings("ru", 1, "Москва", 3, "DESC", 0, 0, "08:00")

        if user.settings.lang != settings.lang:
            set_bot_commands()

        generated = settings_message()
        try:
            generated.edit(chat_id, message_id)
        except ApiTelegramException:
            pass

        sleep(1)
        CallBackAnswer("✅").answer(call_id)

    elif call_data.startswith("edit_event_date"):
        if call_data == "edit_event_date":
            event_date, event_id = (
                message_text[:10],
                message_text.split(".", maxsplit=4)[-2],
            )
            event_text = html.escape(message_text.split("\n", maxsplit=2)[2])
            event_status = str(
                message_text.split(" ", maxsplit=1)[0].split(".", maxsplit=4)[4]
            )

            # Error code: 400. Description: Bad Request: BUTTON_DATA_INVALID"
            # back = f"before del {event_date} {event_id} _"
            day = DayInfo(event_date)
            text = (
                get_translate("select.new_date")
                + f":\n<b>{event_date}.{event_id}.</b>{event_status}"
                + f"  <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})"
                + f"\n{event_text}"
            )

            dt_event_date = convert_date_format(event_date)
            markup = create_monthly_calendar_keyboard(
                (dt_event_date.year, dt_event_date.month),
                f"edit_event_date {event_id}",
                event_date,
            )
            NoEventMessage(text, markup).edit(chat_id, message_id)
        else:
            # Изменяем дату у события
            event_id, event_date = call_data.removeprefix("edit_event_date").split()
            api_response = user.edit_event_date(event_id, event_date)
            if api_response[0]:
                try:
                    update_message_action(message_id, event_date)
                except ApiTelegramException:
                    pass
                text = get_translate("changes_saved")
                CallBackAnswer(text).answer(call_id)
            elif api_response[1] == "Limit Exceeded":
                text = get_translate("errors.limit_exceeded")
                CallBackAnswer(text).answer(call_id)
            else:
                text = get_translate("errors.error")
                CallBackAnswer(text).answer(call_id)

    elif call_data.startswith("admin") and is_secure_chat(message):
        user_id = get_arguments(
            call_data.removeprefix("admin"), {"user_id": ("int", 1)}
        )["user_id"]
        generated = admin_message(user_id)
        generated.edit(chat_id, message_id)

    elif call_data == "groups":
        generated = group_message()
        generated.edit(chat_id, message_id)

    elif call_data == "account":
        generated = account_message()
        generated.edit(chat_id, message_id)

    elif call_data.startswith("user") and is_secure_chat(message):
        arguments = get_arguments(
            call_data.removeprefix("user"),
            {"user_id": "int", "action": "str", "key": "str", "val": "str"},
        )

        user_id = arguments["user_id"]
        action: str = arguments["action"]
        key: str = arguments["key"]
        val: str = arguments["val"]
        user = User(user_id)

        if user_id:
            if action:
                if action == "del":
                    if key == "account":
                        delete_user_chat_id = user.user_id  # TODO user.telegram.chat_id
                        api_response = user.delete_user(user_id)

                        if api_response[0]:
                            text = "Пользователь успешно удалён"
                            csv_file = api_response[1]
                        else:
                            error_text = api_response[1]

                            # TODO перевод
                            error_dict = {
                                "User Not Exist": "Пользователь не найден.",
                                "Not Enough Authority": "Недостаточно прав.",
                                "Unable To Remove Administrator": "Нельзя удалить администратора.\n"
                                "<code>/setuserstatus {user_id} 0</code>",
                                "CSV Error": "Не получилось получить csv файл.",
                            }
                            if error_text in error_dict:
                                return NoEventMessage(
                                    error_dict[error_text],
                                ).send(chat_id)

                            text = "Ошибка при удалении."
                            csv_file = api_response[1][1]
                        try:
                            bot.send_document(
                                delete_user_chat_id,
                                InputFile(csv_file),
                                caption="Ваш аккаунт удалён. Ваши события:",  # TODO перевод
                            )
                        except ApiTelegramException:
                            pass
                        else:
                            text += "\n+файл"

                        NoEventMessage(text).send(chat_id)

                    else:
                        default_button = {get_theme_emoji("back"): f"user {user_id}"}
                        markup = [
                            [
                                {"🗑": f"user {user_id} del account"}
                                if (r, c) == (3, 3)
                                else default_button
                                for c in range(5)
                            ]
                            for r in range(5)
                        ]
                        generated = NoEventMessage(
                            f"Вы точно хотите удалить аккаунт id: "
                            f"<a href='tg://user?id={user_id}'>{user_id}</a>?",
                            generate_buttons(markup),
                        )
                        try:
                            return generated.edit(chat_id, message_id)
                        except ApiTelegramException:
                            return
                elif action == "edit" and key and val:
                    if key == "settings.notifications":
                        api_response = user.set_settings(notifications=int(val))  # type: ignore
                        if not api_response[0]:
                            text = api_response[1]
                            return CallBackAnswer(text).answer(call_id)
                    elif key == "settings.status":
                        api_response = request.user.set_user_status(user_id, int(val))  # type: ignore
                        if not api_response[0]:
                            text = api_response[1]
                            return CallBackAnswer(text).answer(call_id)
                        set_bot_commands(user_id, int(val), user.settings.lang)

            generated = user_message(user_id)
            try:
                generated.edit(chat_id, message_id)
            except ApiTelegramException:
                pass

    elif call_data == "deleted":
        if is_premium_user(user):
            generated = trash_can_message()
            generated.edit(chat_id, message_id)

    elif call_data.startswith("bell"):
        date = get_arguments(call_data.removeprefix("bell"), {"date": "date"})["date"]

        if call_data == "bell":  # and is_premium_user(request.user):
            generated = monthly_calendar_message(
                "bell", "menu", "Выберите дату уведомления"
            )
            generated.edit(chat_id, message_id)
            return

        notifications_message(
            n_date=date,
            user_id_list=[chat_id],
            message_id=message_id,
            from_command=True,
        )

    elif call_data.startswith("week_event_list"):
        generated = week_event_list_message()
        generated.edit(chat_id, message_id)

    # elif call_data.startswith("limits"):
    #     date = get_arguments(
    #         call_data, {"date": ("date", "now")}
    #     )["date"]
    #     from telebot.formatting import hide_link  # noqa
    #     bot.send_message(chat_id, hide_link("https://srus.gay"))
    #     limits_message(date, message)


def reply_handler(message: Message, reply_to_message: Message) -> None:
    if reply_to_message.text.startswith("⚙️"):
        if request.user.set_settings(city=message.text[:50])[0]:
            delete_message_action(message)

        generated = settings_message()
        try:
            generated.edit(request.chat_id, reply_to_message.message_id)
        except ApiTelegramException:
            pass
    elif reply_to_message.text.startswith("😎") and is_secure_chat(message):
        arguments = get_arguments(
            message.text,
            {"user_id": "int", "action": ("str", "user_id")},
        )

        user_id = arguments["user_id"]
        action = arguments["action"]

        if user_id:
            if action == "page":
                generated = admin_message(user_id)
            elif action == "user_id":
                generated = user_message(user_id)
            else:
                return

            try:
                generated.edit(reply_to_message.chat.id, reply_to_message.message_id)
            except ApiTelegramException:
                pass
            else:
                delete_message_action(message)


def clear_state(chat_id: int | str):
    """
    Очищает состояние приёма сообщения у пользователя
    и изменяет сообщение по id из add_event_date
    """
    add_event_date = db.execute(queries["select add_event_date"], (chat_id,))[0][0]

    if add_event_date:
        msg_date, message_id = add_event_date.split(",")
        db.execute(queries["update add_event_date"], params=(0, chat_id), commit=True)
        update_message_action(message_id, msg_date)
