import logging
from copy import deepcopy
from sqlite3 import Error
from typing import Literal
from datetime import datetime, timedelta

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from tgbot.bot import bot
from tgbot.utils import markdown
from tgbot.lang import get_translate
from tgbot.sql_utils import sqlite_format_date, pagination
from tgbot.time_utils import now_time_strftime, DayInfo, convert_date_format, now_time
from todoapi.types import db, UserSettings, Event


class EventMessageGenerator:
    """
    Класс для заполнения и форматирования сообщений по шаблону
    """

    def __init__(
        self,
        settings: UserSettings,
        date: str = "now",
        event_list: tuple | list[Event, ...] = tuple(),
        reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup(),
        page: int = 0,
    ):
        if date == "now":
            date = now_time_strftime(settings.timezone)
        self.event_list = event_list
        self._date = date
        self._settings = settings
        self.text = ""
        self.reply_markup = deepcopy(reply_markup)
        self.page = page
        self.page_signature_needed = True if page else False

    def get_data(
        self,
        *,
        WHERE: str,
        direction: Literal["ASC", "DESC"] = "DESC",
        prefix: str = "|",
    ):
        """
        Получить список кортежей строк id по страницам
        """
        data = pagination(
            WHERE=WHERE,
            direction=direction,
        )
        if data:
            first_message = [
                Event(*event)
                for event in db.execute(
                    f"""
SELECT event_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 WHERE event_id IN ({data[0]}) AND 
       ({WHERE}) 
 ORDER BY {sqlite_format_date("date")} {direction};
""",
                )
            ]

            if self._settings.direction == "ASC":
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
                self.page_signature_needed = True
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
                for event in db.execute(
                    f"""
SELECT event_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 WHERE event_id IN ({', '.join(values)}) AND 
       ({WHERE}) 
 ORDER BY {sqlite_format_date('date')} {self._settings.direction};
""",
                )
            ]
        except Error as e:
            logging.info(
                f'[message_generator.py -> MessageGenerator.get_events] Error "{e}"'
            )
            self.event_list = []
        else:
            if self._settings.direction == "ASC":
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

        def days_before(event_date: str, event_status: str) -> str:
            """
            В сообщении уведомления показывает через сколько будет повторяющееся событие.
            """
            _date = convert_date_format(event_date)
            now_t = now_time(self._settings.timezone)
            dates = []

            # Каждый день
            if "📬" in event_status:
                _day = DayInfo(self._settings, f"{now_t:%d.%m.%Y}")
                return _day.relatively_date

            # Каждую неделю
            if "🗞" in event_status:
                now_wd, event_wd = now_t.weekday(), _date.weekday()
                next_date = now_t + timedelta(days=(event_wd - now_wd + 7) % 7)
                dates.append(next_date)

            # Каждый месяц
            elif "📅" in event_status:
                _day = DayInfo(self._settings, f"{_date:%d}.{now_t:%m.%Y}")
                month, year = _day.datetime.month, _day.datetime.year
                if _day.day_diff >= 0:
                    dates.append(_day.datetime)
                else:
                    if month < 12:
                        dates.append(_day.datetime.replace(month=month + 1))
                    else:
                        dates.append(_day.datetime.replace(year=year + 1, month=1))

            # Каждый год
            elif {*event_status.split(",")}.intersection({"📆", "🎉", "🎊"}):
                _day = DayInfo(self._settings, f"{_date:%d.%m}.{now_t:%Y}")
                if _day.datetime.date() < now_t.date():
                    dates.append(_day.datetime.replace(year=now_t.year + 1))
                else:
                    dates.append(_day.datetime.replace(year=now_t.year))

            else:
                return DayInfo(self._settings, event_date).relatively_date

            return DayInfo(self._settings, f"{min(dates):%d.%m.%Y}").relatively_date

        def days_before_delete(event_deletion_date: str) -> int:
            if event_deletion_date == "0":
                return 30
            else:
                # Текущая дата у пользователя
                d1 = datetime.utcnow() + timedelta(hours=self._settings.timezone)
                d2 = datetime(*[int(i) for i in event_deletion_date.split("-")])

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
        if self.page_signature_needed:
            if self.page == 0:
                self.page = 1
            translate_page = get_translate("text.page", self._settings.lang)
            format_string += f"<b>{translate_page} {self.page}</b>\n"

        format_string += "\n"

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
                            event.text,
                            event.status,
                            self._settings.sub_urls,
                            self._settings.theme,
                        )
                        if "{markdown_text" in args
                        else "",
                        days_before=f"({dbd})"
                        if (
                            (
                                dbd := (
                                    days_before(event.date, event.status)
                                    if "{days_before" in args
                                    else ""
                                )
                            )
                            != day.relatively_date
                        )
                        else "",
                        days_before_delete=""
                        if event.removal_time == "0"
                        else get_translate("deldate", self._settings.lang)(
                            days_before_delete(event.removal_time)
                        ),
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


class NoEventMessage:
    def __init__(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup(),
    ):
        self.text = text
        self.reply_markup = reply_markup

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


class CallBackAnswer:
    def __init__(self, text: str):
        self.text = text

    def answer(
        self, call_id: int, show_alert: bool | None = None, url: str | None = None
    ):
        bot.answer_callback_query(call_id, self.text, show_alert, url)