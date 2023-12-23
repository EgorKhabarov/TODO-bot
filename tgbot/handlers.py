import re
import html
import logging
import traceback
from time import sleep
from io import StringIO
from sqlite3 import Error
from ast import literal_eval

from telebot.apihelper import ApiTelegramException  # noqa
from telebot.types import Message, CallbackQuery, InputFile  # noqa

from tgbot import config
from tgbot.queries import queries
from tgbot.request import request
from tgbot.bot import bot, set_bot_commands
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.message_generator import TextMessage, CallBackAnswer
from tgbot.time_utils import now_time_strftime, now_time, new_time_calendar, DayInfo
from tgbot.bot_actions import delete_message_action
from tgbot.buttons_utils import (
    create_monthly_calendar_keyboard,
    delmarkup,
    create_yearly_calendar_keyboard,
    create_twenty_year_calendar_keyboard,
    decode_id,
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
    event_message,
    event_status_message,
    before_move_message,
    about_event_message,
    events_message,
)
from tgbot.utils import (
    fetch_weather,
    fetch_forecast,
    write_table_to_str,
    is_secure_chat,
    parse_message,
    html_to_markdown,
    add_status_effect,
)
from todoapi.api import User
from todoapi.types import db
from todoapi.log_cleaner import clear_logs
from todoapi.utils import is_admin_id, is_premium_user, is_valid_year
from telegram_utils.argument_parser import get_arguments
from telegram_utils.buttons_generator import generate_buttons
from telegram_utils.command_parser import parse_command, get_command_arguments


delimiter_regex = re.compile(r"[|!]")
re_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}")
re_call_data_date = re.compile(r"\A\d{1,2}\.\d{1,2}\.\d{4}\Z")


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
        menu_message().send(chat_id)

    elif command_text == "calendar":
        monthly_calendar_message().send(chat_id)

    elif command_text == "start":
        set_bot_commands()
        start_message().send(chat_id)

    elif command_text == "week_event_list":
        week_event_list_message().send(chat_id)

    elif command_text == "help":
        help_message().send(chat_id)

    elif command_text == "settings":
        settings_message().send(chat_id)

    elif command_text == "today":
        daily_message(now_time()).send(chat_id)

    elif command_text == "version":
        TextMessage(f"Version {config.__version__}").send(chat_id)

    elif command_text in ("weather", "forecast"):
        # Проверяем есть ли аргументы
        nowcity = get_command_arguments(
            message_text, {"city": ("long str", settings.city)}
        )["city"]

        func = fetch_weather if command_text == "weather" else fetch_forecast
        try:
            text = func(city=nowcity)
        except KeyError:
            text = get_translate(f"errors.{command_text}_invalid_city_name")

        if text:
            TextMessage(text, delmarkup()).send(chat_id)

    elif command_text == "search":
        raw_query = get_command_arguments(
            message.html_text,
            {"query": ("long str", "")},
        )["query"]
        query = html_to_markdown(raw_query)
        search_message(query).send(chat_id)

    elif command_text == "dice":
        value = bot.send_dice(chat_id).json["dice"]["value"]
        sleep(4)
        TextMessage(value).send(chat_id)

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
            TextMessage("Отправить файл не получилось").send(chat_id)

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
                TextMessage(f'Error "{e}"').reply(message)
            else:
                TextMessage("ok").reply(message)
            return

        bot.send_chat_action(chat_id, "upload_document")

        file = StringIO()
        file.name = "table.txt"

        try:
            write_table_to_str(file, query=query)
        except Error as e:
            TextMessage(f'[handlers.py -> "/SQL"] Error "{e}"').reply(message)
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
            return TextMessage(get_translate("errors.export_format")).reply(message)

        api_response = user.export_data(
            f"events_{now_time():%Y-%m-%d_%H-%M-%S}.{file_format}",
            f"{file_format}",
        )

        if api_response[0]:
            bot.send_chat_action(chat_id, "upload_document")

            try:
                bot.send_document(chat_id, InputFile(api_response[1]))
            except ApiTelegramException as e:
                logging.info(f'export ApiTelegramException "{e}"')
                TextMessage(get_translate("errors.file_is_too_big")).send(chat_id)
        else:
            if m := re.match(r"Wait (\d+) min", api_response[1]):
                generated = TextMessage(get_translate("errors.export").format(t=m[1]))
            else:
                generated = TextMessage(get_translate("errors.error"))
            generated.send(chat_id)

    elif command_text == "id":
        if message.reply_to_message:
            text = f"Message id <code>{message.reply_to_message.id}</code>"
        else:
            text = f"Chat id <code>{chat_id}</code>"
        TextMessage(text).reply(message)

    elif command_text == "limits":
        # TODO сделать проверку на user.status ?
        date = get_command_arguments(message_text, {"date": ("date", "now")})["date"]
        limits_message(date)

    elif command_text == "clear_logs":
        try:
            clear_logs()
        except BaseException as e:
            text = (
                f"<b>{e.__class__.__name__}:</b> <i>{e}</i>\n"
                f"<pre>{traceback.format_exc()}</pre>"
            )
        else:
            text = "Ok"

        TextMessage(text).reply(message)

    elif command_text == "commands":
        text, admin_commands = get_translate("text.command_list")

        if is_admin_id(chat_id):
            text += admin_commands

        TextMessage(text).send(chat_id)


def callback_handler(call: CallbackQuery):
    """
    Реакцию бота на нажатия на кнопки
    """

    message_id = call.message.message_id
    message_text = call.message.text
    call_data = call.data
    call_id = call.id
    message = call.message
    chat_id = request.chat_id

    if call_data == "menu":
        menu_message().edit(chat_id, message_id)

    elif call_data == "message_del":
        delete_message_action(message)

    elif call_data == "groups":
        group_message().edit(chat_id, message_id)

    elif call_data == "account":
        account_message().edit(chat_id, message_id)

    elif call_data == "week_event_list":
        week_event_list_message().edit(chat_id, message_id)

    elif call_data.startswith("about_event"):
        # event metadata
        event_id = get_arguments(
            call_data.removeprefix("about_event"),
            {"event_id": "int"},
        )["event_id"]
        about_event_message(event_id).edit(chat_id, message_id)

    elif call_data.startswith("event_add"):
        clear_state(chat_id)
        date = get_arguments(
            call_data.removeprefix("event_add"),
            {"date": "str"},
        )["date"]

        # Проверяем будет ли превышен лимит для пользователя, если добавить 1 событие с 1 символом
        if request.user.check_limit(date, event_count=1, symbol_count=1)[1] is True:
            text = get_translate("errors.exceeded_limit")
            CallBackAnswer(text).answer(call_id, True)
            return

        db.execute(
            queries["update add_event_date"],
            params=(f"{date},{message_id}", chat_id),
            commit=True,
        )

        send_event_text = get_translate("send_event_text")
        CallBackAnswer(send_event_text).answer(call_id)
        text = f"{message.html_text}\n\n<b>?.?.</b>⬜\n{send_event_text}"
        markup = generate_buttons([[{get_theme_emoji("back"): date}]])
        TextMessage(text, markup).edit(chat_id, message_id)

    elif call_data.startswith("confirm_change"):
        arguments = get_arguments(
            call_data.removeprefix("confirm_change"),
            {"event_id": "int", "date": "date"},
        )
        event_id, event_date = arguments["event_id"], arguments["date"]
        text = message_text.split("\n", maxsplit=2)[-1]

        if not request.user.edit_event_text(event_id, text)[0]:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
            return

        CallBackAnswer(get_translate("changes_saved")).answer(call_id)
        generated = event_message(event_id, False, message_id)
        # generated = daily_message(event_date)
        generated.edit(chat_id, message_id)

    elif call_data.startswith("select one"):
        arguments = get_arguments(
            call_data.removeprefix("select one"),
            {
                "action_type": ("str", message_text[:10]),
                "back_data": "str",
                "back_arg": ("str", ""),
            },
        )

        action_type, back_data, back_arg = (
            arguments["action_type"],
            arguments["back_data"],
            arguments["back_arg"],
        )
        in_wastebasket = action_type == "deleted"
        is_open = action_type == "open"
        events_list, different_dates = parse_message(message_text)

        # Если событий нет
        if len(events_list) == 0:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)
            return

        updated_events_list = request.user.get_events(
            [event.event_id for event in events_list],
            in_wastebasket,
        )[1]

        # Если событий нет
        if len(updated_events_list) == 0:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)
            return

        # Если событие одно
        if len(events_list) == 1:
            event = updated_events_list[0]
            if is_open:
                generated = daily_message(event.date)
            else:
                generated = event_message(event.event_id, in_wastebasket, message_id)
            return generated.edit(chat_id, message_id)

        # Если событий несколько
        markup = []
        events_dict = {event.event_id: event for event in updated_events_list}
        for event in events_list:
            event = events_dict.get(event.event_id)

            # Проверяем существование события
            if event is None:
                continue

            button_title = f"{event.event_id}.{event.status} {event.text}"
            button_title = button_title.ljust(60, "⠀")[:60]

            if in_wastebasket or different_dates:
                button_title = f"{event.date}.{button_title}"[:60]

            if is_open:
                button_data = event.date
            else:
                button_data = f"event {event.event_id} {int(in_wastebasket)}"

            markup.append([{button_title: button_data}])

        if is_open:
            text = get_translate("select.event_to_open")
            back_button_data = f"{back_data} {back_arg}".strip()
        else:
            text = get_translate("select.event")
            back_button_data = action_type

        markup.append([{get_theme_emoji("back"): back_button_data}])
        TextMessage(text, generate_buttons(markup)).edit(chat_id, message_id)

    elif call_data.startswith("select many"):
        arguments = get_arguments(
            call_data.removeprefix("select many"),
            {
                "action_type": ("str", message_text[:10]),
                "back_data": "str",
                "back_arg": ("str", ""),
            },
        )

        action_type, back_data, back_arg = (
            arguments["action_type"],
            arguments["back_data"],
            arguments["back_arg"],
        )
        in_wastebasket = action_type == "deleted"
        events_list, different_dates = parse_message(message_text)

        # Если событий нет
        if len(events_list) == 0:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)
            return

        # Если событие одно
        if len(events_list) == 1:
            event = events_list[0]
            if not request.user.check_event(event.event_id, in_wastebasket)[1]:
                call.data = message_text.split("\n", 1)[1][:10]  # TODO проверить
                return callback_handler(call)
            generated = events_message([str(event.event_id)], in_wastebasket)
            generated.edit(chat_id, message_id)
            return

        # Если событий несколько
        markup = []
        event_ids = []
        for n, event in enumerate(events_list):
            api_response = request.user.get_event(event.event_id, in_wastebasket)

            # Проверяем существование события
            if not api_response[0]:
                continue

            e = api_response[1]  # event
            event_ids.append(e.event_id)
            button_title = f"{e.event_id}.{e.status} {e.text}".ljust(60, "⠀")[:60]
            if in_wastebasket or different_dates:
                button_title = f"{e.date}.{button_title}"[:60]

            button_data = f"select {n} {0}"

            markup.append([{button_title: button_data}])

        if not markup:  # Созданный markup пустой
            call.data = message_text.split("\n", 1)[1][:10]
            return callback_handler(call)  # TODO проверить

        markup.append(
            [
                {get_theme_emoji("back"): action_type},
                {"☑️": "select all"},
                {"↗️": f"events {','.join(map(str, event_ids))} {int(in_wastebasket)}"},
            ]
        )
        generated = TextMessage(
            get_translate("select.events"), generate_buttons(markup)
        )
        generated.edit(chat_id, message_id)

    elif call_data.startswith("select all"):
        for line in message.reply_markup.keyboard[:-1]:
            for button in line:
                button.text = (
                    button.text.removeprefix("👉")
                    if button.text.startswith("👉")
                    else f"👉{button.text}"
                )
        generated = TextMessage(markup=message.reply_markup)
        generated.edit(chat_id, message_id, only_markup=True)

    elif call_data.startswith("select"):
        arguments = get_arguments(
            call_data.removeprefix("select"),
            {"row": "int", "column": "int"},
        )

        row, column = arguments["row"], arguments["column"]
        button = message.reply_markup.keyboard[row][column]
        button.text = (
            button.text.removeprefix("👉")
            if button.text.startswith("👉")
            else f"👉{button.text}"
        )
        generated = TextMessage(markup=message.reply_markup)
        generated.edit(chat_id, message_id, only_markup=True)

    elif call_data.startswith("events"):
        arguments = get_arguments(
            call_data.removeprefix("events"),
            {"event_ids": "str", "in_wastebasket": ("int", 0)},
        )
        event_ids, in_wastebasket = arguments["event_ids"], arguments["in_wastebasket"]
        ids = [
            i
            for n, i in enumerate(event_ids.split(","))
            if message.reply_markup.keyboard[n][0].text.startswith("👉")
        ]
        if ids:
            generated = events_message(ids, bool(in_wastebasket))
            if generated:
                try:
                    generated.edit(chat_id, message_id)
                except ApiTelegramException:
                    pass
        else:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)

    elif call_data.startswith("event"):
        arguments = get_arguments(
            call_data.removeprefix("event"),
            {"event_id": "int", "in_wastebasket": ("int", 0)},
        )
        event_id, in_wastebasket = arguments["event_id"], arguments["in_wastebasket"]
        if event_id:
            generated = event_message(event_id, bool(in_wastebasket), message_id)
            if generated:
                try:
                    generated.edit(chat_id, message_id)
                except ApiTelegramException:
                    CallBackAnswer("ok").answer(call_id, True)

    elif call_data.startswith("recover"):
        arguments = get_arguments(
            call_data.removeprefix("recover"),
            {"event_id": "int", "date": "str"},
        )
        event_id, event_date = arguments["event_id"], arguments["date"]

        if not request.user.recover_event(event_id)[0]:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
            return  # такого события нет

        trash_can_message().edit(chat_id, message_id)

    elif call_data.startswith("status page"):
        arguments = get_arguments(
            call_data.removeprefix("status page"),
            {"page": "str", "event_id": "int", "date": "date"},
        )
        page, event_id, date = (
            arguments["page"],
            arguments["event_id"],
            arguments["date"],
        )

        # Проверяем наличие события
        api_response = request.user.get_event(event_id)

        if not api_response[0]:  # Если этого события нет
            return daily_message(date).edit(chat_id, message_id)

        event = api_response[1]
        generated = event_status_message(event, page)
        generated.edit(chat_id, message_id)

    elif call_data.startswith("status set"):
        arguments = get_arguments(
            call_data.removeprefix("status set"),
            {"new_status": "str", "event_id": "int", "date": "date"},
        )
        new_status, event_id, date = (
            arguments["new_status"],
            arguments["event_id"],
            arguments["date"],
        )

        api_response = request.user.get_event(event_id)

        if not api_response[0]:
            return daily_message(date).edit(chat_id, message_id)

        event = api_response[1]
        old_status = event.status

        if new_status == "⬜️" == old_status:
            return event_status_message(event).edit(chat_id, message_id)

        if old_status == "⬜️":
            res_status = new_status

        elif new_status == "⬜️":
            res_status = "⬜️"

        else:
            res_status = f"{old_status},{new_status}"

        api_response = request.user.edit_event_status(event_id, res_status)

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
            event_message(event_id, False, message_id).edit(chat_id, message_id)
        else:
            event.status = res_status
            event_status_message(event).edit(chat_id, message_id)

    elif call_data.startswith("status delete"):
        arguments = get_arguments(
            call_data.removeprefix("status delete"),
            {"status": "str", "event_id": "int", "date": "date"},
        )
        status, event_id, date = (
            arguments["status"],
            arguments["event_id"],
            arguments["date"],
        )

        api_response = request.user.get_event(event_id)

        if not api_response[0]:
            return daily_message(date).edit(chat_id, message_id)

        event = api_response[1]
        old_status = event.status

        if status == "⬜️" or old_status == "⬜️":
            return

        statuses = old_status.split(",")
        statuses.remove(status)
        res_status = ",".join(statuses)

        if not res_status:
            res_status = "⬜️"

        request.user.edit_event_status(event_id, res_status)
        event.status = res_status
        generated = event_status_message(event)
        generated.edit(chat_id, message_id)

    elif call_data.startswith("|"):  # Список id событий на странице
        call_data = call_data.removeprefix("|")
        is_recurring = True if delimiter_regex.findall(call_data)[0] == "!" else False
        page, id_list = (lambda _page, _id_list: (int(_page), decode_id(_id_list)))(
            *delimiter_regex.split(call_data)
        )

        try:
            if message_text.startswith("🔍 "):  # Поиск
                first_line = message.text.split("\n", maxsplit=1)[0]
                query = html.escape(first_line.split(maxsplit=2)[-1][:-1])
                generated = search_message(query, id_list, page)

            elif message_text.startswith("📆"):  # Если /week_event_list
                generated = week_event_list_message(id_list, page)

            elif message_text.startswith("🗑"):  # Корзина
                generated = trash_can_message(id_list, page)

            elif m := re_date.match(message_text):
                func = recurring_events_message if is_recurring else daily_message
                generated = func(m[0], id_list, page)

            elif message_text.startswith("🔔"):  # Будильник
                return notifications_message(
                    user_id_list=[chat_id],
                    id_list=id_list,
                    page=page,
                    message_id=message_id,
                    markup=message.reply_markup,
                    from_command=True,
                )
            else:
                return

            generated.edit(chat_id, message_id, markup=message.reply_markup)

        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_data.startswith("calendar_t "):
        sleep(0.3)
        command, back, decade = literal_eval(call_data.removeprefix("calendar_t "))

        if decade == "now":
            decade = int(str(now_time().year)[:3])
        else:
            decade = int(decade)

        if is_valid_year(int(str(decade) + "0")):
            markup = create_twenty_year_calendar_keyboard(decade, command, back)
            try:
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
            except ApiTelegramException:
                # Сообщение не изменено
                year = now_time().year
                markup = create_yearly_calendar_keyboard(year, command, back)
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
        else:
            CallBackAnswer(get_translate("errors.invalid_date")).answer(call_id)

    elif call_data.startswith("calendar_y "):
        sleep(0.5)
        command, back, year = literal_eval(call_data.removeprefix("calendar_y "))

        if year == "now":
            year = now_time().year

        if is_valid_year(year):
            markup = create_yearly_calendar_keyboard(year, command, back)
            try:
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
            except ApiTelegramException:
                # Сообщение не изменено
                date = new_time_calendar()
                markup = create_monthly_calendar_keyboard(date, command, back)
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
        else:
            CallBackAnswer(get_translate("errors.invalid_date")).answer(call_id)

    elif call_data.startswith("calendar_m "):
        sleep(0.5)
        command, back, date = literal_eval(call_data.removeprefix("calendar_m "))

        if date == "now":
            date = new_time_calendar()

        if is_valid_year(date[0]):
            markup = create_monthly_calendar_keyboard(date, command, back)
            try:
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
            except ApiTelegramException:
                # Если нажата кнопка ⟳, но сообщение не изменено
                now_date = now_time()

                if command is not None and back is not None:
                    call.data = f"{command} {now_date:%d.%m.%Y}"
                    return callback_handler(call)

                generated = daily_message(now_date)
                generated.edit(chat_id, message_id)
        else:
            CallBackAnswer(get_translate("errors.invalid_date")).answer(call_id)

    elif call_data.startswith("calendar"):
        sleep(0.5)
        date = literal_eval(call_data.removeprefix("calendar "))[0]

        if date == "now":
            date = new_time_calendar()

        text = get_translate("select.date")
        markup = create_monthly_calendar_keyboard(date)
        TextMessage(text, markup).edit(chat_id, message_id)

    elif call_data.startswith("settings"):
        if call_data == "settings":
            try:
                settings_message().edit(chat_id, message_id)
            except ApiTelegramException:
                pass
            return

        arguments = get_arguments(
            call_data.removeprefix("settings"),
            {"par_name": "str", "par_val": "str"},
        )
        par_name, par_val = arguments["par_name"], arguments["par_val"]

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

        api_response = request.user.set_settings(**{par_name: par_val})
        if not api_response[0]:
            return CallBackAnswer(get_translate("errors.error")).answer(call_id)

        set_bot_commands()

        try:
            settings_message().edit(chat_id, message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("recurring"):
        date = get_arguments(
            call_data.removeprefix("recurring"),
            {"date": "str"},
        )["date"]
        recurring_events_message(date).edit(chat_id, message_id)

    elif call_data.startswith("update"):
        call_data = get_arguments(
            call_data.removeprefix("update"),
            {"data": "long str"},
        )["data"]

        if re_call_data_date.match(call_data):
            generated = daily_message(call_data)
        elif call_data == "search":
            first_line = message_text.split("\n", maxsplit=1)[0]
            raw_query = first_line.split(maxsplit=2)[-1][:-1]
            query = html.unescape(raw_query)
            generated = search_message(query)
        elif message_text.startswith("📆"):  # week_event_list
            generated = week_event_list_message()
        else:
            return

        sleep(0.5)

        try:
            generated.edit(chat_id, message_id)
        except ApiTelegramException:
            pass

        CallBackAnswer("ok").answer(call_id, True)

    elif re_call_data_date.search(call_data):
        sleep(0.3)
        date = get_arguments(call_data, {"date": "date"})["date"]
        if is_valid_year(date.year):
            daily_message(date).edit(chat_id, message_id)
        else:
            CallBackAnswer(get_translate("errors.invalid_date")).answer(call_id)

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
        if not request.user.clear_basket()[0]:
            return CallBackAnswer(get_translate("errors.error")).answer(call_id)

        try:
            trash_can_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_data == "restore_to_default":
        old_lang = request.user.settings.lang
        request.user.set_settings(
            lang="ru",
            sub_urls=1,
            city="Москва",
            timezone=3,
            direction="DESC",
            notifications=0,
            notifications_time="08:00",
            theme=0,
        )

        if old_lang != "ru":
            set_bot_commands()

        CallBackAnswer("ok").answer(call_id)

        try:
            settings_message().edit(chat_id, message_id)
        except ApiTelegramException:
            pass

    elif call_data.startswith("edit_event_date"):
        arguments = get_arguments(
            call_data.removeprefix("edit_event_date"),
            {"event_id": "int", "action": ("str", "back"), "date": "date"},
        )
        event_id, action, date = (
            arguments["event_id"],
            arguments["action"],
            arguments["date"],
        )
        if action == "back":
            api_response = request.user.get_event(event_id)
            if not api_response[0]:
                return daily_message(date).edit(chat_id, message_id)

            event = api_response[1]
            day = DayInfo(event.date)
            text = f"""
<b>{get_translate("select.new_date")}:
{event.date}.{event_id}.</b>{event.status}  <u><i>{day.str_date}  {day.week_date}</i></u> ({day.relatively_date})
{add_status_effect(event.text, event.status)}
"""

            markup = create_monthly_calendar_keyboard(
                (date.year, date.month),
                f"edit_event_date {event_id} move",
                f"event {event_id}",
            )
            TextMessage(text, markup).edit(chat_id, message_id)
        elif action == "move":
            # Изменяем дату у события
            api_response = request.user.edit_event_date(event_id, f"{date:%d.%m.%Y}")
            if api_response[0]:
                CallBackAnswer(get_translate("changes_saved")).answer(call_id)
                generated = event_message(event_id, False, message_id)
                # generated = daily_message(event_date)
                generated.edit(chat_id, message_id)
            elif api_response[1] == "Limit Exceeded":
                answer = CallBackAnswer(get_translate("errors.limit_exceeded"))
                answer.answer(call_id, True)
            else:
                CallBackAnswer(get_translate("errors.error")).answer(call_id)

    elif call_data.startswith("delete_event"):
        arguments = get_arguments(
            call_data.removeprefix("delete_event"),
            {
                "event_id": "int",
                "date": "date",
                "action": "str",
                "back": ("str", "daily"),
            },
        )
        event_id, date, action, back = (
            arguments["event_id"],
            arguments["date"],
            arguments["action"],
            arguments["back"],
        )
        if action == "before":
            return before_move_message(event_id).edit(chat_id, message_id)
        elif action == "forever":
            if not request.user.delete_event(event_id)[0]:
                CallBackAnswer(get_translate("errors.error")).answer(call_id)
        elif action == "wastebasket":
            if not request.user.delete_event(event_id, True)[0]:
                CallBackAnswer(get_translate("errors.error")).answer(call_id)
        else:
            return

        generated = trash_can_message() if back == "deleted" else daily_message(date)
        generated.edit(chat_id, message_id)

    elif call_data.startswith("admin") and is_secure_chat(message):
        user_id = get_arguments(
            call_data.removeprefix("admin"),
            {"user_id": ("int", 1)},
        )["user_id"]
        admin_message(user_id).edit(chat_id, message_id)

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
                                return TextMessage(error_dict[error_text]).send(chat_id)

                            text = "Ошибка при удалении."
                            csv_file = api_response[1][1]
                        try:
                            bot.send_document(
                                delete_user_chat_id,
                                InputFile(csv_file),
                                caption=get_translate("text.account_has_been_deleted"),
                            )
                        except ApiTelegramException:
                            pass
                        else:
                            text += "\n+файл"

                        TextMessage(text).send(chat_id)

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
                        generated = TextMessage(
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
        if is_premium_user(request.user):
            try:
                trash_can_message().edit(chat_id, message_id)
            except ApiTelegramException:
                CallBackAnswer("ok").answer(call_id, True)

    elif call_data.startswith("bell"):
        n_date = get_arguments(call_data.removeprefix("bell"), {"date": "date"})["date"]

        if call_data == "bell":  # and is_premium_user(request.user):
            generated = monthly_calendar_message(
                "bell", "menu", "Выберите дату уведомления"
            )
            generated.edit(chat_id, message_id)
            return

        notifications_message(
            n_date=n_date,
            user_id_list=[chat_id],
            message_id=message_id,
            from_command=True,
        )

    # elif call_data.startswith("limits"):
    #     date = get_arguments(
    #         call_data, {"date": ("date", "now")}
    #     )["date"]
    #     from telebot.formatting import hide_link  # noqa
    #     bot.send_message(chat_id, hide_link("https://example.com"))
    #     limits_message(date, message)


def reply_handler(message: Message, reply_to_message: Message) -> None:
    """
    Реакции на ответ на сообщение бота
    """

    if reply_to_message.text.startswith("⚙️"):
        if request.user.set_settings(city=html_to_markdown(message.html_text)[:50])[0]:
            try:
                settings_message().edit(request.chat_id, reply_to_message.message_id)
            except ApiTelegramException:
                return
            else:
                delete_message_action(message)

    elif reply_to_message.text.startswith("😎") and is_secure_chat(message):
        arguments = get_arguments(
            message.html_text,
            {"value": "int", "action": ("str", "user_id")},
        )

        value = arguments["value"]
        action = html_to_markdown(arguments["action"])

        if value:
            if action == "page":
                generated = admin_message(value)
            elif action == "user_id":
                generated = user_message(value)
            else:
                return

            try:
                generated.edit(reply_to_message.chat.id, reply_to_message.message_id)
            except ApiTelegramException:
                return
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
        try:
            daily_message(msg_date).edit(chat_id, message_id)
        except ApiTelegramException:
            pass
