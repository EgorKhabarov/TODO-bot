from copy import deepcopy
from logger import logger
from sqlite3 import Error
from typing import Literal, Any
from datetime import datetime

# noinspection PyPackageRequirements
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, InputFile

from tgbot.bot import bot
from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.time_utils import relatively_string_date
from tgbot.buttons_utils import encode_id, number_to_power
from tgbot.utils import add_status_effect, get_message_thread_id
from todoapi.exceptions import EventNotFound
from todoapi.types import db, Event


event_formats = {
    "dl": "<b>{numd}.{event_id}.</b>{statuses}\n{markdown_text}\n",
    "dt": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{markdown_text}\n",
    "b": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> ({days_before_delete})\n{markdown_text}\n",
    "r": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> ({reldate}){days_before}\n{markdown_text}\n",
    "s": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u>\n{markdown_text}\n",
    "a": "<b>{date}.{event_id}.</b>{statuses} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n{text}\n",
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


def DAYS_BEFORE_EVENT(date, statuses):
    return Event(0, "", 0, date, "", statuses, "", "", "").days_before_event(
        request.entity.settings.timezone
    )


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
 ORDER BY ABS(DAYS_BEFORE_EVENT(date, statuses)) {direction},
          DAYS_BEFORE_EVENT(date, statuses) DESC
 LIMIT 400;
""",
        params=params,
        func=("DAYS_BEFORE_EVENT", 2, DAYS_BEFORE_EVENT),
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
            chat_id=chat_id or request.chat_id,
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
        :param only_markup: обновить только клавиатуру self.markup
        :param markup: обновить текст self.text и клавиатура markup


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
                chat_id=chat_id or request.chat_id,
                message_id=message_id,
                reply_markup=self.markup,
                **kwargs,
            )
        elif markup is not None:
            bot.edit_message_text(
                text=self.text,
                chat_id=chat_id or request.chat_id,
                message_id=message_id,
                reply_markup=markup,
                **kwargs,
            )
        else:
            bot.edit_message_text(
                text=self.text,
                chat_id=chat_id or request.chat_id,
                message_id=message_id,
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
        document: Any,
        caption: str = None,
        markup: InlineKeyboardMarkup = None,
    ):
        self.document = document
        self.caption = caption
        self.markup = markup

    def send(self, chat_id: int = None, **kwargs):
        bot.send_document(
            chat_id=chat_id or request.chat_id,
            document=InputFile(self.document),
            caption=self.caption,
            message_thread_id=getattr(request.query, "message_thread_id", None),
            **kwargs,
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
            self.event: None = None

    def format(
        self,
        title: str = "",
        event_date_representation: str = "",
        markup: InlineKeyboardMarkup = None,
    ):
        days_before_event = self.event.days_before_event(
            request.entity.settings.timezone
        )
        str_date, rel_date, week_date = relatively_string_date(days_before_event)

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
    Класс для заполнения и форматирования сообщений по шаблону
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

    def get_pages_data(self, WHERE: str, params: dict | tuple, callback_data: str):
        """
        Получить список кортежей строк id по страницам
        """
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
       statuses,
       adding_time,
       recent_changes_time,
       removal_time
  FROM events
 WHERE event_id IN ({data[0]})
       AND ({WHERE}) 
 ORDER BY ABS(DAYS_BEFORE_EVENT(date, statuses)) {direction},
          DAYS_BEFORE_EVENT(date, statuses) DESC,
          statuses LIKE '%📬%',
          statuses LIKE '%🗞%',
          statuses LIKE '%📅%',
          statuses LIKE '%📆%',
          statuses LIKE '%🎉%',
          statuses LIKE '%🎊%';
""",
                    params=params,
                    func=("DAYS_BEFORE_EVENT", 2, DAYS_BEFORE_EVENT),
                )
            ]

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
                            (
                                InlineKeyboardButton(
                                    f"{numpage}{number_to_power(str(len(event_ids.split(','))))}",
                                    callback_data=f"{callback_data.strip()} {numpage} {event_ids}",
                                )
                                if event_ids
                                else InlineKeyboardButton(" ", callback_data="None")
                            )
                            for numpage, event_ids in row
                        ]
                    )
            else:
                self.page_signature_needed = False
        return self

    def get_page_events(self, WHERE: str, params: tuple, id_list: list[int]):
        """
        Возвращает события входящие в values с условием WHERE
        """
        direction = request.entity.settings.direction

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
       AND ({WHERE}) 
 ORDER BY ABS(DAYS_BEFORE_EVENT(date, statuses)) {direction},
          DAYS_BEFORE_EVENT(date, statuses) DESC,
          statuses LIKE '%📬%',
          statuses LIKE '%🗞%',
          statuses LIKE '%📅%',
          statuses LIKE '%📆%',
          statuses LIKE '%🎉%',
          statuses LIKE '%🎊%';
""",
                    params=(
                        request.entity.safe_user_id,
                        request.entity.group_id,
                        *id_list,
                        *params,
                    ),
                    func=("DAYS_BEFORE_EVENT", 2, DAYS_BEFORE_EVENT),
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
        Заполнение сообщения по шаблону

        {date}     - Date                                                                       ["0000.00.00"]

        {strdate}  - String Date                                                                ["0 January"]

        {weekday} - Week Date                                                                   ["Понедельник"]

        {reldate}  - Relatively Date                                                            ["Завтра"]



        {numd}     - Порядковый номер (циферки)                                                 ["1 2 3"]

        {event_id} - Event_id                                                                   ["1"]

        {status}   - Status                                                                     ["⬜"]

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
                        reldate=rel_date,
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
