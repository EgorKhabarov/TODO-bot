import re
import logging
import traceback
from time import sleep
from io import StringIO
from sqlite3 import Error
from ast import literal_eval

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery, InputFile

from config import DATABASE_PATH, __version__
from tgbot.bot import bot
from tgbot.request import request
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.message_generator import TextMessage, CallBackAnswer
from tgbot.time_utils import new_time_calendar
from tgbot.bot_actions import delete_message_action
from tgbot.buttons_utils import (
    create_monthly_calendar_keyboard,
    delmarkup,
    create_yearly_calendar_keyboard,
    create_twenty_year_calendar_keyboard,
    decode_id,
    edit_button_data,
    encode_id,
)
from tgbot.bot_messages import (
    menu_message,
    search_message,
    week_event_list_message,
    trash_can_message,
    daily_message,
    notification_message,
    recurring_events_message,
    settings_message,
    start_message,
    help_message,
    monthly_calendar_message,
    limits_message,
    admin_message,
    groups_message,
    account_message,
    user_message,
    event_message,
    event_status_message,
    before_event_delete_message,
    before_events_delete_message,
    about_event_message,
    events_message,
    edit_event_date_message,
    edit_events_date_message,
    select_one_message,
    select_events_message,
    event_show_mode_message, group_message,
)
from tgbot.types import TelegramAccount, set_user_telegram_chat_id, get_telegram_account_from_password
from tgbot.utils import (
    fetch_weather,
    fetch_forecast,
    write_table_to_str,
    is_secure_chat,
    html_to_markdown,
    extract_search_query, add_group_pattern, set_bot_commands
)
from todoapi.exceptions import ApiError, UserNotFound, EventNotFound, LimitExceeded, TextIsTooBig, WrongDate, \
    StatusConflict, StatusLengthExceeded, StatusRepeats, NotEnoughPermissions, NotGroupMember, GroupNotFound
from todoapi.types import db, create_user, get_account_from_password, Cache
from todoapi.log_cleaner import clear_logs
from telegram_utils.argument_parser import get_arguments, getargs
from telegram_utils.buttons_generator import generate_buttons
from telegram_utils.command_parser import parse_command, get_command_arguments
from todoapi.utils import is_admin_id, is_valid_year, re_email, re_username


def not_login_handler(x: CallbackQuery | Message) -> None:
    """
    /login <username> <password>
    /signup <email> <username> <password>
    """
    try:
        set_bot_commands(True)
    except ApiTelegramException:
        pass

    message = x if isinstance(x, Message) else x.message

    if message.text.startswith("/login"):
        if request.is_member:
            text = get_translate("errors.forbidden_to_log_account_in_group")
            return TextMessage(text).reply(message)

        arguments = get_command_arguments(
            message.text,
            {"username": "str", "password": "str"},
        )
        username, password = arguments["username"], arguments["password"]

        if not (username and password):
            TextMessage(get_translate("errors.no_account")).reply(message)
        elif not re_username.match(username):
            TextMessage("Wrong username").reply(message)
        else:
            try:
                account = get_account_from_password(username, password)
                set_user_telegram_chat_id(account, message.chat.id)
            except (ApiError, UserNotFound) as e:
                print(type(e), e)
                TextMessage(get_translate("errors.failure")).reply(message)
            else:
                TextMessage(get_translate("errors.success")).send(message.chat.id)
                bot.delete_message(message.chat.id, message.message_id)
                request.entity = get_telegram_account_from_password(username, password)
                start_message().send(message.chat.id)
                set_bot_commands()

    elif message.text.startswith("/signup"):
        if request.is_member:
            text = get_translate("errors.forbidden_to_log_account_in_group")
            return TextMessage(text).reply(message)

        arguments = get_command_arguments(
            message.text,
            {"email": "str", "username": "str", "password": "str"},
        )
        email, username, password = arguments["email"], arguments["username"], arguments["password"]

        if not (email and username and password):
            TextMessage(get_translate("errors.no_account")).reply(message)
        elif not re_email.match(email):
            TextMessage("Wrong email").reply(message)
        elif not re_username.match(username):
            TextMessage("Wrong username").reply(message)
        else:
            try:
                create_user(email, username, password)
            except ApiError as e:
                print(e)
                TextMessage(get_translate("errors.failure")).reply(message)
            else:
                try:
                    account = get_account_from_password(username, password)
                    set_user_telegram_chat_id(account, message.chat.id)
                except ApiError as e:
                    print(e)
                    TextMessage(get_translate("errors.failure")).reply(message)
                else:
                    TextMessage(get_translate("errors.success")).send(message.chat.id)
                    bot.delete_message(message.chat.id, message.message_id)
                    request.entity = get_telegram_account_from_password(username, password)
                    start_message().send(message.chat.id)
                    set_bot_commands()

    elif match := add_group_pattern.match(message.text):
        if request.is_user:
            TextMessage(get_translate("errors.error")).reply(message)
            return

        owner_id, group_id = match.group(1), match.group(2)
        try:
            account = TelegramAccount(x.from_user.id)
        except UserNotFound:
            return TextMessage(get_translate("errors.failure")).reply(message)

        if account.user_id != int(owner_id):
            return TextMessage(get_translate("errors.failure")).reply(message)

        try:
            account.set_group_telegram_chat_id(group_id, message.chat.id)
        except (NotEnoughPermissions, NotGroupMember):
            return TextMessage(get_translate("errors.failure")).reply(message)

        TextMessage(get_translate("errors.success")).reply(message)
        request.entity = account
        start_message().send(message.chat.id)
        set_bot_commands()

    else:
        if request.is_user:
            TextMessage(get_translate("errors.no_account")).reply(message)
        else:
            TextMessage(get_translate("errors.forbidden_to_log_group")).reply(message)


def command_handler(message: Message) -> None:
    """
    Отвечает за реакцию бота на команды
    Метод message.text.startswith("")
    используется и для групп (в них сообщение приходит в формате /command{bot.user.username})
    """
    chat_id, message_text = request.chat_id, message.text
    parsed_command = parse_command(message_text, {"arg": "long str"})
    # TODO Local variable `command_arguments` is assigned to but never used
    command_text, command_arguments = (
        parsed_command["command"],
        parsed_command["arguments"],
    )

    if command_text == "menu":
        menu_message().send(chat_id)

    elif command_text == "calendar":
        monthly_calendar_message(None, "dl", "mnm").send(chat_id)

    elif command_text == "start":
        if add_group_pattern.match(message.text):
            if request.is_member:
                TextMessage(get_translate("errors.already_connected_group")).reply(message)
                return

        set_bot_commands()
        start_message().send(chat_id)

    elif command_text == "week_event_list":
        week_event_list_message().send(chat_id)

    elif command_text == "help":
        help_message().send(chat_id)

    elif command_text == "settings":
        settings_message().send(chat_id)

    elif command_text == "today":
        daily_message(request.entity.now_time()).send(chat_id)

    elif command_text == "version":
        TextMessage(f"Version {__version__}").send(chat_id)

    elif command_text in ("weather", "forecast"):
        # Проверяем есть ли аргументы
        nowcity = get_command_arguments(
            message_text, {"city": ("long str", request.entity.settings.city)}
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
        value = bot.send_dice(
            chat_id, message_thread_id=request.query.message_thread_id or None
        ).json["dice"]["value"]
        sleep(4)
        TextMessage(value).send(chat_id)

    elif command_text == "sqlite" and is_secure_chat(message):
        bot.send_chat_action(chat_id, "upload_document")

        try:
            with open(DATABASE_PATH, "rb") as file:
                bot.send_document(
                    chat_id,
                    file,
                    caption=f"{request.entity.now_time():%d.%m.%Y}",
                )
        except ApiTelegramException:
            # TODO перевод
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

        response, file = request.entity.export_data(
            f"events_{request.entity.now_time():%Y-%m-%d_%H-%M-%S}.{file_format}",
            f"{file_format}",
        )

        if response:
            bot.send_chat_action(chat_id, "upload_document")

            try:
                bot.send_document(
                    chat_id,
                    InputFile(file),
                    message_thread_id=request.query.message_thread_id or None,
                )
            except ApiTelegramException as e:
                logging.info(f'export ApiTelegramException "{e}"')
                TextMessage(get_translate("errors.file_is_too_big")).send(chat_id)
        else:
            if m := re.match(r"Wait (\d+) min", file):
                generated = TextMessage(get_translate("errors.export").format(t=m[1]))
            else:
                generated = TextMessage(get_translate("errors.error"))
            generated.send(chat_id)

    elif command_text == "id":
        if message.reply_to_message:
            text = f"Message id <code>{message.reply_to_message.id}</code>"
        else:
            text = (
                f"User id <code>{request.entity.user_id}</code>\n"
                f"Chat id <code>{chat_id}</code>"
            )
        TextMessage(text).reply(message)

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

    elif command_text == "logout":
        if request.is_user:
            set_user_telegram_chat_id(request.entity, None)
            TextMessage(get_translate("errors.success", request.entity.settings.lang)).reply(message)

    elif command_text in ("login", "signup"):
        TextMessage(get_translate("errors.failure")).reply(message)


def callback_handler(call: CallbackQuery):
    """
    Реакцию бота на нажатия на кнопки

    "md   " {} "message delete"

    "st-d " {} "settings restore to default"
    "st-e " {"par_name": "str", "par_val": "str"} "settings set"

    "b-cl " {} "bin clear"
    "be-m " {"event_id": "int"} "event message bin"
    "be-d " {"event_id": "int"} "event delete bin"
    "be-r " {"event_id": "int", "date": "str"} "event recover bin"
    "bs-m " {"event_ids": "int"} "events message bin"
    "bs-d " {"event_ids": "int"} "events delete bin"
    "bs-r " {"event_ids": "int"} "events recover bin"

    "mn-m " {} "menu"
    "mn-ad" {"page": ("int", 1)} "admin message"
    "mn-au" {"user_id": "int", "action": "str", "key": "str", "val": "str"} "user message"
    "mn-s " {} "settings"
    "mn-gr" {} "group message"
    "mn-a " {} "account message"
    "mn-c " {"date": "literal_eval"} "calendar"
    "mn-h " {"path": ("long str", None)} "help"
    "mn-b " {} "bin"
    "mn-n " {"date": ("date", None)} "notification"

    "e-m  " {"event_id": "int"} "event message"
    "e-a  " {"date": "str"} "event add"
    "e-sp " {"event_id": "int", "date": "date", "page": "str"} "event status page"
    "e-sa " {"event_id": "int", "date": "date", "status": "str"} "event status add"
    "e-sr " {"event_id": "int", "date": "date", "status": "str"} "event status remove"
    "e-et " {"event_id": "int", "date": "date"} "event edit text (confirm_change)"
    "e-sd " {"event_id": "int", "date": "date"} "event select new date"
    "e-ds " {"event_id": "int", "date": "date"} "event new date set"
    "e-bd " {"event_id": "int", "date": "date"} "event before delete"
    "e-d  " {"event_id": "int", "date": "date"} "event delete"
    "e-db " {"event_id": "int", "date": "date"} "event delete to bin"
    "e-ab " {"event_id": "int"} "event about"

    "es-m " {"event_ids": "int"} "events message"
    "es-bd" {"event_ids": "int", "date": "date"} "events before delete"
    "es-d " {"event_ids": "int", "date": "date"} "events delete"
    "es-db" {"event_ids": "int", "date": "date"} "events delete to bin"

    "es-sd" {"event_ids": "int", "date": "date"} "events select new date"
    "es-ds" {"event_ids": "int", "date": "date"} "events new date set"

    "s-e  " {"event_ids": "int", "action_type": ("str", message.text[:10]), "back_data": "str", "back_arg": ("str", "")} "select event"
    "s-es " {"event_ids": "int", "action_type": ("str", message.text[:10]), "back_data": "str", "back_arg": ("str", "")} "select events"
    "s-al " {} "select all"
    "s-on " {"row": "int", "column": "int"} "select one"
    "sb-e " {"event_ids": "int", "action_type": ("str", message.text[:10])} "select event in bin"
    "sb-es" {"event_ids": "int", "action_type": ("str", message.text[:10])} "select events in bin"
    "sb-al" {} "select all in bin"
    "sb-on" {"row": "int", "column": "int"} "select one in bin"

    "p-d  " {"id_list": "str", "page": "str", "date": "date"} "page daily"
    "p-r  " {"id_list": "str", "page": "str", "date": "date"} "page recurring"
    "p-s  " {"id_list": "str", "page": "str"} "page search"
    "p-w  " {"id_list": "str", "page": "str"} "page week event list"
    "p-b  " {"id_list": "str", "page": "str"} "page bin"
    "p-n  " {"id_list": "str", "page": "str"} "page notification"

    "c-m  " {"year,month": "literal_eval", "command": "str", "back": "str"} "calendar month"
    "c-y  " {"year": "int", "command": "str", "back": "str"} "calendar year"
    "c-t  " {"decade": "int", "command": "str", "back": "str"} "calendar twenty year"

    "u-d  " {"date": "date"} "update daily"
    "u-s  " {} "update search"
    "u-w  " {} "update week event list"
    "u-b  " {} "update bin"
    """

    message_id = call.message.message_id
    call_id = call.id
    message = call.message
    chat_id = request.chat_id

    call_prefix = call.data.strip().split(maxsplit=1)[0]
    call_data = call.data.removeprefix(call_prefix).strip()
    args_func = getargs(get_arguments, call_data)

    if call_prefix == "mnm":  # menu
        menu_message().edit(chat_id, message_id)

    elif call_prefix == "mnad" and is_secure_chat(message):  # admin
        page = args_func({"page": ("int", 1)})["page"]
        admin_message(page).edit(chat_id, message_id)

    elif call_prefix == "mnau" and is_secure_chat(message):  # user message
        arguments = args_func(
            {"chat_id": "int", "action": "str", "key": "str", "val": "str"}
        )
        chat_id = arguments["chat_id"]
        # action: str = arguments["action"]
        # key: str = arguments["key"]
        # val: str = arguments["val"]
        # user = get_user_from_chat_id(chat_id)

        if chat_id:
            # TODO переделать
            # if action:
            #     if action == "del":
            #         if key in ("account", "quiet"):
            #             delete_user_chat_id = user.user_id  # TODO user.telegram.chat_id
            #             response, result = user.delete_user(user_id)
            #
            #             if response:
            #                 # TODO перевод
            #                 text = "Пользователь успешно удалён"
            #                 csv_file = result
            #             else:
            #                 # TODO перевод
            #                 error_dict = {
            #                     "User Not Exist": "Пользователь не найден.",
            #                     "Not Enough Authority": "Недостаточно прав.",
            #                     "Unable To Remove Administrator": (
            #                         "Нельзя удалить администратора.\n"
            #                         "<code>/setuserstatus {user_id} 0</code>"
            #                     ),
            #                     "CSV Error": "Не получилось получить csv файл.",
            #                 }
            #                 if result in error_dict:
            #                     return TextMessage(error_dict[result]).send(chat_id)
            #
            #                 text = "Ошибка при удалении."  # TODO перевод
            #                 csv_file = result[1]
            #             try:
            #                 bot.send_document(
            #                     chat_id if key == "quiet" else delete_user_chat_id,
            #                     InputFile(csv_file),
            #                     caption=get_translate("text.account_has_been_deleted"),
            #                 )
            #             except ApiTelegramException:
            #                 pass
            #             else:
            #                 text += "\n+файл"  # TODO перевод
            #
            #             TextMessage(text).send(chat_id)
            #
            #         else:
            #             markup = [
            #                 [
            #                     {get_theme_emoji("back"): f"mnau {user_id}"},
            #                     {"🗑": f"mnau {user_id} del account"},
            #                     {"🤫🗑": f"mnau {user_id} del quiet"},
            #                 ]
            #             ]
            #             # TODO перевод
            #             generated = TextMessage(
            #                 f"Вы точно хотите удалить аккаунт id: "
            #                 f"<a href='tg://user?id={user_id}'>{user_id}</a>?",
            #                 generate_buttons(markup),
            #             )
            #             try:
            #                 return generated.edit(chat_id, message_id)
            #             except ApiTelegramException:
            #                 return
            #     elif action == "edit" and key and val:
            #         if key == "settings.notifications":
            #             response, error_text = user.set_settings(
            #                 notifications=bool(int(val))
            #             )
            #             if not response:
            #                 return CallBackAnswer(error_text).answer(call_id)
            #         elif key == "settings.status":
            #             response, error_text = request.entity.set_user_status(
            #                 user_id, int(val)
            #             )
            #             if not response:
            #                 return CallBackAnswer(error_text).answer(call_id)
            #             set_bot_commands(user_id, int(val), user.settings.lang)

            generated = user_message(chat_id)
            try:
                generated.edit(chat_id, message_id)
            except ApiTelegramException:
                CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "mns":  # settings
        try:
            settings_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "mnw":  # week_event_list
        try:
            week_event_list_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "mngrs":  # groups message
        arguments = args_func({"mode": ("str", "al"), "page": ("int", 1)})
        mode, page = arguments["mode"], arguments["page"]
        groups_message(mode, page).edit(chat_id, message_id)
        cache_create_group("")

    elif call_prefix == "mngr":  # group message
        group_id = args_func({"group_id": "str"})["group_id"]
        group_message(group_id, message_id=message_id).edit(chat_id, message_id)

    elif call_prefix == "mna":  # account message
        account_message().edit(chat_id, message_id)

    elif call_prefix == "mnc":  # calendar
        sleep(0.5)
        date = literal_eval(call_data)[0]
        date = new_time_calendar() if date == "now" else date
        text = get_translate("select.date")
        monthly_calendar_message(date, "dl", "mnm", text).edit(chat_id, message_id)

    elif call_prefix == "mnh":  # help
        page = args_func({"page": ("long str", "page 1")})["page"]
        markup = None if page.startswith("page") else message.reply_markup

        try:
            help_message(page).edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_prefix == "mnb" and ((request.is_user and request.entity.is_premium) or (request.is_member and ...)):  # bin
        try:
            trash_can_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "mnn":  # notification
        n_date = args_func({"date": "date"})["date"]

        if n_date is None:
            return monthly_calendar_message(
                None, "mnn", "mnm", get_translate("select.notification_date")
            ).edit(chat_id, message_id)
        try:
            notification_message(n_date, from_command=True).edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "dl":
        cache_add_event_date("")
        date = args_func({"date": "date"})["date"]
        try:
            daily_message(date).edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "em":  # event message
        event_id = args_func({"event_id": "int"})["event_id"]
        generated = event_message(event_id, message_id=message_id)
        if generated:
            try:
                generated.edit(chat_id, message_id)
            except ApiTelegramException:
                CallBackAnswer("ok").answer(call_id, True)
        else:
            text = get_translate("errors.no_events_to_interact")
            CallBackAnswer(text).answer(call_id, True)

    elif call_prefix == "ea":  # event add
        cache_add_event_date("")
        date = args_func({"date": "str"})["date"]

        # Проверяем будет ли превышен лимит для пользователя, если добавить 1 событие с 1 символом
        if request.entity.limit.is_exceeded_for_events(date=date, event_count=1, symbol_count=1):
            text = get_translate("errors.exceeded_limit")
            CallBackAnswer(text).answer(call_id, True)
            return

        cache_add_event_date(f"{date},{message_id}")

        send_event_text = get_translate("text.send_event_text")
        CallBackAnswer(send_event_text).answer(call_id)
        text = f"{message.html_text}\n\n<b>?.?.</b>⬜\n{send_event_text}"
        markup = generate_buttons([[{get_theme_emoji("back"): f"dl {date}"}]])
        TextMessage(text, markup).edit(chat_id, message_id)

    elif call_prefix == "esp":  # event status page
        page, date, event_id = args_func(
            {"page": "str", "date": "date", "event_id": "int"}
        ).values()
        try:
            event = request.entity.get_event(event_id)
        except EventNotFound:
            generated = daily_message(date)
        else:
            generated = event_status_message(event, page)

        generated.edit(chat_id, message_id)

    elif call_prefix == "esa":  # event status add
        status, date, event_id = args_func(
            {"status": "str", "date": "date", "event_id": "int"}
        ).values()
        try:
            event = request.entity.get_event(event_id)
        except EventNotFound:
            return daily_message(date).edit(chat_id, message_id)

        if status == "⬜️" == event.status:
            return event_status_message(event).edit(chat_id, message_id)

        if event.status == "⬜️":
            res_status = status
        elif status == "⬜️":
            res_status = "⬜️"
        else:
            res_status = f"{event.status},{status}"

        try:
            request.entity.edit_event_status(event_id, res_status)
        except StatusConflict:
            text = get_translate("errors.conflict_statuses")
        except StatusLengthExceeded:
            text = get_translate("errors.more_5_statuses")
        except StatusRepeats:
            text = get_translate("errors.status_already_posted")
        except ApiError:
            text = get_translate("errors.error")
        else:
            if status == "⬜️":
                generated = event_message(event_id, False, message_id)
            else:
                event.status = res_status
                generated = event_status_message(event)
            generated.edit(chat_id, message_id)
            return

        CallBackAnswer(text).answer(call_id, True)

    elif call_prefix == "esr":  # event status remove
        status, date, event_id = args_func(
            {"status": "str", "date": "date", "event_id": "int"}
        ).values()
        try:
            event = request.entity.get_event(event_id)
        except EventNotFound:
            return daily_message(date).edit(chat_id, message_id)

        if status == "⬜️" or event.status == "⬜️":
            return

        statuses = event.status.split(",")
        try:
            statuses.remove(status)
        except ValueError:  # Если попытаться удалить статус который уже не стоит
            pass
        res_status = ",".join(statuses)

        if not res_status:
            res_status = "⬜️"

        request.entity.edit_event_status(event_id, res_status)
        event.status = res_status
        event_status_message(event).edit(chat_id, message_id)

    elif call_prefix == "eet":  # event edit text
        event_id, event_date = args_func({"event_id": "int", "date": "date"}).values()
        text = message.text.split("\n", maxsplit=2)[-1]
        try:
            request.entity.edit_event_text(event_id, text)
        except TextIsTooBig:
            text = get_translate("errors.message_is_too_long")
        except LimitExceeded:
            text = get_translate("errors.limit_exceeded")
        except ApiError:
            text = get_translate("errors.error")
        else:
            CallBackAnswer(get_translate("text.changes_saved")).answer(call_id)
            generated = event_message(event_id, False, message_id)
            # generated = daily_message(event_date)
            generated.edit(chat_id, message_id)
            return
        return CallBackAnswer(text).answer(call_id, True)

    elif call_prefix == "esdt":  # event select new date
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()
        generated = edit_event_date_message(event_id, date)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    elif call_prefix == "eds":  # event new date set
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()
        try:
            request.entity.edit_event_date(event_id, f"{date:%d.%m.%Y}")
        except (ApiError, WrongDate):
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
        except LimitExceeded:
            CallBackAnswer(get_translate("errors.limit_exceeded")).answer(call_id, True)
        else:
            CallBackAnswer(get_translate("text.changes_saved")).answer(call_id)
            generated = event_message(event_id, False, message_id)
            generated.edit(chat_id, message_id)
            # generated = daily_message(event_date)

    elif call_prefix == "ebd":  # event before delete
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()
        generated = before_event_delete_message(event_id)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    elif call_prefix == "ed":  # event delete
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()
        try:
            request.entity.delete_event(event_id)
        except EventNotFound:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)

        daily_message(date).edit(chat_id, message_id)

    elif call_prefix == "edb":  # event delete to bin
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()
        try:
            request.entity.delete_event_to_bin(event_id)
        except NotEnoughPermissions:
            # TODO перевод
            CallBackAnswer("Недостаточно полномочий").answer(call_id)
        except EventNotFound:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)

        daily_message(date).edit(chat_id, message_id)

    elif call_prefix == "eab":  # event about
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()
        generated = about_event_message(event_id)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    elif call_prefix == "esh":  # event show
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()
        generated = event_show_mode_message(event_id)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    elif call_prefix == "esm":  # events message
        id_list = args_func({"id_list": "str"})["id_list"]
        if id_list == "_":
            id_list = encode_id(
                [
                    int(i[0].callback_data.rsplit(maxsplit=1)[-1])
                    for n, i in enumerate(message.reply_markup.keyboard)
                    if i[0].text.startswith("👉")
                ]
            )
        if id_list == "_":
            text = get_translate("errors.no_events_to_interact")
            return CallBackAnswer(text).answer(call_id, True)

        generated = events_message(decode_id(id_list))
        if generated:
            generated.edit(chat_id, message_id)
        else:
            text = get_translate("errors.no_events_to_interact")
            CallBackAnswer(text).answer(call_id, True)

    elif call_prefix == "esbd":  # events before delete
        id_list = args_func({"id_list": "str"})["id_list"]
        before_events_delete_message(decode_id(id_list)).edit(chat_id, message_id)

    elif call_prefix == "esd":  # events delete
        id_list, date = args_func({"id_list": "str", "date": "date"}).values()
        not_deleted: list[int] = []
        for event_id in decode_id(id_list):
            try:
                request.entity.delete_event(event_id)
            except EventNotFound:
                not_deleted.append(event_id)

        if not_deleted:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
            return events_message(not_deleted).edit(chat_id, message_id)

        # events_message([]).edit(chat_id, message_id)
        daily_message(date).edit(chat_id, message_id)

    elif call_prefix == "esdb":  # events delete to bin
        id_list, date = args_func({"id_list": "str", "date": "date"}).values()
        not_deleted: list[int] = []
        for event_id in decode_id(id_list):
            try:
                request.entity.delete_event_to_bin(event_id)
            except EventNotFound:
                not_deleted.append(event_id)

        if not_deleted:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
            # events_message(not_deleted).edit(chat_id, message_id)
            return before_events_delete_message(not_deleted)

        # events_message([]).edit(chat_id, message_id)
        daily_message(date).edit(chat_id, message_id)

    elif call_prefix == "essd":  # events select new date
        id_list = args_func({"id_list": "str"})["id_list"]
        edit_events_date_message(decode_id(id_list)).edit(chat_id, message_id)

    elif call_prefix == "esds":  # events new date set
        id_list, date = args_func({"id_list": "str", "date": "date"}).values()
        id_list = decode_id(id_list)
        not_edit: list[int] = []
        for event_id in id_list:
            try:
                request.entity.edit_event_date(event_id, f"{date:%d.%m.%Y}")
            except (WrongDate, EventNotFound, LimitExceeded, ApiError):
                not_edit.append(event_id)

        if not_edit:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
        else:
            CallBackAnswer(get_translate("text.changes_saved")).answer(call_id)

        events_message(id_list).edit(chat_id, message_id)

    elif call_prefix == "se":  # select event
        info, id_list = args_func({"info": "str", "id_list": "str"}).values()
        back_data = call_data.removeprefix(f"{info} {id_list}").strip()
        # TODO Добавить если поставить кавычки " или ', то можно внутри юзать пробел
        generated = select_one_message(
            decode_id(id_list),
            back_data,
            is_in_wastebasket="b" in info,
            is_in_search="s" in info,
            is_open="o" in info,
            message_id=message_id,
        )
        if generated:
            if "s" in info:
                query = extract_search_query(message.text)
                srch = get_translate("messages.search")
                generated.text = f"🔍 {srch} <u>{query}</u>:\n{generated.text}"
            generated.edit(chat_id, message_id)
        else:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)

    elif call_prefix == "ses":  # select events
        info, id_list = args_func({"info": "str", "id_list": "str"}).values()
        back_data = call_data.removeprefix(f"{info} {id_list}").strip()
        generated = select_events_message(
            decode_id(id_list),
            back_data,
            in_bin="b" in info,
            is_in_search="s" in info,
        )
        if generated:
            if "s" in info:
                query = extract_search_query(message.text)
                srch = get_translate("messages.search")
                generated.text = f"🔍 {srch} <u>{query}</u>:\n{generated.text}"
            generated.edit(chat_id, message_id)
        else:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)

    elif call_prefix in ("sal", "sbal"):  # select all | select all in bin
        for line in message.reply_markup.keyboard[:-1]:
            for button in line:
                button.text = (
                    button.text.removeprefix("👉")
                    if button.text.startswith("👉")
                    else f"👉{button.text}"
                )
        generated = TextMessage(markup=message.reply_markup)
        generated.edit(chat_id, message_id, only_markup=True)

    elif call_prefix in ("son", "sbon"):  # select one | select one in bin
        row, column = args_func({"row": "int", "column": ("int", 0)}).values()
        button = message.reply_markup.keyboard[row][column]
        button.text = (
            button.text.removeprefix("👉")
            if button.text.startswith("👉")
            else f"👉{button.text}"
        )
        generated = TextMessage(markup=message.reply_markup)
        generated.edit(chat_id, message_id, only_markup=True)

    elif call_prefix == "pd":  # page daily
        date, page, id_list = args_func(
            {"date": "str", "page": ("int", 0), "id_list": ("str", "")}
        ).values()
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, 1, f"se _ {id_list} pd {date}")
            edit_button_data(markup, 0, 2, f"ses _ {id_list} pd {date}")
        try:
            daily_message(date, decode_id(id_list), page).edit(
                chat_id, message_id, markup=markup
            )
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_prefix == "pr":  # page recurring
        date, page, id_list = args_func(
            {"date": "str", "page": ("str", 0), "id_list": ("str", "")}
        ).values()
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, -1, f"se o {id_list} pr {date}")
        try:
            recurring_events_message(date, decode_id(id_list), page).edit(
                chat_id, message_id, markup=markup
            )
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_prefix == "ps":  # page search
        page, id_list = args_func({"page": ("str", 0), "id_list": ("str", "")}).values()
        query = extract_search_query(message.text)
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, 2, f"se os {id_list} us")
            edit_button_data(markup, 0, 3, f"ses s {id_list} us")
        try:
            search_message(query, decode_id(id_list), page).edit(
                chat_id, message_id, markup=markup
            )
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_prefix == "pw":  # page week event list
        page, id_list = args_func({"page": ("str", 0), "id_list": ("str", ())}).values()
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, 2, f"se o {id_list} mnw")
        try:
            week_event_list_message(decode_id(id_list), page).edit(
                chat_id, message_id, markup=markup
            )
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_prefix == "pb":  # page bin
        page, id_list = args_func({"page": ("str", 0), "id_list": ("str", ())}).values()
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, 0, f"se b {id_list} mnb")
            edit_button_data(markup, 0, 1, f"ses b {id_list} mnb")
        try:
            trash_can_message(decode_id(id_list), page).edit(
                chat_id, message_id, markup=markup
            )
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_prefix == "pn":  # page notification
        n_date, page, id_list = args_func(
            {"date": "date", "page": ("str", 0), "id_list": ("str", ())}
        ).values()
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, -1, f"se o {id_list} mnn {n_date:%d.%m.%Y}")
        try:
            generated = notification_message(n_date, decode_id(id_list), page, True)
            generated.edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    elif call_prefix == "cm":  # calendar month
        sleep(0.5)
        command, back, date, arguments = literal_eval(call_data)

        if date == "now":
            date = new_time_calendar()

        if is_valid_year(date[0]):
            markup = create_monthly_calendar_keyboard(date, command, back, arguments)
            try:
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
            except ApiTelegramException:
                # Если нажата кнопка ⟳, но сообщение не изменено
                now_date = request.entity.now_time()

                if command is not None and back is not None:
                    call.data = f"{command}{f' {arguments}' if arguments else ''} {now_date:%d.%m.%Y}"
                    return callback_handler(call)

                daily_message(now_date).edit(chat_id, message_id)
        else:
            CallBackAnswer(get_translate("errors.invalid_date")).answer(call_id)

    elif call_prefix == "cy":  # calendar year
        sleep(0.5)
        command, back, year, arguments = literal_eval(call_data)

        if year == "now":
            year = request.entity.now_time().year

        if is_valid_year(year):
            markup = create_yearly_calendar_keyboard(year, command, back, arguments)
            try:
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
            except ApiTelegramException:
                # Сообщение не изменено
                date = new_time_calendar()
                markup = create_monthly_calendar_keyboard(
                    date, command, back, arguments
                )
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
        else:
            CallBackAnswer(get_translate("errors.invalid_date")).answer(call_id)

    elif call_prefix == "ct":  # calendar twenty year
        sleep(0.3)
        command, back, decade, arguments = literal_eval(call_data)

        if decade == "now":
            decade = int(str(request.entity.now_time().year)[:3])
        else:
            decade = int(decade)

        if is_valid_year(int(str(decade) + "0")):
            markup = create_twenty_year_calendar_keyboard(
                decade, command, back, arguments
            )
            try:
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
            except ApiTelegramException:
                # Сообщение не изменено
                year = request.entity.now_time().year
                markup = create_yearly_calendar_keyboard(year, command, back, arguments)
                TextMessage(markup=markup).edit(chat_id, message_id, only_markup=True)
        else:
            CallBackAnswer(get_translate("errors.invalid_date")).answer(call_id)

    elif call_prefix == "us":  # update search
        query = extract_search_query(message.text)
        try:
            search_message(query).edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "md":  # message delete
        delete_message_action(message)

    elif call_prefix == "std":  # settings restore to default
        old_lang = request.entity.settings.lang
        request.entity.set_telegram_user_settings(
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

    elif call_prefix == "ste":  # settings set
        par_name, par_val = args_func({"par_name": "str", "par_val": "str"}).values()

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

        try:
            request.entity.set_telegram_user_settings(**{par_name: par_val})
        except ValueError:
            return CallBackAnswer(get_translate("errors.error")).answer(call_id)

        try:
            set_bot_commands()
            settings_message().edit(chat_id, message_id)
        except ApiTelegramException:
            pass

    elif call_prefix == "bcl":  # bin clear
        request.entity.clear_basket()

        try:
            trash_can_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    elif call_prefix == "bem":  # event message bin
        event_id = args_func({"event_id": "int"})["event_id"]
        generated = event_message(event_id, True, message_id=message_id)
        if generated:
            try:
                generated.edit(chat_id, message_id)
            except ApiTelegramException:
                CallBackAnswer("ok").answer(call_id, True)
        else:
            text = get_translate("errors.no_events_to_interact")
            CallBackAnswer(text).answer(call_id, True)

    elif call_prefix == "bed":  # event delete bin
        event_id = args_func({"event_id": "int"})["event_id"]
        try:
            request.entity.delete_event(event_id, in_bin=True)
        except EventNotFound:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
        try:
            trash_can_message().edit(chat_id, message_id)
        except ApiTelegramException:
            pass

    elif call_prefix == "ber":  # event recover bin
        event_id, date = args_func({"event_id": "int", "date": "date"}).values()

        try:
            request.entity.recover_event(event_id)
        except (EventNotFound, LimitExceeded):
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
            return  # такого события нет

        # daily_message(date).edit(chat_id, message_id)
        trash_can_message().edit(chat_id, message_id)

    elif call_prefix == "bsm":  # events message bin
        id_list = args_func({"id_list": "str"})["id_list"]
        if id_list == "_" or not id_list:
            id_list = encode_id(
                [
                    int(i[0].callback_data.rsplit(maxsplit=1)[-1])
                    for n, i in enumerate(message.reply_markup.keyboard)
                    if i[0].text.startswith("👉")
                ]
            )
        if id_list == "_":
            text = get_translate("errors.no_events_to_interact")
            return CallBackAnswer(text).answer(call_id, True)

        generated = events_message(decode_id(id_list), True)
        if generated:
            generated.edit(chat_id, message_id)
        else:
            text = get_translate("errors.no_events_to_interact")
            CallBackAnswer(text).answer(call_id, True)

    elif call_prefix == "bsd":  # events delete bin
        id_list = args_func({"id_list": "str"})["id_list"]
        not_deleted: list[int] = []
        for event_id in decode_id(id_list):
            try:
                request.entity.delete_event(event_id, in_bin=True)
            except EventNotFound:
                not_deleted.append(event_id)

        if not_deleted:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)

        trash_can_message().edit(chat_id, message_id)

    elif call_prefix == "bsr":  # events recover bin
        id_list, date = args_func({"id_list": "str", "date": "date"}).values()
        not_recover: list[int] = []
        for event_id in decode_id(id_list):
            try:
                request.entity.recover_event(event_id)
            except (LimitExceeded, ApiError):
                not_recover.append(event_id)

        if not_recover:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)

        # daily_message(date).edit(chat_id, message_id)
        trash_can_message().edit(chat_id, message_id)

    elif call_prefix == "logout":
        if request.is_user:
            set_user_telegram_chat_id(request.entity, None)
            set_bot_commands(True)
            TextMessage(get_translate("errors.success")).edit(chat_id, message_id)

    elif call_prefix == "lm":  # limits message
        date = args_func({"date": "date"})["date"]
        if not date:
            generated = monthly_calendar_message(
                None, "lm", "mna", get_translate("select.date")
            )
            return generated.edit(chat_id, message_id)
        limits_message(date).edit(chat_id, message_id, disable_web_page_preview=False)

    elif call_prefix == "grcr":
        cache_create_group("")
        if request.entity.limit.is_exceeded_for_groups(create=True):
            return CallBackAnswer(get_translate("errors.limit_exceeded")).answer(call_id)

        cache_create_group(str(message_id))
        text = """
👥 Группы 👥

Отправьте имя группы
"""
        markup = generate_buttons(
            [
                [{get_theme_emoji("back"): "mngrs"}]
            ]
        )
        TextMessage(text, markup).edit(chat_id, message_id)
        CallBackAnswer(get_translate("text.send_group_name")).answer(call_id)

    elif call_prefix == "grd":  # group delete
        group_id = args_func({"group_id": "str"})["group_id"]
        try:
            request.entity.delete_group(group_id)
        except (NotGroupMember, NotEnoughPermissions):
            CallBackAnswer(get_translate("errors.error")).answer(call_id, show_alert=True)
        else:
            groups_message().edit(chat_id, message_id)

    elif call_prefix == "grlv":  # group leave
        group_id = args_func({"group_id": "str"})["group_id"]
        try:
            request.entity.remove_group_member(request.entity.user_id, group_id)
        except NotGroupMember:
            return CallBackAnswer(get_translate("errors.error")).answer(call_id)

        groups_message().edit(chat_id, message_id)

    elif call_prefix == "grrgr":  # group remove from telegram group
        group_id = args_func({"group_id": "str"})["group_id"]
        try:
            request.entity.set_group_telegram_chat_id(group_id)
        except (NotGroupMember, NotEnoughPermissions):
            CallBackAnswer(get_translate("errors.error")).answer(call_id, show_alert=True)
        else:
            group_message(group_id, message_id=message_id).edit(chat_id, message_id)



def reply_handler(message: Message, reply_to_message: Message) -> None:
    """
    Реакции на ответ на сообщение бота
    """

    if reply_to_message.text.startswith("⚙️"):
        try:
            request.entity.set_telegram_user_settings(city=html_to_markdown(message.html_text)[:50])
        except ValueError:
            TextMessage(get_translate("errors.error")).reply(message)
        else:
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


def cache_add_event_date(state: str = None) -> str | bool:
    """
    Очищает состояние приёма сообщения у пользователя
    и изменяет сообщение по id из add_event_date

    if state - поставить
    if state is None - получить
    if state == "" - очистить
    """
    table = "add_event"

    if state:
        Cache(table)[request.entity.request_chat_id] = state
        return True

    data = Cache(table)[request.entity.request_chat_id]

    if state is None:
        return data

    if data:
        msg_date, message_id = data.split(",")
        del Cache(table)[request.entity.request_chat_id]
        try:
            daily_message(msg_date).edit(request.entity.request_chat_id, message_id)
        except ApiTelegramException:
            pass


def cache_create_group(state: str = None) -> str | bool:
    """
    Очищает состояние приёма сообщения у пользователя
    и изменяет сообщение по id из add_event_date

    if state - поставить
    if state is None - получить
    if state == "" - очистить
    """
    table = "add_group"

    if state:
        Cache(table)[request.entity.request_chat_id] = state
        return True

    data = Cache(table)[request.entity.request_chat_id]

    if state is None:
        return data

    if data:
        message_id = int(data)
        del Cache(table)[request.entity.request_chat_id]
        try:
            groups_message().edit(request.entity.request_chat_id, message_id)
        except ApiTelegramException:
            pass


def cache_edit_group_name(state: str = None) -> str | bool:
    """
    Очищает состояние приёма сообщения у пользователя
    и изменяет сообщение по id из add_event_date

    if state - поставить
    if state is None - получить
    if state == "" - очистить
    """
    table = "edit_group_name"

    if state:
        Cache(table)[request.entity.request_chat_id] = state
        return True

    data = Cache(table)[request.entity.request_chat_id]

    if state is None:
        return data

    if data:
        msg_date, message_id = data.split(",")
        del Cache(table)[request.entity.request_chat_id]
        try:
            daily_message(msg_date).edit(request.entity.request_chat_id, message_id)
        except ApiTelegramException:
            pass
