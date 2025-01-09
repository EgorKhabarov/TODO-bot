from io import StringIO
from copy import deepcopy
from sqlite3 import Error
from datetime import datetime
from typing import Any

# noinspection PyPackageRequirements
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, InputFile

from tgbot.bot import bot
from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.time_utils import relatively_string_date
from tgbot.buttons_utils import encode_id, number_to_power
from tgbot.utils import add_status_effect, get_message_thread_id
from todoapi.logger import logger
from todoapi.types import db, Event
from todoapi.exceptions import EventNotFound


event_formats = {
    "dl": "<b>{numd}.{event_id}.</b>{statuses}\n{markdown_text}\n",
    "dt": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> {reldate}\n{markdown_text}\n",
    "b": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> ({days_before_delete})\n{markdown_text}\n",
    "r": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> {reldate}{days_before}\n{markdown_text}\n",
    "s": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u>\n{markdown_text}\n",
    "a": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> {reldate}\n{text}\n",
}
"""
"dl" - Template for events for one day
"dt" - Template for events on different days
"b" - Template for the cart, shows the number of days until the event is allocated
"r" - A pattern for events that can be repeated,
      shows the number of days until the next repetition
"s" - Template for displaying events, without relative dates
"a" - Template for displaying an event message, without markdown markup
"""


def calculate_days_before_event(date, statuses):
    return Event(0, "", 0, date, "", statuses, "", "", "").days_before_event(
        request.entity.settings.timezone
    )


def pagination(
    sql_where: str,
    params: dict,
    max_group_len: int = 10,
    max_group_symbols_count: int = 2500,
    max_group_id_len: int = 39,
) -> list[str]:
    """
    :param sql_where: SQL condition
    :param params: options
    :param max_group_len: Maximum number of elements per page
    :param max_group_symbols_count: Maximum number of characters per page
    :param max_group_id_len: Maximum length of shortened id
    The amount of data in a button is limited to 64 characters
    """

    data = db.execute(
        f"""
SELECT event_id,
       LENGTH(text)
  FROM events
 WHERE {sql_where}
 ORDER BY ABS(DAYS_BEFORE_EVENT(date, statuses)),
          DAYS_BEFORE_EVENT(date, statuses),
          statuses LIKE '%📬%',
          statuses LIKE '%🗞%',
          statuses LIKE '%📅%',
          statuses LIKE '%📆%',
          statuses LIKE '%🎉%',
          statuses LIKE '%🎊%',
          statuses LIKE '%🟥%',
          event_id DESC
 LIMIT 400;
""",
        params=params,
        functions=(("DAYS_BEFORE_EVENT", calculate_days_before_event),),
    )
    _result = []
    group = []
    group_sum = 0

    for event_id, text_len in data:
        event_id = str(event_id)
        if (
            len(group) < max_group_len
            and group_sum + text_len <= max_group_symbols_count
            and len(encode_id([int(i) for i in group + [event_id]])) <= max_group_id_len
        ):
            group.append(event_id)
            group_sum += text_len
        else:
            if group:
                _result.append(",".join(group))
            group = [event_id]
            group_sum = text_len

    if group:
        _result.append(",".join(group))

    return _result


class TextMessage:
    def __init__(self, text: str = None, markup: InlineKeyboardMarkup = None):
        self.text = text
        self.markup = markup

    def send(self, chat_id: int = None, **kwargs) -> Message:
        return bot.send_message(
            chat_id=int(chat_id or request.chat_id),
            text=self.text,
            reply_markup=self.markup,
            message_thread_id=get_message_thread_id(),
            **kwargs,
        )

    def edit(
        self,
        chat_id: int = None,
        message_id: int = None,
        *,
        only_markup: bool = False,
        markup: InlineKeyboardMarkup = None,
        **kwargs,
    ) -> None:
        """
        :param chat_id: chat_id
        :param message_id: message_id
        :param only_markup: update only keyboard self.markup
        :param markup: update self.text and keyboard markup


        bot.edit_message_text(text, chat_id, message_id, reply_markup=self.markup)

        .edit(chat_id, message_id, markup=markup)

        bot.edit_message_reply_markup(self.text, chat_id, message_id, reply_markup=markup)

        .edit(chat_id, message_id, only_markup=True)

        bot.edit_message_text(self.text, chat_id, message_id, reply_markup=self.markup)

        .edit(chat_id, message_id)
        """
        if not message_id:
            if request.is_callback:
                message: Message = request.query.message
            else:
                message: Message = request.query

            message_id = message.message_id

        if only_markup:
            bot.edit_message_reply_markup(
                chat_id=int(chat_id or request.chat_id),
                message_id=int(message_id),
                reply_markup=self.markup,
                **kwargs,
            )
        elif markup is not None:
            bot.edit_message_text(
                text=self.text,
                chat_id=int(chat_id or request.chat_id),
                message_id=int(message_id),
                reply_markup=markup,
                **kwargs,
            )
        else:
            bot.edit_message_text(
                text=self.text,
                chat_id=int(chat_id or request.chat_id),
                message_id=int(message_id),
                reply_markup=self.markup,
                **kwargs,
            )

    def reply(self, message: Message = None, **kwargs):
        if message:
            if message.reply_to_message:
                message_thread_id = message.reply_to_message.message_thread_id
            else:
                message_thread_id = message.message_thread_id
        else:
            message_thread_id = get_message_thread_id()

            if request.is_message:
                message = request.query
            else:
                message = request.query.message

        bot.reply_to(
            message=message,
            text=self.text,
            reply_markup=self.markup,
            message_thread_id=message_thread_id,
            **kwargs,
        )


class CallBackAnswer:
    def __init__(self, text: str):
        self.text = text

    def answer(self, call_id: int = None, show_alert: bool = None, url: str = None):
        if not call_id and request.is_callback:
            call_id = request.query.id

        bot.answer_callback_query(call_id, self.text, show_alert, url)


class ChatAction:
    def __init__(self, action: str):
        self.action = action

    def send(self, chat_id: int = None, **kwargs) -> None:
        bot.send_chat_action(
            chat_id=chat_id or request.chat_id,
            action=self.action,
            message_thread_id=getattr(request.query, "message_thread_id", None),
            **kwargs,
        )


class DocumentMessage:
    def __init__(
        self,
        document: Any | StringIO,
        caption: str = None,
        markup: InlineKeyboardMarkup = None,
        file_name: str | None = None,
    ):
        self.__document = document
        self.caption = caption
        self.markup = markup
        self.file_name = (
            document.name if hasattr(document, "name") else None
        ) or file_name

    def send(self, chat_id: int = None, **kwargs):
        bot.send_document(
            chat_id=chat_id or request.chat_id,
            document=InputFile(self.__document, self.file_name),
            caption=self.caption,
            message_thread_id=getattr(request.query, "message_thread_id", None),
            **kwargs,
        )


class EventMessage(TextMessage):
    """
    Class for interacting with one event
    """

    def __init__(self, event_id: int, in_wastebasket: bool = False):
        super().__init__()
        self.event_id = event_id
        self.event: Event | None = None
        try:
            self.event = request.entity.get_event(event_id, in_wastebasket)
        except EventNotFound:
            pass

    def format(
        self,
        title: str = "",
        event_date_representation: str = "",
        markup: InlineKeyboardMarkup = None,
    ):
        str_date, rel_date, week_date = relatively_string_date(
            self.event.days_before_event(request.entity.settings.timezone)
        )

        days_before = ""
        markdown_text = ""
        if "{markdown_text}" in event_date_representation:
            markdown_text = add_status_effect(self.event.text, self.event.statuses)

        days_before_delete = ""
        if self.event.removal_time is not None:
            days_before_delete = get_translate("func.deldate")(
                self.event.days_before_delete
            )

        event_date_representation = event_date_representation.format(
            date=self.event.date,
            strdate=str_date,
            weekday=week_date,
            reldate=rel_date,
            event_id=f"{self.event.event_id}",
            statuses=self.event.string_statuses,
            markdown_text=markdown_text,
            days_before=days_before,
            days_before_delete=days_before_delete,
            text=self.event.text,
        )
        self.text = f"<b>{title}</b>\n{event_date_representation}".strip()
        self.markup = markup
        return self


class EventsMessage(TextMessage):
    """
    Class for filling and formatting messages using a template
    """

    def __init__(
        self,
        date: str = "now",
        event_list: tuple | list[Event, ...] = tuple(),
        markup: InlineKeyboardMarkup = None,
        page: int = 0,
        page_indent: int = 0,
    ):
        if markup is ...:
            markup = InlineKeyboardMarkup()
        super().__init__("", deepcopy(markup))
        if date == "now":
            date = f"{request.entity.now_time():%d.%m.%Y}"

        self.event_list = event_list
        self._date = date
        self.page = page
        self.page_indent = page_indent
        self.page_signature_needed = True if page else False

    def get_pages_data(self, sql_where: str, params: dict | tuple, callback_data: str):
        """
        Get a list of row id tuples by page
        """
        data = pagination(sql_where, params)

        if data:
            first_message = [
                Event(*event)
                for event in db.execute(
                    f"""
SELECT user_id,
       group_id,
       event_id,
       date,
       text,
       statuses,
       adding_time,
       recent_changes_time,
       removal_time
  FROM events
 WHERE event_id IN ({data[0]})
       AND ({sql_where})
 ORDER BY ABS(DAYS_BEFORE_EVENT(date, statuses)),
          DAYS_BEFORE_EVENT(date, statuses),
          statuses LIKE '%📬%',
          statuses LIKE '%🗞%',
          statuses LIKE '%📅%',
          statuses LIKE '%📆%',
          statuses LIKE '%🎉%',
          statuses LIKE '%🎊%',
          statuses LIKE '%🟥%',
          event_id DESC;
""",
                    params=params,
                    functions=(("DAYS_BEFORE_EVENT", calculate_days_before_event),),
                )
            ]

            self.event_list = first_message

            count_columns = 5
            page_diapason: list[list[tuple[int, str]]] = []
            for num, d in enumerate(data):  # Filling data from ranges into a list
                if int(f"{num}"[-1]) in (0, count_columns):
                    # Divide the ranges into lines of 5
                    page_diapason.append([])
                # Page number, id
                page_diapason[-1].append(
                    (num + 1, encode_id([int(i) for i in d.split(",")]))
                )

            if len(page_diapason[0]) != 1:  # If there is more than one page
                self.page_signature_needed = True
                for i in range(count_columns - len(page_diapason[-1])):
                    # Filling the empty buttons in the last row up to 5
                    page_diapason[-1].append((0, ""))

                # Trim down to 8 button lines, so there aren't too many button lines
                for row in page_diapason[:8]:
                    self.markup.row(
                        *[
                            (
                                InlineKeyboardButton(
                                    f"{page_num}{number_to_power(str(len(event_ids.split(','))))}",
                                    callback_data=f"{callback_data.strip()} {page_num} {event_ids}",
                                )
                                if event_ids
                                else InlineKeyboardButton(" ", callback_data="None")
                            )
                            for page_num, event_ids in row
                        ]
                    )
            else:
                self.page_signature_needed = False
        return self

    def get_page_events(self, sql_where: str, params: tuple, id_list: list[int]):
        """
        Returns events included in values with the WHERE condition
        """
        try:
            res = [
                Event(*event)
                for event in db.execute(
                    f"""
SELECT user_id,
       group_id,
       event_id,
       date,
       text,
       statuses,
       adding_time,
       recent_changes_time,
       removal_time
  FROM events
 WHERE user_id IS ?
       AND group_id IS ?
       AND event_id IN ({','.join('?' for _ in id_list)})
       AND ({sql_where})
 ORDER BY ABS(DAYS_BEFORE_EVENT(date, statuses)),
          DAYS_BEFORE_EVENT(date, statuses),
          statuses LIKE '%📬%',
          statuses LIKE '%🗞%',
          statuses LIKE '%📅%',
          statuses LIKE '%📆%',
          statuses LIKE '%🎉%',
          statuses LIKE '%🎊%',
          statuses LIKE '%🟥%',
          event_id DESC;
""",
                    params=(
                        request.entity.safe_user_id,
                        request.entity.group_id,
                        *id_list,
                        *params,
                    ),
                    functions=(("DAYS_BEFORE_EVENT", calculate_days_before_event),),
                )
            ]
        except Error as e:
            logger.info(
                f'[message_generator.py -> MessageGenerator.get_events] Error "{e}"'
            )
            self.event_list = []
        else:
            self.event_list = res
        return self

    def format(
        self,
        title: str,
        args: str = event_formats["dl"],
        ending: str = "",
        if_empty: str = "🕸🕷  🕸",
        **kwargs,
    ):
        """
        Filling out a message using a template
        {date} - Date ["0000.00.00"]
        {strdate} - String Date ["0 January"]
        {weekday} - Week Date ["Monday"]
        {reldate} - Relatively Date ["Tomorrow"]

        {numd} - Serial number (digits) ["1 2 3"]
        {event_id} - Event_id ["1"]
        {status} - Status ["⬜"]
        {markdown_text} - wraps the text in the desired status tag ["<b>"]
        {text} - Text ["text"]
        {days_before_delete} - Days until removal
        {days_before} - (Days until)

        :param title: Heading
        :param args: Repeating pattern
        :param ending: End of message
        :param if_empty: If the query result is empty
        :return: message.text
        """
        dt_date = datetime.strptime(self._date, "%d.%m.%Y")
        n_time = request.entity.now_time()
        n_time = datetime(n_time.year, n_time.month, n_time.day)
        str_date, rel_date, week_date = relatively_string_date((dt_date - n_time).days)

        format_string = (
            title.format(
                date=self._date,
                strdate=str_date,
                weekday=week_date,
                reldate=rel_date,
            ).strip()
            + "\n"
        )
        if self.page_signature_needed:
            if self.page == 0:
                self.page = 1
            translate_page = get_translate("text.page")
            format_string += (
                "\n" * self.page_indent
            ) + f"<b>{translate_page} {self.page}</b>\n"

        format_string += "\n"

        if not self.event_list:
            format_string += if_empty
        else:
            for num, event in enumerate(self.event_list):
                str_date, rel_date, week_date = relatively_string_date(
                    (event.datetime - n_time).days
                )

                days_before = ""
                if "{days_before}" in args:
                    dbe = relatively_string_date(
                        event.days_before_event(request.entity.settings.timezone)
                    )[1]
                    if dbe != rel_date:
                        days_before = f"<b>({dbe})</b>"

                markdown_text = ""
                if "{markdown_text}" in args:
                    markdown_text = add_status_effect(event.text, event.statuses)

                days_before_delete = ""
                if event.removal_time is not None:
                    days_before_delete = get_translate("func.deldate")(
                        event.days_before_delete
                    )

                format_string += (
                    args.format(
                        date=event.date,
                        strdate=str_date,
                        weekday=week_date,
                        reldate=(
                            f"<i><s>({rel_date})</s></i>"
                            if days_before
                            else f"({rel_date})"
                        ),
                        numd=f"{num + 1}",
                        event_id=f"{event.event_id}",
                        statuses=event.string_statuses,
                        markdown_text=markdown_text,
                        days_before=days_before,
                        days_before_delete=days_before_delete,
                        **kwargs,
                        text=event.text,
                    )
                    + "\n"
                )

        self.text = (format_string + ending).strip()
        return self
