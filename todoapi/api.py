import csv
import re
from io import StringIO
from sqlite3 import Error
from typing import Literal

from todoapi.utils import (
    html_to_markdown,
    to_html_escaping,
    remove_html_escaping,
    is_admin_id,
    sqlite_format_date,
    is_premium_user,
)
from todoapi.types import Event, UserSettings, Limit, db, export_cooldown

re_date = re.compile(r"\A\d{2}\.\d{2}\.\d{4}\Z")


class User:
    def __init__(self, user_id: int | str, settings: UserSettings = None):
        self.user_id = int(user_id)
        self.settings: UserSettings = settings or UserSettings(user_id)

    def check_event(self, event_id: int, in_wastebasket: bool = False) -> bool:
        """
        Возвращает есть ли событие в базе данных

        :param event_id:
        :param in_wastebasket:
        """
        return bool(
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
        )

    def check_user(self, user_id: int) -> bool:
        """
        Возвращает есть ли пользователь в базе данных

        :param user_id:
        """
        return bool(
            db.execute(
                """
SELECT 1
  FROM settings
 WHERE user_id = ?;
""",
                params=(
                    user_id,
                ),
            )
        )

    def get_limits(
        self, date: str | None = None
    ) -> list[int, int, int, int, int, int, int, int]:
        """
        Возвращает список процентов заполнения лимитов для рисования статистики.

        :param date:
        """
        limit = Limit(self.user_id, self.settings.user_status, date)
        return limit.now_limit_percent()

    def check_limit(
        self, date: str | None = None, *, event_count: int = 0, symbol_count: int = 0
    ) -> bool:
        """
        Проверить лимит.

        :param date:
        :param event_count:
        :param symbol_count:
        """
        limit = Limit(self.user_id, self.settings.user_status, date)
        return limit.is_exceeded(event_count=event_count, symbol_count=symbol_count)

    def get_event(
        self, event_id: int, in_wastebasket: bool = False
    ) -> tuple[bool | Event, str]:
        """
        Получить одно событие

        :param event_id:
        :param in_wastebasket:

        (event, "") - Успешно.

        (False, "Неверный id") - Неверный id.

        (False, f"{Error}") - Ошибка sql.

        (False, "Events Not Found") - Событие не найдено.
        """
        if 0 >= int(event_id):
            return False, "Неверный id"

        try:
            raw_event = db.execute(
                f"""
SELECT event_id,
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
            return False, f"{e}"

        if raw_event:
            event = Event(*raw_event[0])
            return event, ""
        else:
            return False, "Events Not Found"

    def get_events(
        self,
        events_id: list | tuple[int, ...],
        direction: Literal[-1, 1, "DESC", "ASC"] = -1,
    ) -> tuple[list[Event] | bool, str]:
        """
        Получить события по списку id.

        :param events_id:
        :param direction:

        (events, "") - Успешно.

        (False, 'direction must be in [-1, 1, "DESC", "ASC"]') - Неверный direction.

        (False, f"{Error}") - Ошибка sql.
        """
        if direction in (-1, 1):
            direction = {-1: "DESC", 1: "ASC"}[direction]

        if direction not in ("DESC", "ASC"):
            return False, 'direction must be in [-1, 1, "DESC", "ASC"]'

        try:
            raw_events = db.execute(
                """
SELECT event_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 WHERE user_id = ? AND
       event_id IN ({})
 ORDER BY {} {};
""".format(
                    ", ".join(str(int(e_id)) for e_id in events_id),
                    sqlite_format_date("date"),
                    direction,
                ),
                params=(self.user_id,),
            )
            events = [Event(*raw_event) for raw_event in raw_events if raw_event]
            return events, ""
        except Error as e:
            return False, f"{e}"

    def get_settings(self) -> UserSettings:
        """
        :return: json settings
        """
        return self.settings

    def add_event(self, date: str, text: str) -> tuple[bool, str]:
        """
        Добавить событие.

        :param date: dd.mm.yyyy
        :param text: text

        (True, "") - Успешно.

        (False, "Text Is Too Big") - Текст слишком большой.

        (False, "Wrong Date") - Неверная дата.

        (False, "Limit Exceeded") - Лимит превышен.

        (False, f"{Error}") - Ошибка sql.
        """
        if len(text) >= 3800:
            return False, "Text Is Too Big"

        # Неверный формат или не входит в диапазон
        if not re_date.match(date) or not 1980 < int(date[-4:]) < 3000:
            return False, "Wrong Date"

        if max(self.get_limits(date)) >= 100:
            return False, "Limit Exceeded"

        try:
            db.execute(
                """
INSERT INTO events (
event_id,
user_id,
date,
text
)
VALUES (
    COALESCE(
        (
            SELECT user_max_event_id
              FROM settings
             WHERE user_id = :user_id
        ),
        1
    ),
    :user_id,
    :date,
    :text
);
""",
                params={
                    "user_id": self.user_id,
                    "date": date,
                    "text": to_html_escaping(html_to_markdown(text)),
                },
                commit=True,
            )
            db.execute(
                """
UPDATE settings
SET user_max_event_id = user_max_event_id + 1
WHERE user_id = ?;
""",
                params=(self.user_id,),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"{e}"

    def edit_event(self, event_id: int, text: str) -> tuple[bool, str]:
        """
        Изменить текст события.

        :param event_id:
        :param text:

        (True, "") - Успешно.

        (False, "Text Is Too Big") - Текст слишком большой.

        (False, "Event Not Found") - Событие не найдено.

        (False, "Limit Exceeded") - Лимит превышен.

        (False, f"{e}") - Ошибка sql.
        """
        if len(text) >= 3800:
            return False, "Text Is Too Big"

        event = self.get_event(event_id)[0]
        if not event:
            return False, "Event Not Found"

        # Вычисляем количество добавленных символов
        new_symbol_count = (
            0 if len(text) < len(event.text) else len(text) - len(event.text)
        )
        if self.check_limit(event.date, symbol_count=new_symbol_count):
            return False, "Limit Exceeded"

        try:
            db.execute(
                """
UPDATE events
   SET text = :text
 WHERE user_id = :user_id AND 
       event_id = :event_id;
""",
                params={
                    "user_id": self.user_id,
                    "event_id": event_id,
                    "text": to_html_escaping(html_to_markdown(text)),
                },
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"{e}"

    def delete_event(self, event_id: int, to_bin: bool = False) -> tuple[bool, str]:
        """
        Удалить событие.

        :param event_id:
        :param to_bin:

        (True, "") - Успешно.

        (False, "Event Not Found") - Событие не найдено.

        (False, f"{e}") - Ошибка sql.
        """
        if not self.check_event(event_id):
            return False, "Event Not Found"

        try:
            if is_premium_user(self) and to_bin:
                db.execute(
                    """
UPDATE events
   SET removal_time = DATE() 
 WHERE user_id = ? AND 
       event_id = ?;
""",
                    params=(self.user_id, event_id),
                    commit=True,
                )
            else:
                db.execute(
                    """
DELETE FROM events
      WHERE user_id = ? AND 
            event_id = ?;
""",
                    params=(self.user_id, event_id),
                    commit=True,
                )
            return True, ""
        except Error as e:
            return False, f"{e}"

    def edit_event_date(self, event_id: int, date: str) -> tuple[bool, str]:
        """
        Изменить дату.

        :param event_id:
        :param date:

        (True, "") - Успешно.

        (False, "Invalid Date Format") - Формат даты неверный.

        (False, "Event Not Found") - Событие не найдено.

        (False, f"{Error}") - Ошибка sql.
        """
        date_format = re.compile("\d{2}\.\d{2}\.\d{4}")

        if not date_format.match(date):
            return False, "Invalid Date Format"

        if not self.check_event(event_id):
            return False, "Event Not Found"

        try:
            db.execute(
                """
UPDATE events
   SET date = ?
 WHERE user_id = ? AND
       event_id = ?;
""",
                params=(date, self.user_id, event_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"{e}"

    def recover_event(self, event_id: int) -> tuple[bool, str]:
        """
        Восстановить событие из корзины.

        :param event_id:

        (True, "") - Успешно.

        (False, "Event Not Found") - Событие не найдено.

        (False, f"{Error}") - Ошибка sql.
        """
        if not self.check_event(event_id, True):
            return False, "Event Not Found"

        try:
            db.execute(
                """
UPDATE events
   SET removal_time = 0
 WHERE user_id = ? AND 
       event_id = ?;
""",
                params=(self.user_id, event_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"{e}"

    def set_status(self, event_id: int, status: str = "⬜️") -> tuple[bool, str]:
        """
        Поставить статус.

        :param event_id:
        :param status:

        (True, "") - Успешно.

        (False, "Event Not Found") - Событие не было найдено.

        (False, "Status Conflict") - В статусах есть конфликты.

        (False, "Status Length Exceeded") - Статус слишком большой.

        (False, "Status Repeats") - Статусы повторяются.

        (False, f"{Error}") - Ошибка sql.
        """
        if not self.check_event(event_id):
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
        if len(statuses) > 5 or max(len(s) for s in statuses) > 3:
            return False, "Status Length Exceeded"

        if len(statuses) != len(set(statuses)):
            return False, "Status Repeats"

        try:
            db.execute(
                """
UPDATE events
   SET status = ?
 WHERE user_id = ? AND 
       event_id = ?;
""",
                params=(status, self.user_id, event_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"{e}"

    def clear_basket(self) -> tuple[bool, str]:
        """
        Очистить корзину.

        (True, "") - Успешно.

        (False, f"{Error}") - Ошибка sql.
        """
        try:
            db.execute(
                """
DELETE FROM events
      WHERE user_id = ? AND 
            removal_time != 0;
""",
                params=(self.user_id,),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"{e}"

    def export_data(
        self, file_name: str, file_format: str = "csv"
    ) -> tuple[bool | StringIO, str]:
        """
        Экспортировать в csv.

        :param file_name:
        :param file_format:

        (file, "") - Успешно.

        (False, "Format Is Not Valid") - Невалидный формат.

        (False, f"Wait {t // 60} min") - Слишком часто запрашивали ждите x минут.
        """
        if file_format not in ("csv",):
            return False, "Format Is Not Valid"

        response, t = export_cooldown.check(self.user_id, False)

        if response:
            file = StringIO()
            file.name = file_name
            table: list[tuple[int, str, str, str], ...] = db.execute(
                """
SELECT event_id,
       date,
       status,
       text
  FROM events
 WHERE user_id = ? AND 
       removal_time = 0;
""",
                params=(self.user_id,),
                column_names=True,
            )
            file_writer = csv.writer(file)
            [
                file_writer.writerows(
                    [
                        [
                            str(event_id),
                            event_date,
                            event_status,
                            remove_html_escaping(event_text),
                        ]
                    ]
                )
                for event_id, event_date, event_status, event_text in table
            ]
            file.seek(0)
            return file, ""
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
        notifications: Literal[0, 1] = None,
        notifications_time: str = None,
    ) -> tuple[bool, str]:
        """
        Установить настройку.
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
            self.settings.sub_urls = sub_urls

        if city is not None:
            update_list.append("city")
            self.settings.city = city

        if timezone is not None:
            if timezone not in [j for i in range(-11, 12) for j in (i, str(i))]:
                return False, "timezone must be -12 and less 12"

            update_list.append("timezone")
            self.settings.timezone = timezone

        if direction is not None:
            if direction not in ("DESC", "ASC"):
                return False, 'direction must be in ["DESC", "ASC"]'

            update_list.append("direction")
            self.settings.direction = direction

        if user_status is not None:
            if user_status not in (-1, 0, 1, 2, "-1", "0", "1", "2"):
                return False, "user_status must be in [-1, 0, 1, 2]"

            update_list.append("user_status")
            self.settings.user_status = user_status

        if notifications is not None:
            if notifications not in (0, 1, "0", "1"):
                return False, "notifications must be in [0, 1]"

            update_list.append("notifications")
            self.settings.notifications = notifications

        if notifications_time is not None:
            hour, minute = [int(v) for v in notifications_time.split(":")]
            if not -1 < hour < 13:
                return False, "hour must be more -1 and less 13"

            if minute not in (0, 10, 20, 30, 40, 50):
                return False, "minute must be in [0, 10, 20, 30, 40, 50]"

            update_list.append("notifications_time")
            self.settings.notifications_time = notifications_time

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
        return True, ""

    def delete_user(
        self, user_id: int = None
    ) -> (
        tuple[bool, str]
        | tuple[bool, tuple[str, bool | StringIO]]
        | tuple[bool | StringIO, str]
    ):
        """
        Удалить все данные пользователя.

        :param user_id:

        (csv_file, "") - Успешно.

        (False, "User Not Exist") - Пользователь не существует.

        (False, "Not Enough Authority") - Недостаточно прав.

        (False, "Unable To Remove Administrator") - Нельзя удалить администратора.

        (False, "Error") - Не получилось получить csv файл.

        (False, (f"{Error}", csv_file)) - Ошибка при удалении.
        """
        user_id = user_id or self.user_id

        if is_admin_id(self.user_id):
            return False, "Not Enough Authority"

        if is_admin_id(user_id):
            return False, "Unable To Remove Administrator"

        if not self.check_user(user_id):
            return False, "User Not Exist"

        tmp_user = User(user_id)
        csv_file = tmp_user.export_data("deleted_user_info.csv")[0]
        if not csv_file:
            return False, "Error"

        try:
            db.execute(
                """
DELETE FROM settings
      WHERE user_id = ?;
""",
                params=(user_id,),
                commit=True,
            )
            db.execute(
                """
DELETE FROM events
      WHERE user_id = ?;
""",
                params=(user_id,),
                commit=True,
            )
        except Error as e:
            return False, (f"{e}", csv_file)

        return csv_file, ""

    def set_user_status(
        self, user_id: int = None, status: Literal[-1, 0, 1, 2] = 0
    ) -> tuple[bool, str]:
        """
        Поставить статус пользователю.

        :param user_id:
        :param status:

        (True, "") - Успешно.

        (False, "User Not Exist") - Пользователь не существует.

        (False, "Not Enough Authority") - Недостаточно прав.

        (False, "Invalid status") - Неверный статус.

        (False, "Cannot be reduced in admin rights") - Нельзя понизить администратора.

        (False, f"{Error}") - Ошибка sql.
        """
        user_id = int(user_id or self.user_id)

        if is_admin_id(self.user_id):
            return False, "Not Enough Authority"

        if status not in (-1, 0, 1, 2):
            return False, "Invalid status"

        if is_admin_id(user_id) and status != 2:
            return False, "Cannot be reduced in admin rights"

        if not self.check_user(user_id):
            return False, "User Not Exist"

        try:
            db.execute(
                """
UPDATE settings
   SET user_status = ?
 WHERE user_id = ?;
""",
                params=(status, user_id),
                commit=True,
            )
            return True, ""
        except Error as e:
            return False, f"{e}"


# user = User(1563866138)
# # [print(i) for i in dir(user)]
# csv_file = user.export_data("my_data.csv")[0].read()
# print(csv_file)
# if csv_file[0]:
#     print(csv_file[0].read())
# else:
#     print(csv_file[-1])
# [print(event.to_json()) for event in user.get_events((1,))]
# print(user.set_status(1, "🔗,💻"))
# print(user.set_status(1, "⬜️"))

"""
```markdown
|                 |    |
|-----------------|----|
| add_event       |    |
| check_event     |    |
| check_limit     |    |
| clear_basket    |    |
| del_event       |    |
| delete_user     |    |
| edit_event      |    |
| edit_event_date |    |
| export_data     |    |
| get_event       |    |
| get_events      |    |
| get_limits      |    |
| get_settings    |    |
| recover_event   |    |
| set_settings    |    |
| set_status      |    |
| set_user_status |    |

|                 |    |
|-----------------|----|
| settings        |    |
| user_id         |    |
| db_conn         |    |

```
"""
