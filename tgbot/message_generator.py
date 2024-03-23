import logging
from copy import deepcopy
from sqlite3 import Error
from typing import Literal, Callable

# noinspection PyPackageRequirements
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from tgbot.bot import bot
from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.buttons_utils import encode_id
from tgbot.time_utils import now_time_strftime, DayInfo
from tgbot.utils import add_status_effect, days_before_event
from todoapi.exceptions import EventNotFound
from todoapi.types import db, Event
from todoapi.utils import sqlite_format_date


event_formats = {
    "dl": "<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n",
    "dt": "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
    "b": "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({days_before_delete})\n{markdown_text}\n",
    "r": "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n",
    "s": "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u>\n{markdown_text}\n",
    "a": "<b>{date}.{event_id}.</b>{status} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{text}\n",
}
"""
"dl" - Шаблон для событий на один день
"dt" - Шаблон для событий на разные дни
"b" - Шаблон для корзины, показывает количество дней до уделения события
"r" - Шаблон для событий которые могут повторяться,
      показывает количество дней до следующего повторения
"s" - Шаблон для показа событий, без относительных дат
"a" - Шаблон для показа сообщения о событии, без markdown разметки
"""


def pagination(
    WHERE: str,
    params: dict,
    direction: Literal["ASC", "DESC"] = "DESC",
    max_group_len: int = 10,
    max_group_symbols_count: int = 2500,
    max_group_id_len: int = 39,
) -> list[str]:
    """
    :param WHERE: SQL условие
    :param params: параметры
    :param direction: Направление сортировки
    :param max_group_len: Максимальное количество элементов на странице
    :param max_group_symbols_count: Максимальное количество символов на странице
    :param max_group_id_len: Максимальная длинна сокращённого id
    Количество данных в кнопке ограничено 64 символами
    """

    data = db.execute(
        f"""
SELECT event_id,
       LENGTH(text) 
  FROM events
 WHERE {WHERE}
 ORDER BY {sqlite_format_date('date')} {direction}
 LIMIT 400;
""",
        params=params,
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
    def __init__(
        self,
        text: str | None = None,
        markup: InlineKeyboardMarkup | None = None,
    ):
        self.text = text
        self.markup = markup

    def send(self, chat_id: int) -> Message:
        return bot.send_message(
            chat_id=chat_id,
            text=self.text,
            reply_markup=self.markup,
            message_thread_id=getattr(request.query, "message_thread_id", None),
        )

    def edit(
        self,
        chat_id: int,
        message_id: int,
        *,
        only_markup: bool = False,
        markup: InlineKeyboardMarkup = None,
    ) -> None:
        """
        :param chat_id: chat_id
        :param message_id: message_id
        :param only_markup: обновить только клавиатуру self.markup
        :param markup: обновить текст self.text и клавиатура markup


        bot.edit_message_text(text, chat_id, message_id, reply_markup=self.markup)

        .edit(chat_id, message_id, markup=markup)

        bot.edit_message_reply_markup(self.text, chat_id, message_id, reply_markup=markup)

        .edit(chat_id, message_id, only_markup=True)

        bot.edit_message_text(self.text, chat_id, message_id, reply_markup=self.markup)

        .edit(chat_id, message_id)
        """
        if only_markup:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.markup,
            )
        elif markup is not None:
            bot.edit_message_text(
                text=self.text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
            )
        else:
            bot.edit_message_text(
                text=self.text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.markup,
            )

    def reply(self, message):
        bot.reply_to(
            message=message,
            text=self.text,
            reply_markup=self.markup,
            message_thread_id=getattr(request.query, "message_thread_id", None),
        )


class EventMessage(TextMessage):
    """
    Класс для взаимодействия с одним событием
    """

    def __init__(self, event_id: int, in_wastebasket: bool = False):
        super().__init__()
        self.event_id = event_id
        try:
            self.event: Event = request.entity.get_event(event_id, in_wastebasket)
        except EventNotFound:
            self.event: Event | None = None

    def format(
        self,
        title: str = "",
        event_date_representation: str = "",
        markup: InlineKeyboardMarkup = None,
    ):
        day = DayInfo(self.event.date)
        event_date_representation = event_date_representation.format(
            date=day.date,
            strdate=day.str_date,
            weekday=day.week_date,
            reldate=day.relatively_date,
            event_id=f"{self.event.event_id}",
            status=self.event.status,
            markdown_text=add_status_effect(self.event.text, self.event.status)
            if "{markdown_text" in event_date_representation
            else "",
            days_before=f"<b>({dbd})</b>"
            if (
                (
                    dbd := (
                        days_before_event(self.event.date, self.event.status)[-1]
                        if "{days_before" in event_date_representation
                        else ""
                    )
                )
                != day.relatively_date
            )
            else "",
            days_before_delete=""
            if self.event.removal_time is None
            else get_translate("func.deldate")(self.event.days_before_delete),
            text=self.event.text,
        )
        self.text = f"<b>{title}</b>\n{event_date_representation}".strip()
        self.markup = markup
        return self


class EventsMessage(TextMessage):
    """
    Класс для заполнения и форматирования сообщений по шаблону
    """

    def __init__(
        self,
        date: str = "now",
        event_list: tuple | list[Event, ...] = tuple(),
        markup: InlineKeyboardMarkup = None,
        page: int = 0,
    ):
        if markup is ...:
            markup = InlineKeyboardMarkup()
        super().__init__("", deepcopy(markup))
        if date == "now":
            date = now_time_strftime()
        self.event_list = event_list
        self._date = date
        self.page = page
        self.page_signature_needed = True if page else False

    def get_pages_data(
        self,
        WHERE: str,
        params: dict,
        callback_data: Callable[[int, str], str],
        column: str = sqlite_format_date("date"),
        direction: Literal["ASC", "DESC"] | None = None,
    ):
        """
        Получить список кортежей строк id по страницам
        """
        if not direction:
            direction = request.entity.settings.direction

        data = pagination(WHERE, params, direction)

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
       status,
       adding_time,
       recent_changes_time,
       removal_time
  FROM events
 WHERE event_id IN ({data[0]}) AND 
       ({WHERE}) 
 ORDER BY {column} {direction};
""",
                    params=params,
                    func=(
                        "DAYS_BEFORE_EVENT",
                        2,
                        lambda date, status: days_before_event(date, status)[0],
                    )
                    if "DAYS_BEFORE_EVENT" in column
                    else None,
                )
            ]

            if request.entity.settings.direction == "ASC":
                first_message = first_message[::-1]
            self.event_list = first_message

            count_columns = 5
            page_diapason: list[list[tuple[int, str]]] = []
            for num, d in enumerate(data):  # Заполняем данные из диапазонов в список
                if int(f"{num}"[-1]) in (0, count_columns):
                    # Разделяем диапазоны в строчки по 5
                    page_diapason.append([])
                # Номер страницы, id
                page_diapason[-1].append(
                    (num + 1, encode_id([int(i) for i in d.split(",")]))
                )

            if len(page_diapason[0]) != 1:  # Если страниц больше одной
                self.page_signature_needed = True
                for i in range(count_columns - len(page_diapason[-1])):
                    # Заполняем пустые кнопки в последнем ряду до 5
                    page_diapason[-1].append((0, ""))

                # Обрезаем до 8 строк кнопок чтобы не было слишком много строк кнопок
                for row in page_diapason[:8]:
                    self.markup.row(
                        *[
                            InlineKeyboardButton(
                                f"{numpage}",
                                callback_data=callback_data(numpage, event_ids),
                            )
                            if event_ids
                            else InlineKeyboardButton(" ", callback_data="None")
                            for numpage, event_ids in row
                        ]
                    )
        return self

    def get_page_events(self, WHERE: str, params: dict, id_list: list[int]):
        """
        Возвращает события входящие в values с условием WHERE
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
       status,
       adding_time,
       recent_changes_time,
       removal_time
  FROM events
 WHERE (user_id IS :user_id AND group_id IS :group_id)
       AND event_id IN ({', '.join(f"{event_id}" for event_id in id_list)}) AND
       ({WHERE}) 
 ORDER BY {sqlite_format_date('date')} {request.entity.settings.direction};
""",
                    params=params,
                )
            ]
        except Error as e:
            logging.info(
                f'[message_generator.py -> MessageGenerator.get_events] Error "{e}"'
            )
            self.event_list = []
        else:
            if request.entity.settings.direction == "ASC":
                res = res[::-1]
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
        Заполнение сообщения по шаблону

        {date}     - Date                                                                       ["0000.00.00"]

        {strdate}  - String Date                                                                ["0 January"]

        {weekday} - Week Date                                                                   ["Понедельник"]

        {reldate}  - Relatively Date                                                            ["Завтра"]



        {numd}     - Порядковый номер (циферки)                                                 ["1 2 3"]

        {event_id} - Event_id                                                                   ["1"]

        {status}   - Status                                                                     ["⬜️"]

        {markdown_text} - оборачивает текст в нужный тег по статусу                             ["<b>"]

        {text}     - Text                                                                       ["text"]

        {days_before_delete} - Дней до удаления

        {days_before} - (Дней до)

        :param title:    Заголовок
        :param args:     Повторяющийся шаблон
        :param ending:   Конец сообщения
        :param if_empty: Если результат запроса пустой
        :return:         message.text
        """

        day = DayInfo(self._date)

        format_string = (
            title.format(
                date=day.date,
                strdate=day.str_date,
                weekday=day.week_date,
                reldate=day.relatively_date,
            )
            + "\n"
        )
        if self.page_signature_needed:
            if self.page == 0:
                self.page = 1
            translate_page = get_translate("text.page")
            format_string += f"<b>{translate_page} {self.page}</b>\n"

        format_string += "\n"

        if not self.event_list:
            format_string += if_empty
        else:
            for num, event in enumerate(self.event_list):
                day = DayInfo(event.date)
                format_string += (
                    args.format(
                        date=day.date,
                        strdate=day.str_date,
                        weekday=day.week_date,
                        reldate=day.relatively_date,
                        numd=f"{num + 1}",
                        event_id=f"{event.event_id}",
                        status=event.status,
                        markdown_text=add_status_effect(event.text, event.status)
                        if "{markdown_text" in args
                        else "",
                        days_before=f"<b>({dbd})</b>"
                        if (
                            (
                                dbd := (
                                    days_before_event(event.date, event.status)[-1]
                                    if "{days_before" in args
                                    else ""
                                )
                            )
                            != day.relatively_date
                        )
                        else "",
                        days_before_delete=""
                        if event.removal_time is None
                        else get_translate("func.deldate")(event.days_before_delete),
                        **kwargs,
                        text=event.text,
                    )
                    + "\n"
                )

        self.text = (format_string + ending).strip()
        return self


class CallBackAnswer:
    def __init__(self, text: str):
        self.text = text

    def answer(
        self, call_id: int, show_alert: bool | None = None, url: str | None = None
    ):
        bot.answer_callback_query(call_id, self.text, show_alert, url)
