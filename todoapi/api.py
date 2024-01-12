import csv
import html
import json
import logging
from sqlite3 import Error
from typing import Literal
from io import StringIO, BytesIO
import xml.etree.ElementTree as xml  # noqa

from todoapi.queries import queries
from todoapi.types import Event, UserSettings, Limit, db, export_cooldown
from todoapi.utils import (
    sqlite_format_date,
    is_premium_user,
    is_valid_year,
    is_admin_id,
    re_date,
)


class User:
    def __init__(self, user_id: int | str):
        self.user_id = int(user_id)
        self.settings: UserSettings = UserSettings(user_id)
        self.__no_cooldown = False

    def check_event(
        self, event_id: int, in_wastebasket: bool = False
    ) -> tuple[bool, bool | str]:
        """
        Возвращает есть ли событие в базе данных

        :param event_id:
        :param in_wastebasket:
        """
        if not str(event_id).isdigit():
            return False, ""

        if not isinstance(in_wastebasket, bool):
            return False, ""

        return (
            True,
            bool(
                db.execute(
                    f"""
SELECT 1
  FROM events
 WHERE user_id = ? AND 
       event_id = ?
       {"AND removal_time != 0" if in_wastebasket else ""};
""",
                    params=(
                        self.user_id,
                        event_id,
                    ),
                )
            ),
        )

    @staticmethod
    def check_user(user_id: int) -> tuple[bool, bool]:
        """
        Возвращает есть ли пользователь в базе данных

        :param user_id:
        """
        return (
            True,
            bool(
                db.execute(
                    """
SELECT 1
  FROM settings
 WHERE user_id = ?;
""",
                    params=(user_id,),
                )
            ),
        )

    def check_limit(
        self, date: str | None = None, *, event_count: int = 0, symbol_count: int = 0
    ) -> tuple[bool, bool | str]:
        """
        Проверить лимит.

        :param date:
        :param event_count:
        :param symbol_count:

        "Invalid Date Format" - Формат даты неверный.

        "Wrong Date" - Неверная дата.
        """

        if not re_date.match(date):
            return False, "Invalid Date Format"

        if not is_valid_year(int(date[-4:])):
            return False, "Wrong Date"

        limit = Limit(self.user_id, self.settings.user_status, date)
        return True, limit.is_exceeded(
            event_count=event_count, symbol_count=symbol_count
        )

    def get_limits(
        self, date: str | None = None
    ) -> tuple[bool, list[int, int, int, int, int, int, int, int]]:
        """
        Возвращает список процентов заполнения лимитов для рисования статистики.

        :param date:
        """
        limit = Limit(self.user_id, self.settings.user_status, date)
        return True, limit.now_limit_percent()

    def get_settings(self) -> UserSettings:
        """
        :return:
        """
        return self.settings

    def add_event(self, date: str, text: str) -> tuple[bool, str]:
        """
        Добавить событие.

        :param date: dd.mm.yyyy
        :param text: text

        "Text Is Too Big" - Текст слишком большой.

        "Invalid Date Format" - Формат даты неверный.

        "Wrong Date" - Неверная дата.

        "Limit Exceeded" - Лимит превышен.

        "SQL Error {}" - Ошибка sql.
        """

        if len(text) >= 3800:
            return False, "Text Is Too Big"

        if not re_date.match(date):
            return False, "Invalid Date Format"

        if not is_valid_year(int(date[-4:])):
            return False, "Wrong Date"

        if self.check_limit(date, event_count=1)[1]:
            # max(self.get_limits(date)[1]) >= 100:
            return False, "Limit Exceeded"

        try:
            db.execute(
                queries["insert event"],
                params={
                    "user_id": self.user_id,
                    "date": date,
                    "text": text,
                },
                commit=True,
            )
            db.execute(
                queries["update user_max_event_id"],
                params=(self.user_id,),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"

    def get_event(
        self, event_id: int, in_wastebasket: bool = False
    ) -> tuple[bool, Event | str]:
        """
        Получить одно событие

        :param event_id:
        :param in_wastebasket:
        :return: tuple[bool | Event, str]

        "Wrong id" - Неверный id.

        "SQL Error {}" - Ошибка sql.

        "Events Not Found" - Событие не найдено.
        """
        try:
            event_id = int(event_id)
        except TypeError:
            return False, "Wrong id"

        if 0 >= int(event_id):
            return False, "Wrong id"

        try:
            raw_event = db.execute(
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
 WHERE user_id = ? AND 
       event_id = ? AND
       removal_time {"!" if in_wastebasket else ""}= 0;
""",
                params=(self.user_id, event_id),
            )
        except Error as e:
            return False, f"SQL Error {e}"

        if raw_event:
            return True, Event(*raw_event[0])
        else:
            return False, "Events Not Found"

    def get_events(
        self,
        events_id: list[int] | tuple[int],
        in_wastebasket: bool = False,
        direction: Literal[-1, 1, "DESC", "ASC"] | None = None,
    ) -> tuple[bool, list[Event] | str]:
        """
        Получить события по списку id.

        :param events_id:
        :param in_wastebasket:
        :param direction:

        (events, "") - Успешно.

        'direction must be in [-1, 1, "DESC", "ASC"]' - Неверный direction.

        "SQL Error {}" - Ошибка sql.
        """
        if direction is None:
            direction = self.settings.direction or "DESC"

        if direction in (-1, 1):
            """
            Expected type 'int', got 'Literal[-1, 1, "DESC", "ASC"]' instead
            """
            direction = {-1: "DESC", 1: "ASC"}[direction]

        if direction not in ("DESC", "ASC"):
            return False, 'direction must be in [-1, 1, "DESC", "ASC"]'

        try:
            raw_events = db.execute(
                """
SELECT user_id,
       event_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 WHERE user_id = ? AND 
       event_id IN ({}) AND
       removal_time {}= 0
 ORDER BY {} {};
""".format(
                    ", ".join(str(int(e_id)) for e_id in events_id),
                    ("!" if in_wastebasket else ""),
                    sqlite_format_date("date"),
                    direction,
                ),
                params=(self.user_id,),
            )
            return True, [Event(*raw_event) for raw_event in raw_events if raw_event]
        except Error as e:
            return False, f"SQL Error {e}"

    def edit_event_text(self, event_id: int, text: str) -> tuple[bool, str]:
        """
        Изменить текст события.

        :param event_id:
        :param text:

        "Text Is Too Big" - Текст слишком большой.

        "Event Not Found" - Событие не найдено.

        "Limit Exceeded" - Лимит превышен.

        "SQL Error {}" - Ошибка sql.
        """

        if len(text) >= 3800:
            return False, "Text Is Too Big"

        response, event = self.get_event(event_id)
        if not response:
            return False, "Event Not Found"

        # Вычисляем количество добавленных символов
        _len_text, _len_event_text = len(text), len(event.text)
        new_symbol_count = (
            0 if _len_text < _len_event_text else _len_text - _len_event_text
        )

        if self.check_limit(event.date, symbol_count=new_symbol_count)[1] is True:
            return False, "Limit Exceeded"

        try:
            db.execute(
                queries["update event_text"],
                params=(text, self.user_id, event_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"

    def edit_event_date(self, event_id: int, date: str) -> tuple[bool, str]:
        """
        Изменить дату.

        :param event_id:
        :param date:

        "Invalid Date Format" - Формат даты неверный.

        "Wrong Date" - Неверная дата.

        "Event Not Found" - Событие не найдено.

        "Limit Exceeded" - Лимит превышен.

        "SQL Error {}" - Ошибка sql.
        """

        if not re_date.match(date):
            return False, "Invalid Date Format"

        if not is_valid_year(int(date[-4:])):
            return False, "Wrong Date"

        response, event = self.get_event(event_id)
        if not response:
            return False, "Event Not Found"

        if (
            self.check_limit(date, event_count=1, symbol_count=len(event.text))[1]
            is True
        ):
            return False, "Limit Exceeded"

        try:
            db.execute(
                queries["update event_date"],
                params=(date, self.user_id, event_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"

    def edit_event_status(self, event_id: int, status: str = "⬜️") -> tuple[bool, str]:
        """
        Поставить статус.

        :param event_id:
        :param status:

        "Event Not Found" - Событие не было найдено.

        "Status Conflict" - В статусах есть конфликты.

        "Status Length Exceeded" - Статус слишком большой.

        "Status Repeats" - Статусы повторяются.

        "SQL Error {}" - Ошибка sql.
        """

        if not self.check_event(event_id)[1]:
            return False, "Event Not Found"

        if any(
            [
                st1 in status and st2 in status
                for st1, st2 in (
                    ("🔗", "💻"),
                    ("🪞", "💻"),
                    ("🔗", "⛓"),
                    ("🧮", "🗒"),
                )
            ]
        ):
            return False, "Status Conflict"

        statuses = status.split(",")

        # Статусов не может быть больше 5
        # Длинна одного обычного статуса не может быть больше 3 символов
        # Язык кода не может быть больше 6 символов
        if (
            len(statuses) > 5
            or max(
                # Если длинна больше 6, то сумма булева (>) значения и 3 будет больше 3
                (3 + (len(s.removeprefix("💻")) > 6)) if s.startswith("💻") else len(s)
                for s in statuses
            )
            > 3
        ):
            return False, "Status Length Exceeded"

        if len(statuses) != len(set(statuses)):
            return False, "Status Repeats"

        try:
            db.execute(
                queries["update event_status"],
                params=(status, self.user_id, event_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"

    def delete_event(self, event_id: int, to_bin: bool = False) -> tuple[bool, str]:
        """
        Удалить событие.

        :param event_id:
        :param to_bin:

        "Event Not Found" - Событие не найдено.

        "SQL Error {}" - Ошибка sql.
        """

        if not self.check_event(event_id)[1]:
            return False, "Event Not Found"

        try:
            if is_premium_user(self) and to_bin:
                db.execute(
                    queries["update event_to_trash"],
                    params=(self.user_id, event_id),
                    commit=True,
                )
            else:
                db.execute(
                    queries["delete event"],
                    params=(self.user_id, event_id),
                    commit=True,
                )
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"

    def recover_event(self, event_id: int) -> tuple[bool, str]:
        """
        Восстановить событие из корзины.

        :param event_id:

        "Event Not Found" - Событие не найдено.

        "SQL Error {}" - Ошибка sql.
        """

        if not self.check_event(event_id, True)[1]:
            return False, "Event Not Found"

        try:
            db.execute(
                queries["update restore_events"],
                params=(self.user_id, event_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"

    def clear_basket(self) -> tuple[bool, str]:
        """
        Очистить корзину.

        "SQL Error {}" - Ошибка sql.
        """

        try:
            db.execute(
                queries["delete deleted_events"],
                params=(self.user_id,),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"

    def export_data(
        self, file_name: str, file_format: str = "csv"
    ) -> tuple[bool, StringIO | str]:
        """
        Экспортировать в csv.

        :param file_name:
        :param file_format:

        "Format Is Not Valid" - Невалидный формат файла.

        "Wait {t // 60} min" - Слишком часто запрашивали ждите x минут.

        "SQL Error {}" - Ошибка sql.
        """

        if file_format not in ("csv", "xml", "json", "jsonl"):
            return False, "Format Is Not Valid"

        if self.__no_cooldown:
            response, t = True, 0
            self.__no_cooldown = False
        else:
            response, t = export_cooldown.check(self.user_id, False)

        if response:

            def export_csv() -> tuple[bool, StringIO | str]:
                file = StringIO()
                file.name = file_name

                try:
                    table: list[tuple[int, str, str, str], ...] = db.execute(
                        queries["select all_events"],
                        params=(self.user_id,),
                        column_names=True,
                    )
                except Error as e:
                    return False, f"SQL Error {e}"

                file_writer = csv.writer(file)
                [
                    file_writer.writerows(
                        [
                            [
                                str(event_id),
                                event_date,
                                event_status,
                                html.unescape(event_text),
                            ]
                        ]
                    )
                    for event_id, event_date, event_status, event_text in table
                ]
                file.seek(0)
                return True, file

            def export_xml() -> tuple[bool, BytesIO | str]:
                file = BytesIO()
                file.name = file_name

                try:
                    table: list[tuple[int, str, str, str], ...] = db.execute(
                        queries["select all_events"],
                        params=(self.user_id,),
                    )
                except Error as e:
                    return False, f"SQL Error {e}"

                xml_events = xml.Element("events")
                for event_id, date, status, text in table:
                    xml_event = xml.SubElement(xml_events, "event")
                    xml.SubElement(xml_event, "event_id").text = str(event_id)
                    xml.SubElement(xml_event, "date").text = date
                    xml.SubElement(xml_event, "status").text = status
                    xml.SubElement(xml_event, "text").text = text
                    xml.indent(xml_event, space="  ")

                tree = xml.ElementTree(xml_events)
                xml.indent(tree, space="  ")
                # noinspection PyTypeChecker
                tree.write(
                    file,
                    encoding="UTF-8",
                    method="xml",
                    xml_declaration=False,
                    short_empty_elements=False,
                )

                file.seek(0)
                return True, file

            def export_json() -> tuple[bool, StringIO | str]:
                file = StringIO()
                file.name = file_name

                try:
                    table: list[tuple[int, str, str, str], ...] = db.execute(
                        queries["select all_events"],
                        params=(self.user_id,),
                    )
                except Error as e:
                    return False, f"SQL Error {e}"

                # event_id, date, status, text
                d = tuple(
                    {
                        "event_id": event[0],
                        "date": event[1],
                        "status": event[2],
                        "text": event[3],
                    }
                    for event in table
                )

                if file_format == "json":
                    file.write(json.dumps(d, indent=4, ensure_ascii=False))
                else:
                    file.writelines(
                        json.dumps(line, ensure_ascii=False) + "\n" for line in d
                    )

                file.seek(0)
                return True, file

            match file_format:
                case "csv":
                    return export_csv()
                case "xml":
                    return export_xml()
                case x if x in ("json", "jsonl"):
                    return export_json()
                case _:
                    return False, "SQL Error"
        else:
            return False, f"Wait {t // 60} min"

    def set_settings(
        self,
        lang: Literal["ru", "en"] = None,
        sub_urls: Literal[0, 1] = None,
        city: str = None,
        timezone: int = None,
        direction: Literal["DESC", "ASC"] = None,
        user_status: Literal[-1, 0, 1, 2] = None,
        notifications: Literal[0, 1] | bool = None,
        notifications_time: str = None,
        theme: int = None,
    ) -> tuple[bool, str]:
        """
        Установить настройку.

        'lang must be in ["ru", "en"]'

        "sub_urls must be in [0, 1]"

        "length city must be less than 50 characters"

        "timezone must be -12 and less 12"

        'direction must be in ["DESC", "ASC"]'

        "user_status must be in [-1, 0, 1, 2]"

        "notifications must be in [0, 1]"

        "hour must be more -1 and less 24"

        "minute must be in [0, 10, 20, 30, 40, 50]"

        "theme must be in [0, 1]"

        "SQL Error {}" - Ошибка sql.
        """
        update_list = []

        if lang is not None:
            if lang not in ("ru", "en"):
                return False, 'lang must be in ["ru", "en"]'

            update_list.append("lang")
            self.settings.lang = lang

        if sub_urls is not None:
            if sub_urls not in (0, 1, "0", "1"):
                return False, "sub_urls must be in [0, 1]"

            update_list.append("sub_urls")
            self.settings.sub_urls = int(sub_urls)

        if city is not None:
            if len(city) > 50:
                return False, "length city must be less than 50 characters"

            update_list.append("city")
            self.settings.city = city

        if timezone is not None:
            if timezone not in [j for i in range(-11, 12) for j in (i, str(i))]:
                return False, "timezone must be -12 and less 12"

            update_list.append("timezone")
            self.settings.timezone = int(timezone)

        if direction is not None:
            if direction not in ("DESC", "ASC"):
                return False, 'direction must be in ["DESC", "ASC"]'

            update_list.append("direction")
            self.settings.direction = direction

        if user_status is not None:
            if user_status not in (-1, 0, 1, 2, "-1", "0", "1", "2"):
                return False, "user_status must be in [-1, 0, 1, 2]"

            update_list.append("user_status")
            self.settings.user_status = int(user_status)

        if notifications is not None:
            if notifications not in (1, 0, "1", "0", True, False):
                return False, "notifications must be in [0, 1]"

            update_list.append("notifications")
            self.settings.notifications = int(notifications)

        if notifications_time is not None:
            hour, minute = [int(v) for v in notifications_time.split(":")]
            if not -1 < hour < 24:
                return False, "hour must be more -1 and less 24"

            if minute not in (0, 10, 20, 30, 40, 50):
                return False, "minute must be in [0, 10, 20, 30, 40, 50]"

            update_list.append("notifications_time")
            self.settings.notifications_time = notifications_time

        if theme is not None:
            if theme not in (0, 1, "0", "1"):
                return False, "theme must be in [0, 1]"

            update_list.append("theme")
            self.settings.theme = int(theme)

        try:
            db.execute(
                """
UPDATE settings
   SET {}
 WHERE user_id = :user_id;
""".format(
                    ", ".join(f"{update} = :{update}" for update in update_list)
                ),
                params={
                    "lang": lang,
                    "city": city,
                    "theme": theme,
                    "sub_urls": sub_urls,
                    "timezone": timezone,
                    "direction": direction,
                    "user_status": user_status,
                    "notifications": notifications,
                    "notifications_time": notifications_time,
                    "user_id": self.user_id,
                },
                commit=True,
            )
        except Error as e:
            return False, f"SQL Error {e}"

        return True, ""

    def delete_user(
        self, user_id: int
    ) -> tuple[bool, StringIO | str | tuple[str, StringIO]]:
        """
        Удалить все данные пользователя.

        :param user_id:

        "User Not Exist" - Пользователь не существует.

        "Not Enough Authority" - Недостаточно прав.

        "Unable To Remove Administrator" - Нельзя удалить администратора.

        "CSV Error" - Не получилось получить csv файл.

        ("SQL Error {}", csv_file) - Ошибка при удалении.
        """
        is_self = self.user_id == user_id

        # Когда ты не админ и пытаешься удалить другого человека
        if not is_admin_id(self.user_id) and not is_self:
            return False, "Not Enough Authority"

        if is_admin_id(user_id):
            return False, "Unable To Remove Administrator"

        if not self.check_user(user_id)[1]:
            return False, "User Not Exist"

        tmp_user = User(user_id)
        tmp_user.__no_cooldown = True
        response, csv_file = tmp_user.export_data(f"{user_id}.csv")
        if not response:
            logging.info(f"CSV Error {csv_file}")
            return False, "CSV Error"

        try:
            db.execute(
                queries["delete settings"],
                params=(user_id,),
                commit=True,
            )
            db.execute(
                queries["delete all_events"],
                params=(user_id,),
                commit=True,
            )
        except Error as e:
            return False, (f"SQL Error {e}", csv_file)

        return True, csv_file

    def set_user_status(
        self, user_id: int, status: Literal[-1, 0, 1, 2] = 0
    ) -> tuple[bool, str]:
        """
        Поставить статус пользователю.

        :param user_id:
        :param status:

        "User Not Exist" - Пользователь не существует.

        "Not Enough Authority" - Недостаточно прав.

        "Invalid status" - Неверный статус.

        "Cannot be reduced in admin rights" - Нельзя понизить администратора.

        "SQL Error {}" - Ошибка sql.
        """

        if not is_admin_id(self.user_id):
            return False, "Not Enough Authority"

        if is_admin_id(user_id):
            return False, "Cannot be reduced in admin rights"

        if status not in (-1, 0, 1, 2, "-1", "0", "1", "2"):
            # TODO Убрать статус 2.
            #  Пусть админом можно будет стать только вставив его id в config
            return False, "Invalid status"

        if not self.check_user(user_id)[1]:
            return False, "User Not Exist"

        try:
            db.execute(
                queries["update user_status"],
                params=(status, user_id),
                commit=True,
            )
            self.settings.user_status = status
            return True, ""
        except Error as e:
            return False, f"SQL Error {e}"
