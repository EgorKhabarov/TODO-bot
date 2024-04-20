import html
import logging
import traceback
from time import sleep
from ast import literal_eval
from datetime import datetime
from typing import Callable, Literal

# noinspection PyPackageRequirements
from telebot.apihelper import ApiTelegramException

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

import config
from tgbot.bot import bot
from tgbot.request import request
from tgbot.time_utils import new_time_calendar
from tgbot.bot_actions import delete_message_action
from tgbot.lang import get_translate, get_theme_emoji
from tgbot.message_generator import (
    ChatAction,
    TextMessage,
    CallBackAnswer,
    DocumentMessage,
)
from tgbot.buttons_utils import (
    delmarkup,
    encode_id,
    decode_id,
    create_yearly_calendar_keyboard,
    create_monthly_calendar_keyboard,
    create_twenty_year_calendar_keyboard,
)
from tgbot.bot_messages import (
    menu_message,
    help_message,
    start_message,
    event_message,
    group_message,
    daily_message,
    event_history,
    limits_message,
    groups_message,
    events_message,
    account_message,
    settings_message,
    trash_can_message,
    select_one_message,
    about_event_message,
    event_status_message,
    notification_message,
    select_events_message,
    search_filter_message,
    search_filters_message,
    search_results_message,
    edit_event_date_message,
    event_show_mode_message,
    week_event_list_message,
    recurring_events_message,
    monthly_calendar_message,
    edit_events_date_message,
    before_event_delete_message,
    before_events_delete_message,
)
from tgbot.types import (
    TelegramAccount,
    set_user_telegram_chat_id,
    get_telegram_account_from_password,
)
from tgbot.utils import (
    fetch_weather,
    fetch_forecast,
    is_secure_chat,
    html_to_markdown,
    set_bot_commands,
    add_group_pattern,
    extract_search_query,
    re_user_login_message,
    re_user_signup_message,
    extract_search_filters,
    generate_search_sql_condition,
)
from todoapi.exceptions import (
    ApiError,
    WrongDate,
    TextIsTooBig,
    UserNotFound,
    StatusRepeats,
    EventNotFound,
    LimitExceeded,
    StatusConflict,
    NotGroupMember,
    NotUniqueEmail,
    NotUniqueUsername,
    StatusLengthExceeded,
    NotEnoughPermissions,
)
from todoapi.log_cleaner import clear_logs
from todoapi.utils import is_valid_year, re_email, re_username
from todoapi.types import (
    Account,
    VedisCache,
    create_user,
    set_user_status,
    get_account_from_password,
)
from telegram_utils.argument_parser import getargs
from telegram_utils.buttons_generator import generate_buttons, edit_button_data
from telegram_utils.command_parser import parse_command, get_command_arguments


add_event_cache = VedisCache("add_event")
add_group_cache = VedisCache("add_group")


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

    if isinstance(x, CallbackQuery) and x.data == "md":
        return delete_message_action(message)

    parsed_command = parse_command(message.text, {"arg": "long str"})
    command_text = parsed_command["command"]
    button_login = {
        "switch_inline_query_current_chat": "user.login\nusername: \npassword: "
    }
    button_signup = {
        "switch_inline_query_current_chat": (
            "user.signup\nemail: \nusername: \npassword: "
        )
    }
    markup = generate_buttons(
        [[{"/login": button_login}], [{"/signup": button_signup}]]
    )

    def login(username: str, password: str) -> None:
        if not (username and password):
            TextMessage(get_translate("errors.no_account"), markup).reply(message)
        elif not re_username.match(username):
            TextMessage(get_translate("errors.wrong_username")).reply(message)
        else:
            try:
                set_user_telegram_chat_id(
                    get_account_from_password(username, password), message.chat.id
                )
            except UserNotFound:
                TextMessage(get_translate("errors.account_not_found")).reply(message)
            except ApiError:
                TextMessage(get_translate("errors.error")).reply(message)
            else:
                TextMessage(get_translate("errors.success")).send(message.chat.id)
                bot.delete_message(message.chat.id, message.message_id)
                request.entity = get_telegram_account_from_password(username, password)
                start_message().send(message.chat.id)
                set_bot_commands()

    def signup(email: str, username: str, password: str) -> None:
        if not (email and username and password):
            TextMessage(get_translate("errors.no_account"), markup).reply(message)
        elif not re_email.match(email):
            TextMessage(get_translate("errors.wrong_email")).reply(message)
        elif not re_username.match(username):
            TextMessage(get_translate("errors.wrong_username")).reply(message)
        else:
            try:
                create_user(email, username, password)
            except NotUniqueEmail:
                TextMessage(get_translate("errors.email_is_taken")).reply(message)
            except NotUniqueUsername:
                TextMessage(get_translate("errors.username_is_taken")).reply(message)
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
                    request.entity = get_telegram_account_from_password(
                        username, password
                    )
                    start_message().send(message.chat.id)
                    set_bot_commands()

    if match := add_group_pattern.match(message.text):
        if request.is_user:
            TextMessage(get_translate("errors.error")).reply(message)
            return

        owner_id, group_id = match.group(1), match.group(2)
        try:
            request.entity = TelegramAccount(x.from_user.id)
        except UserNotFound:
            return TextMessage(get_translate("errors.failure")).reply(message)

        if request.entity.user_id != int(owner_id):
            return TextMessage(get_translate("errors.failure")).reply(message)

        try:
            request.entity.set_group_telegram_chat_id(group_id, message.chat.id)
        except (NotEnoughPermissions, NotGroupMember):
            return TextMessage(get_translate("errors.failure")).reply(message)

        TextMessage(get_translate("errors.success")).reply(message)
        start_message().send(message.chat.id)
        set_bot_commands()

    elif command_text == "start":
        m = markup if request.is_user else None
        TextMessage(get_translate("messages.start"), m).send(message.chat.id)

    elif command_text == "login":
        if request.is_member:
            text = get_translate("errors.forbidden_to_log_account_in_group")
            return TextMessage(text).reply(message)

        login(
            *get_command_arguments(
                message.text,
                {"username": "str", "password": "str"},
            ).values()
        )

    elif command_text == "signup":
        if request.is_member:
            text = get_translate("errors.forbidden_to_log_account_in_group")
            return TextMessage(text).reply(message)

        signup(
            *get_command_arguments(
                message.text, {"email": "str", "username": "str", "password": "str"}
            ).values()
        )

    elif match := re_user_login_message.findall(message.text):
        login(*match[0])

    elif match := re_user_signup_message.findall(message.text):
        signup(*match[0])

    else:
        if request.is_user:
            TextMessage(get_translate("errors.no_account"), markup).reply(message)
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
    command_text = parsed_command["command"]

    if command_text == "start":
        if add_group_pattern.match(message.text) and request.is_member:
            TextMessage(get_translate("errors.already_connected_group")).reply(message)
            return

        set_bot_commands()
        start_message().send(chat_id)

    elif command_text == "menu":
        menu_message().send(chat_id)

    elif command_text == "calendar":
        monthly_calendar_message(None, "dl", "mnm").send(chat_id)

    elif command_text == "today":
        daily_message(request.entity.now_time()).send(chat_id)

    elif command_text == "week_event_list":
        week_event_list_message().send(chat_id)

    elif command_text == "help":
        help_message().send(chat_id)

    elif command_text == "settings":
        settings_message().send(chat_id)

    elif command_text in ("version", "v"):
        TextMessage(f"Version {config.__version__}").send(chat_id)

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
            message.html_text, {"query": ("long str", "")}
        )["query"]
        query = html_to_markdown(raw_query)
        search_results_message(query).send(chat_id)

    elif command_text == "dice":
        value = bot.send_dice(
            chat_id, message_thread_id=request.query.message_thread_id or None
        ).json["dice"]["value"]
        sleep(4)
        TextMessage(value).send(chat_id)

    elif command_text == "export":
        file_format = get_command_arguments(
            message_text,
            {"format": ("str", "csv")},
        )["format"].strip()

        if file_format not in ("csv", "xml", "json", "jsonl"):
            return TextMessage(get_translate("errors.export_format")).reply(message)

        file = request.entity.export_data(
            f"events_{request.entity.now_time():%Y-%m-%d_%H-%M-%S}.{file_format}",
            file_format,
        )
        ChatAction("upload_document").send(chat_id)
        try:
            DocumentMessage(file).send(chat_id)
        except ApiTelegramException as e:
            logging.info(f'export ApiTelegramException "{e}"')
            TextMessage(get_translate("errors.file_is_too_big")).send(chat_id)

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
        if not is_secure_chat(message):
            return

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

    elif command_text == "clear_logs":
        if not is_secure_chat(message):
            return

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
        if is_secure_chat(message):
            text += admin_commands
        TextMessage(text).send(chat_id)

    elif command_text == "logout":
        if request.is_user:
            set_user_telegram_chat_id(request.entity, None)
            TextMessage(get_translate("errors.success")).reply(message)
            set_bot_commands(True)

    elif command_text in ("login", "signup"):
        TextMessage(get_translate("errors.failure")).reply(message)


_handlers = {}
def prefix(prefix_: str | tuple[str, ...], arguments: dict = None, eval_: bool = None):
    if isinstance(prefix_, str):
        prefix_: tuple[str] = (prefix_,)

    def decorator(func: Callable):
        for p in prefix_:
            _handlers[p] = (
                func, arguments if arguments is not None else {}, eval_
            )
        return func
    return decorator


class CallBackHandler:
    def __call__(self, call: CallbackQuery):
        call_prefix = call.data.strip().split(maxsplit=1)[0]
        method: tuple[Callable, dict, bool] | None = _handlers.get(call_prefix)

        if method is None:
            return

        func, arguments, eval_ = method
        call_data = call.data.removeprefix(call_prefix).strip()

        # noinspection PyUnresolvedReferences
        return func(
            self,
            *literal_eval(call_data) if eval_ else (),
            **{
                k: v
                for k, v in {
                    "chat_id": call.message.chat.id,
                    "message_id": call.message.message_id,
                    "message": call.message,
                    "call_id": call.id,
                    "call_data": call_data,
                    "call": call,
                    **getargs(call_data)(arguments),
                }.items()
                if k in func.__code__.co_varnames
            }
        )

    @prefix("mnm")
    def menu(self, chat_id: int, message_id: int) -> None:
        menu_message().edit(chat_id, message_id)

    @prefix("mns")
    def settings(self, chat_id: int, message_id: int, call_id: int) -> None:
        try:
            settings_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    @prefix("mnw")
    def week_event_list(self, chat_id: int, message_id: int, call_id: int) -> None:
        try:
            week_event_list_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    @prefix("mngrs", {"mode": ("str", "al"), "page": ("int", 1)})
    def groups_message(self, mode: Literal["al", "me", "md", "ad"], page: int, chat_id: int, message_id: int) -> None:
        try:
            groups_message(mode, page).edit(chat_id, message_id)
        except ApiTelegramException:
            pass
        cache_create_group("")

    @prefix("mngr", {"group_id": "str", "mode": ("str", "al")})
    def group_message(self, group_id: str, mode: str, chat_id: int, message_id: int) -> None:
        group_message(group_id, message_id, mode).edit(chat_id, message_id)

    @prefix("mna")
    def account_message(self, chat_id: int, message_id: int):
        account_message(message_id).edit(chat_id, message_id)

    @prefix("mnc", eval_=True)
    def calendar(self, date: str, chat_id: int, message_id: int):
        date = new_time_calendar() if date == "now" else date
        monthly_calendar_message(date, "dl", "mnm").edit(chat_id, message_id)

    @prefix("mnh", {"page": ("long str", "page 1")})
    def help_message(self, page: str, chat_id: int, message_id: int, call_id: int, message: Message):
        markup = None if page.startswith("page") else message.reply_markup

        try:
            help_message(page).edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    @prefix("mnb")
    def bin_message(self, chat_id: int, message_id: int, call_id: int):
        if (request.is_user and request.entity.is_premium) or request.is_member:
            try:
                trash_can_message().edit(chat_id, message_id)
            except ApiTelegramException:
                CallBackAnswer("ok").answer(call_id, True)
        else:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)

    @prefix("mnn", {"date": "date"})
    def notification(self, n_date: datetime, chat_id: int, message_id: int, call_id: int):
        if n_date is None:
            return monthly_calendar_message(
                None, "mnn", "mnm", get_translate("select.notification_date")
            ).edit(chat_id, message_id)

        try:
            notification_message(n_date, from_command=True).edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    @prefix("mnsr")
    def search_message(self, chat_id: int, message_id: int):
        search_results_message(
            get_translate("text.search_placeholder"), id_list=[0], is_placeholder=True
        ).edit(chat_id, message_id)

    @prefix("dl", {"date": "date"})
    def daily_message(self, date: datetime, chat_id: int, message_id: int, call_id: int):
        cache_add_event_date("")
        try:
            daily_message(date).edit(chat_id, message_id)
        except ApiTelegramException:
            logging.error(traceback.format_exc())
            CallBackAnswer("ok").answer(call_id, True)

    @prefix("em", {"event_id": "int"})
    def event_message(self, event_id: int, chat_id: int, message_id: int, call_id: int):
        generated = event_message(event_id, message_id=message_id)
        if generated:
            try:
                generated.edit(chat_id, message_id)
            except ApiTelegramException:
                CallBackAnswer("ok").answer(call_id, True)
        else:
            text = get_translate("errors.no_events_to_interact")
            CallBackAnswer(text).answer(call_id, True)

    @prefix("ea", {"date": "str"})
    def event_add(self, date: datetime, chat_id: int, message_id: int, call_id: int, message: Message):
        cache_add_event_date("")

        # Проверяем будет ли превышен лимит для пользователя, если добавить 1 событие с 1 символом
        if request.entity.limit.is_exceeded_for_events(date, 1, 1):
            CallBackAnswer(get_translate("errors.exceeded_limit")).answer(call_id, True)
            return

        cache_add_event_date(f"{date},{message_id}")
        send_event_text = get_translate("text.send_event_text")
        CallBackAnswer(send_event_text).answer(call_id)
        text = f"{message.html_text}\n\n<b>?.?.</b>⬜\n{send_event_text}"
        markup = generate_buttons([[{get_theme_emoji("back"): f"dl {date}"}]])
        TextMessage(text, markup).edit(chat_id, message_id)

    @prefix("es", {"statuses": "str", "folder": "str", "event_id": "int", "date": "str"})
    def event_status_page(self, statuses: str, folder: str, event_id: int, date: str, chat_id: int, message_id: int):
        event_status_message(statuses, folder, event_id, date).edit(chat_id, message_id)

    @prefix("ess", {"event_id": "int", "date": "str", "new_status": "str"})
    def event_status_set(self, event_id: int, date: str, new_status: str, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.edit_event_status(event_id, new_status.split(","))
        except EventNotFound:
            return daily_message(date).edit(chat_id, message_id)
        except StatusConflict:
            text = get_translate("errors.conflict_statuses")
        except StatusLengthExceeded:
            text = get_translate("errors.more_5_statuses")
        except StatusRepeats:
            text = get_translate("errors.status_already_posted")
        except ApiError:
            logging.error(traceback.format_exc())
            text = get_translate("errors.error")
        else:
            generated = event_message(event_id, False, message_id)
            return generated.edit(chat_id, message_id)

        CallBackAnswer(text).answer(call_id, True)

    @prefix("eet", {"event_id": "int", "date": "date"})
    def event_edit_text(self, event_id: int, date: datetime, chat_id: int, message_id: int, call_id: int, message: Message):
        text = message.text.split("\n", maxsplit=2)[-1]

        try:
            request.entity.edit_event_text(event_id, text)
        except EventNotFound:
            daily_message(date).edit(chat_id, message_id)
        except TextIsTooBig:
            text = get_translate("errors.message_is_too_long")
        except LimitExceeded:
            text = get_translate("errors.limit_exceeded")
        except ApiError:
            text = get_translate("errors.error")
        else:
            CallBackAnswer(get_translate("text.changes_saved")).answer(call_id)
            event_message(event_id, False, message_id).edit(chat_id, message_id)
            return
        CallBackAnswer(text).answer(call_id, True)

    @prefix("eds", {"event_id": "int", "date": "date"})
    def event_new_date_set(self, event_id: int, date: datetime, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.edit_event_date(event_id, f"{date:%d.%m.%Y}")
        except (ApiError, WrongDate):
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
        except LimitExceeded:
            CallBackAnswer(get_translate("errors.limit_exceeded")).answer(call_id, True)
        else:
            CallBackAnswer(get_translate("text.changes_saved")).answer(call_id)
            event_message(event_id, False, message_id).edit(chat_id, message_id)

    @prefix("ed", {"event_id": "int", "date": "date"})
    def event_delete(self, event_id: int, date: datetime, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.delete_event(event_id)
        except EventNotFound:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
        daily_message(date).edit(chat_id, message_id)

    @prefix("edb", {"event_id": "int", "date": "date"})
    def event_delete_to_bin(self, event_id: int, date: datetime, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.delete_event_to_bin(event_id)
        except NotEnoughPermissions:
            text = get_translate("errors.not_enough_permissions")
            CallBackAnswer(text).answer(call_id)
        except EventNotFound:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)

        daily_message(date).edit(chat_id, message_id)

    @prefix("esdt", {"event_id": "int", "date": "date"})
    def event_select_new_date(self, event_id: int, date: datetime, chat_id: int, message_id: int):
        generated = edit_event_date_message(event_id, date)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    @prefix("ebd", {"event_id": "int", "date": "date"})
    def event_before_delete(self, event_id: int, date: datetime, chat_id: int, message_id: int):
        generated = before_event_delete_message(event_id)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    @prefix("eab", {"event_id": "int", "date": "date"})
    def event_before_delete(self, event_id: int, date: datetime, chat_id: int, message_id: int):
        generated = about_event_message(event_id)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    @prefix("esh", {"event_id": "int", "date": "date"})
    def event_before_delete(self, event_id: int, date: datetime, chat_id: int, message_id: int):
        generated = event_show_mode_message(event_id)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    @prefix("eh", {"event_id": "int", "date": "date", "page": ("int", 1)})
    def event_before_delete(self, event_id: int, date: datetime, page: int, chat_id: int, message_id: int):
        generated = event_history(event_id, date, page)
        if generated is None:
            generated = daily_message(date)
        generated.edit(chat_id, message_id)

    @prefix("esm", {"id_list": "str"})
    def events_message(self, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
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

    @prefix("esbd", {"id_list": "str"})
    def events_before_delete(self, id_list: str, chat_id: int, message_id: int):
        generated = before_events_delete_message(decode_id(id_list))
        generated.edit(chat_id, message_id)

    @prefix("essd", {"id_list": "str"})
    def events_select_new_date(self, id_list: str, chat_id: int, message_id: int):
        generated = edit_events_date_message(decode_id(id_list))
        generated.edit(chat_id, message_id)

    @prefix("esd", {"id_list": "str", "date": "date"})
    def events_delete(self, id_list: str, date: datetime, chat_id: int, message_id: int, call_id: int):
        not_deleted: list[int] = []
        for event_id in decode_id(id_list):
            try:
                request.entity.delete_event(event_id)
            except EventNotFound:
                not_deleted.append(event_id)

        if not_deleted:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
            return events_message(not_deleted).edit(chat_id, message_id)

        daily_message(date).edit(chat_id, message_id)

    @prefix("esdb", {"id_list": "str", "date": "date"})
    def events_delete_to_bin(self, id_list: str, date: datetime, chat_id: int, message_id: int, call_id: int):
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

        daily_message(date).edit(chat_id, message_id)

    @prefix("esds", {"id_list": "str", "date": "date"})
    def events_new_date_set(self, id_list: str, date: datetime, chat_id: int, message_id: int, call_id: int):
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

    @prefix("se", {"info": "str", "id_list": "str"})
    def select_event(self, info: str, id_list: str, chat_id: int, message_id: int, call_id: int, call_data: str, message: Message):
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
                query = extract_search_query(message.html_text)
                filters = extract_search_filters(message.html_text)
                string_filters = [
                    f"{args[0]}: {html.escape(' '.join(args[1:]))}"
                    for args in filters
                    if args
                ]
                all_string_filters = "\n".join(string_filters)
                srch = get_translate("messages.search")
                if all_string_filters:
                    all_string_filters = f"\n{all_string_filters}"
                generated.text = f"🔍 {srch} <u>{html.escape(query)}</u>:{all_string_filters}\n\n{generated.text}"
            generated.edit(chat_id, message_id)
        else:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)

    @prefix("ses", {"info": "str", "id_list": "str"})
    def select_events(self, info: str, id_list: str, chat_id: int, message_id: int, call_id: int, call_data: str, message: Message):
        back_data = call_data.removeprefix(f"{info} {id_list}").strip()
        generated = select_events_message(
            decode_id(id_list),
            back_data,
            in_bin="b" in info,
            is_in_search="s" in info,
        )
        if generated:
            if "s" in info:
                query = extract_search_query(message.html_text)
                filters = extract_search_filters(message.html_text)
                string_filters = [
                    f"{args[0]}: {html.escape(' '.join(args[1:]))}"
                    for args in filters
                    if args
                ]
                all_string_filters = "\n".join(string_filters)
                srch = get_translate("messages.search")
                if all_string_filters:
                    all_string_filters = f"\n{all_string_filters}"
                generated.text = f"🔍 {srch} <u>{html.escape(query)}</u>:{all_string_filters}\n\n{generated.text}"
            generated.edit(chat_id, message_id)
        else:
            no_events = get_translate("errors.no_events_to_interact")
            CallBackAnswer(no_events).answer(call_id, True)

    @prefix(("sal", "sbal"))
    def select_all(self, chat_id: int, message_id: int, message: Message):
        # select all | select all in bin
        for line in message.reply_markup.keyboard[:-1]:
            for button in line:
                button.text = (
                    button.text.removeprefix("👉")
                    if button.text.startswith("👉")
                    else f"👉{button.text}"
                )
        generated = TextMessage(markup=message.reply_markup)
        generated.edit(chat_id, message_id, only_markup=True)

    @prefix(("son", "sbon"), {"row": "int", "column": ("int", 0)})
    def select_one(self, row: int, column: int, chat_id: int, message_id: int, message: Message):
        # select one | select one in bin
        button = message.reply_markup.keyboard[row][column]
        button.text = (
            button.text.removeprefix("👉")
            if button.text.startswith("👉")
            else f"👉{button.text}"
        )
        generated = TextMessage(markup=message.reply_markup)
        generated.edit(chat_id, message_id, only_markup=True)

    @prefix("pd", {"date": "str", "page": ("int", 0), "id_list": ("str", "")})
    def page_daily(self, date: str, page: int, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
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

    @prefix("pr", {"date": "str", "page": ("int", 0), "id_list": ("str", "")})
    def page_recurring(self, date: str, page: int, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
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

    @prefix("ps", {"page": ("int", 1), "id_list": ("str", "")})
    def page_search(self, page: int, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, 1, f"se os {id_list} us")
            edit_button_data(markup, 0, 2, f"ses s {id_list} us")
        try:
            search_results_message(
                extract_search_query(message.html_text),
                extract_search_filters(message.html_text),
                decode_id(id_list),
                page,
            ).edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    @prefix("pw", {"page": ("int", 0), "id_list": ("str", ())})
    def page_week_event_list(self, page: int, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
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

    @prefix("pb", {"page": ("int", 0), "id_list": ("str", ())})
    def page_bin(self, page: int, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
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

    @prefix("pn", {"date": "date", "page": ("int", 0), "id_list": ("str", ())})
    def page_notification(self, n_date: datetime, page: int, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
        markup = message.reply_markup if page else None
        if markup:
            edit_button_data(markup, 0, -1, f"se o {id_list} mnn {n_date:%d.%m.%Y}")
        try:
            generated = notification_message(n_date, decode_id(id_list), page, True)
            generated.edit(chat_id, message_id, markup=markup)
        except ApiTelegramException:
            text = get_translate("errors.already_on_this_page")
            CallBackAnswer(text).answer(call_id)

    @prefix("cm", eval_=True)
    def calendar_month(self, command, back, date, arguments, chat_id: int, message_id: int, call_id: int, call: CallbackQuery):
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

    @prefix("cy", eval_=True)
    def calendar_year(self, command, back, year, arguments, chat_id: int, message_id: int, call_id: int):
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

    @prefix("ct", eval_=True)
    def calendar_twenty_year(self, command, back, decade, arguments, chat_id: int, message_id: int, call_id: int):
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

    @prefix("us")
    def update_search(self, chat_id: int, message_id: int, call_id: int, message: Message):
        try:
            search_results_message(
                extract_search_query(message.html_text),
                extract_search_filters(message.html_text),
            ).edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    @prefix("sfs")
    def search_filters(self, chat_id: int, message_id: int, call_data: str, message: Message):
        if message.text.startswith("🔍"):
            search_filters_message(message, call_data).edit(chat_id, message_id)

    @prefix("sf")
    def search_filter(self, chat_id: int, message_id: int, call_data: str, message: Message):
        if message.text.startswith("🔍⚙️"):
            search_filter_message(message, call_data).edit(chat_id, message_id)

    @prefix("sfe")
    def search_filter_export(self, chat_id: int, message: Message):
        if message.text.startswith("🔍"):
            query = extract_search_query(message.html_text)
            filters = extract_search_filters(message.html_text)
            file = request.entity.export_data(
                f"events_{request.entity.now_time():%Y-%m-%d_%H-%M-%S}.csv",
                "csv",
                *generate_search_sql_condition(query, filters),
            )
            ChatAction("upload_document").send(chat_id)
            try:
                DocumentMessage(file).send(chat_id)
            except ApiTelegramException as e:
                logging.info(f'export ApiTelegramException "{e}"')
                TextMessage(get_translate("errors.file_is_too_big")).send(chat_id)

    @prefix("md")
    def message_delete(self, message: Message):
        delete_message_action(message)

    @prefix("std")
    def settings_restore_to_default(self, chat_id: int, message_id: int, call_id: int):
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

    @prefix("ste", {"par_name": "str", "par_val": "str"})
    def settings_set(self, par_name: str, par_val: str, chat_id: int, message_id: int, call_id: int):
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

    @prefix("bcl")
    def bin_clear(self, chat_id: int, message_id: int, call_id: int):
        request.entity.clear_basket()

        try:
            trash_can_message().edit(chat_id, message_id)
        except ApiTelegramException:
            CallBackAnswer("ok").answer(call_id, True)

    @prefix("bem", {"event_id": "int"})
    def event_message_bin(self, event_id: int, chat_id: int, message_id: int, call_id: int):
        generated = event_message(event_id, True, message_id=message_id)
        if generated:
            try:
                generated.edit(chat_id, message_id)
            except ApiTelegramException:
                CallBackAnswer("ok").answer(call_id, True)
        else:
            text = get_translate("errors.no_events_to_interact")
            CallBackAnswer(text).answer(call_id, True)

    @prefix("bed", {"event_id": "int"})
    def event_delete_bin(self, event_id: int, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.delete_event(event_id, in_bin=True)
        except EventNotFound:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)
        try:
            trash_can_message().edit(chat_id, message_id)
        except ApiTelegramException:
            pass

    @prefix("ber", {"event_id": "int", "date": "date"})
    def event_recover_bin(self, event_id: int, date: datetime, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.recover_event(event_id)
        except (EventNotFound, LimitExceeded):
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
            return  # такого события нет

        trash_can_message().edit(chat_id, message_id)

    @prefix("bsm", {"id_list": "str"})
    def events_message_bin(self, id_list: str, chat_id: int, message_id: int, call_id: int, message: Message):
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

    @prefix("bsd", {"id_list": "str"})
    def events_delete_bin(self, id_list: str, chat_id: int, message_id: int, call_id: int):
        not_deleted: list[int] = []
        for event_id in decode_id(id_list):
            try:
                request.entity.delete_event(event_id, in_bin=True)
            except EventNotFound:
                not_deleted.append(event_id)

        if not_deleted:
            CallBackAnswer(get_translate("errors.error")).answer(call_id)

        trash_can_message().edit(chat_id, message_id)

    @prefix("bsr", {"id_list": "str", "date": "date"})
    def events_recover_bin(self, id_list: str, date: datetime, chat_id: int, message_id: int, call_id: int):
        not_recover: list[int] = []
        for event_id in decode_id(id_list):
            try:
                request.entity.recover_event(event_id)
            except (LimitExceeded, ApiError):
                not_recover.append(event_id)

        if not_recover:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)

        trash_can_message().edit(chat_id, message_id)

    @prefix("logout")
    def logout(self, chat_id: int, message_id: int):
        if request.is_user:
            set_user_telegram_chat_id(request.entity, None)
            set_bot_commands(True)
            TextMessage(get_translate("errors.success")).edit(chat_id, message_id)

    @prefix("lm", {"date": "date"})
    def limits_message(self, date: datetime, chat_id: int, message_id: int):
        if not date:
            generated = monthly_calendar_message(None, "lm", "mna")
            return generated.edit(chat_id, message_id)
        limits_message(date).edit(chat_id, message_id, disable_web_page_preview=False)

    @prefix("grcr")
    def group_create(self, chat_id: int, message_id: int, call_id: int):
        cache_create_group("")
        if request.entity.limit.is_exceeded_for_groups(create=True):
            text = get_translate("errors.limit_exceeded")
            return CallBackAnswer(text).answer(call_id)

        cache_create_group(str(message_id))
        text = """
👥 Группы 👥

Отправьте имя группы
"""
        markup = generate_buttons([[{get_theme_emoji("back"): "mngrs"}]])
        TextMessage(text, markup).edit(chat_id, message_id)
        CallBackAnswer(get_translate("text.send_group_name")).answer(call_id)

    @prefix("gre", {"group_id": "str", "format": ("str", "csv")})
    def group_export(self, group_id: str, file_format: str, chat_id: int, message: Message):
        # TODO ограничить кол-во взаимодействий
        if file_format not in ("csv", "xml", "json", "jsonl"):
            return TextMessage(get_translate("errors.export_format")).reply(message)

        file = Account(request.entity.user_id, group_id).export_data(
            f"events_{request.entity.now_time():%Y-%m-%d_%H-%M-%S}.{file_format}",
            file_format,
        )
        ChatAction("upload_document").send(chat_id)
        try:
            DocumentMessage(file).send(chat_id)
        except ApiTelegramException:
            logging.error(traceback.format_exc())
            TextMessage(get_translate("errors.file_is_too_big")).send(chat_id)

    @prefix("grd", {"group_id": "str", "mode": ("str", "al")})
    def group_delete(self, group_id: str, mode: str, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.delete_group(group_id)
        except (NotGroupMember, NotEnoughPermissions):
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
        else:
            groups_message(mode).edit(chat_id, message_id)

    @prefix("grlv", {"group_id": "str", "mode": ("str", "al")})
    def group_leave(self, group_id: str, mode: str, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.remove_group_member(request.entity.user_id, group_id)
        except NotGroupMember:
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
        else:
            groups_message(mode).edit(chat_id, message_id)

    @prefix("grrgr", {"group_id": "str", "mode": ("str", "al")})
    def group_remove_from_telegram_group(self, group_id: str, mode: str, chat_id: int, message_id: int, call_id: int):
        try:
            request.entity.set_group_telegram_chat_id(group_id)
        except (NotGroupMember, NotEnoughPermissions):
            CallBackAnswer(get_translate("errors.error")).answer(call_id, True)
        else:
            group_message(group_id, message_id, mode).edit(chat_id, message_id)

    @prefix("get_premium")
    def get_premium(self, chat_id: int, message_id: int, call_id: int):
        # Заглушка на получение доступа к корзине и повышенным лимитам
        # TODO реализовать нормальное получение
        if request.is_user:
            set_user_status(request.entity.user_id, 1)
            CallBackAnswer("ok").answer(call_id, True)
            request.entity.user.user_status = 1
            account_message(message_id).edit(chat_id, message_id)


callback_handler = CallBackHandler()


def reply_handler(message: Message, reply_to_message: Message) -> None:
    """
    Реакции на ответ на сообщение бота
    """

    if reply_to_message.text.startswith("⚙️"):
        try:
            request.entity.set_telegram_user_settings(
                city=html_to_markdown(message.html_text)[:50]
            )
        except ValueError:
            TextMessage(get_translate("errors.error")).reply(message)
        else:
            try:
                settings_message().edit(request.chat_id, reply_to_message.message_id)
            except ApiTelegramException:
                return
            else:
                delete_message_action(message)

    elif reply_to_message.text.startswith("🔍 "):
        query = html_to_markdown(message.html_text)
        filters = extract_search_filters(reply_to_message.html_text)
        search_results_message(query, filters).edit(
            request.chat_id, reply_to_message.message_id
        )
        delete_message_action(message)


def cache_add_event_date(state: str = None) -> str | bool:
    """
    Очищает состояние приёма сообщения у пользователя
    и изменяет сообщение по id из add_event_date

    if state - поставить
    if state is None - получить
    if state == "" - очистить
    """

    if state:
        add_event_cache[request.entity.request_chat_id] = state
        return True

    data = add_event_cache[request.entity.request_chat_id]

    if state is None:
        return data

    if data:
        msg_date, message_id = data.split(",")
        del add_event_cache[request.entity.request_chat_id]
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

    if state:
        add_group_cache[request.entity.request_chat_id] = state
        return True

    data = add_group_cache[request.entity.request_chat_id]

    if state is None:
        return data

    if data:
        message_id = int(data)
        del add_group_cache[request.entity.request_chat_id]
        try:
            groups_message().edit(request.entity.request_chat_id, message_id)
        except ApiTelegramException:
            pass
