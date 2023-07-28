from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlite3 import Error
from typing import Literal

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

import logging
from db.db import SQL
from bot import bot
from lang import get_translate
from utils import markdown
from db.sql_utils import sqlite_format_date, pagination
from time_utils import now_time_strftime, convert_date_format, DayInfo
from user_settings import UserSettings


@dataclass
class Event:
    """
    date: str = "now"
    event_id: int = 0
    status: str = ""
    text: str = ""
    deldate: str = "0"
    """

    date: str = "now"
    event_id: int = 0
    status: str = ""
    text: str = ""
    deldate: str = "0"


class MessageGenerator:
    """
    Класс для заполнения и форматирования сообщений по шаблону
    """

    def __init__(
        self,
        settings: UserSettings,
        date: str = "now",
        event_list: tuple | list[Event, ...] = tuple(),
        reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup(),
    ):
        if date == "now":
            date = now_time_strftime(settings.timezone)
        self.event_list = event_list
        self._date = date
        self._settings = settings
        self.text = ""
        self.reply_markup = deepcopy(reply_markup)

    def get_data(
        self,
        *,
        WHERE: str,
        direction: Literal["ASC", "DESC"] = "DESC",
        prefix: str = "|",
    ):
        """
        Получить [список (кортежей 'строк id',)] по страницам
        """
        data = pagination(
            WHERE=WHERE,
            direction=direction,
        )
        if data:
            first_message = [
                Event(*event)
                for event in SQL(
                    f"""
                SELECT date, event_id, status, text, isdel FROM events 
                WHERE event_id IN ({data[0]}) AND ({WHERE})
                ORDER BY {sqlite_format_date("date")} {direction};"""
                )
            ]

            if self._settings.direction_sql == "ASC":
                first_message = first_message[::-1]
            self.event_list = first_message

            count_columns = 5
            diapason_list = []
            for num, d in enumerate(data):  # Заполняем данные из диапазонов в список
                if int(f"{num}"[-1]) in (0, count_columns):
                    # Разделяем диапазоны в строчки по 5
                    diapason_list.append([])
                diapason_list[-1].append((num + 1, d))  # Номер страницы, id

            if len(diapason_list[0]) != 1:  # Если страниц больше одной
                for i in range(count_columns - len(diapason_list[-1])):
                    # Заполняем пустые кнопки в последнем ряду до 5
                    diapason_list[-1].append((0, 0))

                # Обрезаем до 8 строк кнопок чтобы не было слишком много строк кнопок
                [
                    self.reply_markup.row(
                        *[
                            InlineKeyboardButton(
                                f"{numpage}", callback_data=f"{prefix}{numpage}|{vals}"
                            )
                            if vals
                            else InlineKeyboardButton(" ", callback_data="None")
                            for numpage, vals in row
                        ]
                    )
                    for row in diapason_list[:8]
                ]
        return self

    def get_events(self, WHERE: str, values: list | tuple[str]):
        """
        Возвращает события входящие в values с условием WHERE
        """
        try:
            res = [
                Event(*event)
                for event in SQL(
                    f"""
SELECT date, event_id, status, text, isdel FROM events
WHERE event_id IN ({', '.join(values)}) AND ({WHERE})
ORDER BY {sqlite_format_date('date')} {self._settings.direction_sql};
"""
                )
            ]
        except Error as e:
            logging.info(
                f'[message_generator.py -> MessageGenerator.get_events] Error "{e}"'
            )
            self.event_list = []
        else:
            if self._settings.direction_sql == "ASC":
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
        \n ⠀
        \n {date}     - Date                                                                       ["0000.00.00"]
        \n {strdate}  - String Date                                                                ["0 January"]
        \n {weekday} - Week Date                                                                   ["Понедельник"]
        \n {reldate}  - Relatively Date                                                            ["Завтра"]
        \n ⠀
        \n {numd}     - Порядковый номер (циферный)                                                ["1 2 3"]
        \n {nums}     - Порядковый номер (смайлики)                                                ["1 2 3"]
        \n {event_id} - Event_id                                                                   ["1"]
        \n {status}   - Status                                                                     ["⬜️"]
        \n {markdown_text} - оборачивает текст в нужный тег по статусу                             ["<b>"]
        \n {markdown_text_nourlsub} - оборачивает текст в нужный тег по статусу без сокращения url ["</b>"]
        \n {text}     - Text                                                                       ["text"]
        \n {days_before_delete} - Дней до удаления

        :param title:    Заголовок
        :param args:     Повторяющийся шаблон
        :param ending:   Конец сообщения
        :param if_empty: Если результат запроса пустой
        :return:         message.text
        """

        def days_before_delete(event_deletion_date):
            if event_deletion_date in (0, 1):
                return 30
            else:
                d1 = datetime.utcnow() + timedelta(
                    hours=self._settings.timezone
                )  # Текущая дата у пользователя
                d2 = convert_date_format(event_deletion_date)

                return 30 - (d1 - d2).days

        day = DayInfo(self._settings, self._date)

        format_string = (
            title.format(
                date=day.date,
                strdate=day.str_date,
                weekday=day.week_date,
                reldate=day.relatively_date,
            )
            + "\n"
        )

        if not self.event_list:
            format_string += if_empty
        else:
            for num, event in enumerate(self.event_list):
                day = DayInfo(self._settings, event.date)
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
                        markdown_text=markdown(
                            event.text, event.status, self._settings.sub_urls
                        ),
                        markdown_text_nourlsub=markdown(event.text, event.status),
                        days_before_delete=get_translate(
                            "deldate", self._settings.lang
                        )(days_before_delete(event.deldate)),
                        **kwargs,
                        text=event.text,
                    )
                    + "\n"
                )

        self.text = (format_string + ending).strip()
        return self

    def send(self, chat_id: int) -> Message:
        return bot.send_message(
            chat_id=chat_id, text=self.text, reply_markup=self.reply_markup
        )

    def edit(
        self,
        *,
        chat_id: int,
        message_id: int,
        only_markup: bool = False,
        markup: InlineKeyboardMarkup = None,
    ) -> None:
        """
        :param chat_id: chat_id
        :param message_id: message_id
        :param only_markup: обновить только клавиатуру self.reply_markup
        :param markup: обновить текст self.text и клавиатура markup
        """
        if only_markup:
            bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=self.reply_markup
            )
        elif markup is not None:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self.text,
                reply_markup=markup,
            )
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self.text,
                reply_markup=self.reply_markup,
            )
