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
from todoapi.types import db, Event
from todoapi.utils import sqlite_format_date


def pagination(
    WHERE: str,
    direction: Literal["ASC", "DESC"] = "DESC",
    max_group_len: int = 10,
    max_group_symbols_count: int = 2500,
    max_group_id_len: int = 39,
) -> list[str]:
    """
    :param WHERE: SQL условие
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
"""
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
        self.reply_markup = markup

    def send(self, chat_id: int) -> Message:
        return bot.send_message(
            chat_id=chat_id, text=self.text, reply_markup=self.reply_markup
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
        :param only_markup: обновить только клавиатуру self.reply_markup
        :param markup: обновить текст self.text и клавиатура markup


        bot.edit_message_text(text, chat_id, message_id, reply_markup=self.reply_markup)

        .edit(chat_id, message_id, markup=markup)

        bot.edit_message_reply_markup(self.text, chat_id, message_id, reply_markup=markup)

        .edit(chat_id, message_id, only_markup=True)

        bot.edit_message_text(self.text, chat_id, message_id, reply_markup=self.reply_markup)

        .edit(chat_id, message_id)
        """
        if only_markup:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.reply_markup,
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
                reply_markup=self.reply_markup,
            )

    def reply(self, message):
        bot.reply_to(
            message,
            self.text,
            reply_markup=self.reply_markup,
        )


class EventsMessage(TextMessage):
    """
    Класс для заполнения и форматирования сообщений по шаблону
    """

    def __init__(
        self,
        date: str = "now",
        event_list: tuple | list[Event, ...] = tuple(),
        reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup(),
        page: int = 0,
    ):
        super().__init__("", deepcopy(reply_markup))
        if date == "now":
            date = now_time_strftime()
        self.event_list = event_list
        self._date = date
        self.page = page
        self.page_signature_needed = True if page else False

    def get_data(
        self,
        WHERE: str,
        call_back_func: Callable[[int, str], str],
        column: str = sqlite_format_date("date"),
        direction: Literal["ASC", "DESC"] | None = None,
    ):
        """
        Получить список кортежей строк id по страницам
        """
        if not direction:
            direction = request.user.settings.direction

        data = pagination(WHERE, direction)

        if data:
            first_message = [
                Event(*event)
                for event in db.execute(
                    f"""
SELECT user_id,
       event_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 WHERE event_id IN ({data[0]}) AND 
       ({WHERE}) 
 ORDER BY {column} {direction};
""",
                    func=(
                        "DAYS_BEFORE_EVENT",
                        2,
                        lambda date, status: days_before_event(date, status)[0],
                    )
                    if "DAYS_BEFORE_EVENT" in column
                    else None,
                )
            ]

            if request.user.settings.direction == "ASC":
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
                [
                    self.reply_markup.row(
                        *[
                            InlineKeyboardButton(
                                f"{numpage}",
                                callback_data=call_back_func(numpage, event_ids),
                            )
                            if event_ids
                            else InlineKeyboardButton(" ", callback_data="None")
                            for numpage, event_ids in row
                        ]
                    )
                    for row in page_diapason[:8]
                ]
        return self

    def get_events(self, WHERE: str, values: list | tuple[int | str]):
        """
        Возвращает события входящие в values с условием WHERE
        """
        try:
            res = [
                Event(*event)
                for event in db.execute(
                    f"""
SELECT user_id,
       event_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 WHERE user_id = {request.user.settings.user_id} AND
       event_id IN ({', '.join(str(i) for i in values)}) AND
       ({WHERE}) 
 ORDER BY {sqlite_format_date('date')} {request.user.settings.direction};
""",
                )
            ]
        except Error as e:
            logging.info(
                f'[message_generator.py -> MessageGenerator.get_events] Error "{e}"'
            )
            self.event_list = []
        else:
            if request.user.settings.direction == "ASC":
                res = res[::-1]
            self.event_list = res
        return self

    def format(
        self,
        title: str = "{date} <u><i>{strdate}  {weekday}</i></u> ({reldate})\n",
        args: str = "<b>{numd}.{event_id}.</b>{status}\n{markdown_text}\n",
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

        {nums}     - Порядковый номер (смайлики)                                                ["1 2 3"]

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
                        nums=f"{num + 1}️⃣",  # создание смайлика с цифрой
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
                        if event.removal_time == "0"
                        else get_translate("func.deldate")(event.days_before_delete()),
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
