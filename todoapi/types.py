import json
import logging
from functools import wraps
from io import StringIO
from typing import Callable, Any
from datetime import datetime
from sqlite3 import Error, connect
from contextlib import contextmanager
from uuid import uuid4

from oauthlib.common import generate_token

from todoapi.exceptions import (
    ApiError,
    EventNotFound,
    TextIsTooBig,
    LimitExceeded,
    WrongDate,
    StatusConflict,
    StatusLengthExceeded,
    StatusRepeats,
    NotEnoughPermissions,
    UserNotFound,
    GroupNotFound, NotGroupMember,
)
from config import DATABASE_PATH
from todoapi.utils import re_date, is_valid_year, sql_date_pattern, re_username, re_email

event_limits = {
    -1: {
        "max_event_day": 0,
        "max_symbol_day": 0,
        "max_event_month": 0,
        "max_symbol_month": 0,
        "max_event_year": 0,
        "max_symbol_year": 0,
        "max_event_all": 0,
        "max_symbol_all": 0,
    },
    0: {
        "max_event_day": 20,
        "max_symbol_day": 4000,
        "max_event_month": 75,
        "max_symbol_month": 10000,
        "max_event_year": 500,
        "max_symbol_year": 80000,
        "max_event_all": 500,
        "max_symbol_all": 100000,
    },
    1: {
        "max_event_day": 40,
        "max_symbol_day": 8000,
        "max_event_month": 100,
        "max_symbol_month": 15000,
        "max_event_year": 750,
        "max_symbol_year": 100000,
        "max_event_all": 900,
        "max_symbol_all": 150000,
    },
    2: {
        "max_event_day": 60,
        "max_symbol_day": 20000,
        "max_event_month": 200,
        "max_symbol_month": 65000,
        "max_event_year": 1000,
        "max_symbol_year": 120000,
        "max_event_all": 2000,
        "max_symbol_all": 200000,
    },
}
group_limits = {
    -1: {
        "max_group": 0,
        "max_group_create": 0,
    },
    0: {
        "max_group": 50,
        "max_group_create": 1,
    },
    1: {
        "max_group": 100,
        "max_group_create": 10,
    },
    2: {
        "max_group": 200,
        "max_group_create": 50,
    },
}
string_status = {-1: "ban", 0: "normal", 1: "premium", 2: "admin"}


class DataBase:
    def __init__(self):
        self.sqlite_connection = None
        self.sqlite_cursor = None
        # self.sqlite_connection = connect(config.DATABASE_PATH)
        # self.sqlite_connection.close()

    @contextmanager
    def connection(self):
        # self.sqlite_connection = connect(config.DATABASE_PATH)
        yield
        # self.sqlite_connection.close()

    @contextmanager
    def cursor(self):
        # self.sqlite_cursor = self.sqlite_connection.cursor()
        yield
        # self.sqlite_cursor.close()

    def execute(
        self,
        query: str,
        params: tuple | dict = (),
        commit: bool = False,
        column_names: bool = False,
        func: tuple[str, int, Callable] | None = None,
        script: bool = False,
    ) -> list[tuple[int | str | bytes | Any, ...], ...]:
        """
        Выполняет SQL запрос
        Пробовал через with, но оно не закрывало файл

        :param query: Запрос
        :param params: Параметры запроса (необязательно)
        :param commit: Нужно ли сохранить изменения? (необязательно, по умолчанию False)
        :param column_names: Названия столбцов вставить в результат.
        :param func: Оконная функция. (название функции, кол-во аргументов, функция)
        :param script: query состоит из нескольких запросов
        :return: Результат запроса
        """
        self.sqlite_connection = connect(DATABASE_PATH)
        self.sqlite_cursor = self.sqlite_connection.cursor()
        if func:
            self.sqlite_connection.create_function(*func)
        logging.debug(
            "    " + " ".join([line.strip() for line in query.split("\n")]).strip()
        )

        if script:
            self.sqlite_cursor.executescript(query)
        else:
            self.sqlite_cursor.execute(query, params)

        if commit:
            self.sqlite_connection.commit()
        result = self.sqlite_cursor.fetchall()
        if column_names:
            description = [column[0] for column in self.sqlite_cursor.description]
            result = [description] + result
        # self.sqlite_cursor.close()
        self.sqlite_connection.close()
        # noinspection PyTypeChecker
        return result


class Limit:
    def __init__(self, *, user_id: int = None, group_id: str = None, status: int):
        self.user_id = user_id
        self.group_id = group_id
        self.status = status
        self.user_max_limits = event_limits[status]

    def get_event_limits(self, date: str | datetime = None) -> list[tuple[int]]:
        date = date if date else datetime.now().strftime("%d.%m.%Y")

        # Убрать из выборки события в корзине
        try:
            return db.execute(
                """
SELECT (
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE (user_id = :user_id OR group_id = :group_id) AND 
           date = :date
) AS count_today,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE (user_id = :user_id OR group_id = :group_id) AND 
           date = :date
) AS sum_length_today,
(
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE (user_id = :user_id OR group_id = :group_id) AND 
           SUBSTR(date, 4, 7) = :date_3
) AS count_month,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE (user_id = :user_id OR group_id = :group_id) AND 
           SUBSTR(date, 4, 7) = :date_3
) AS sum_length_month,
(
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE (user_id = :user_id OR group_id = :group_id) AND 
           SUBSTR(date, 7, 4) = :date_6
) AS count_year,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE (user_id = :user_id OR group_id = :group_id) AND 
           SUBSTR(date, 7, 4) = :date_6
) AS sum_length_year,
(
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE user_id = :user_id OR group_id = :group_id
) AS total_count,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE user_id = :user_id OR group_id = :group_id
) AS total_length;
""",
                params={
                    "user_id": self.user_id,
                    "group_id": self.group_id,
                    "date": date,
                    "date_3": date[3:],
                    "date_6": date[6:],
                },
            )[0]
        except Error:
            raise ApiError

    def is_exceeded_events(self, *, date: str | datetime = None, event_count: int = 0, symbol_count: int = 0) -> bool:
        inf = float("inf")  # Бесконечность
        actual_limits = self.get_event_limits(date)

        limits_event_count = zip(actual_limits[::2], tuple(self.user_max_limits.values())[::2])
        limits_symbol_count = zip(actual_limits[1::2], tuple(self.user_max_limits.values())[1::2])

        return (
            any(
                actual_limit + event_count >= (max_limit or inf)
                for actual_limit, max_limit in limits_event_count
            ) or any(
                actual_limit + symbol_count >= (max_limit or inf)
                for actual_limit, max_limit in limits_symbol_count
            )
        )

    def now_limit_percent(self, date: str | datetime = None) -> list[int, int, int, int, int, int, int, int]:
        actual_limits = self.get_event_limits(date)

        # noinspection PyTypeChecker
        return [
            int((actual_limit / max_limit) * 100)
            for actual_limit, max_limit in zip(actual_limits, self.user_max_limits)
        ]


class Media:
    def __init__(
        self,
        media_id: str,
        event_id: int,
        user_id: int,
        group_id: str,
        filename: str,
        media: bytes,
        url: str = "",
        url_create_time: str = "",
    ):
        self.media_id = media_id
        self.event_id = event_id
        self.user_id = user_id
        self.group_id = group_id
        self.filename = filename
        self.media = media
        self.url = url
        self.url_create_time = url_create_time


class Settings:
    def __init__(
        self,
        lang: str = "ru",
        sub_urls: bool = True,
        city: str = "Москва",
        timezone: int = 3,
        direction: str = "DESC",
        notifications: bool = False,
        notifications_time: str = "08:00",
        theme: int = 0,
    ):
        self.lang = lang
        self.sub_urls = sub_urls
        self.city = city
        self.timezone = timezone
        self.direction = direction
        self.notifications = notifications
        self.notifications_time = notifications_time
        self.theme = theme


class TelegramSettings:
    def __init__(
        self,
        user_id: int,
        group_id: str,
        lang: str = "ru",
        sub_urls: bool = True,
        city: str = "Москва",
        timezone: int = 3,
        direction: str = "DESC",
        notifications: bool = False,
        notifications_time: str = "08:00",
        theme: int = 0,
        add_event_date: str = "",
    ):
        self.user_id = user_id
        self.group_id = group_id
        self.lang = lang
        self.sub_urls = sub_urls
        self.city = city
        self.timezone = timezone
        self.direction = direction
        self.notifications = notifications
        self.notifications_time = notifications_time
        self.theme = theme
        self.add_event_date = add_event_date


class Event:
    def __init__(
        self,
        user_id: int,
        group_id: str,
        event_id: int,
        date: str,
        text: str,
        status: str,
        adding_time: str,
        recent_changes_time: str,
        removal_time: str,
        history: str,
    ):
        self.user_id = user_id
        self.group_id = group_id
        self.event_id = event_id
        self.date = date
        self.text = text
        self.status = status
        self.adding_time = adding_time
        self.recent_changes_time = recent_changes_time
        self.removal_time = removal_time
        self.history = history

    @property
    def is_delete(self) -> bool:
        return bool(self.removal_time)

    @property
    def media_list(self) -> list["Media"]:
        try:
            media_list = db.execute(
                """
SELECT media_id,
       event_id,
       user_id,
       group_id,
       filename,
       media,
       url,
       url_create_time
  FROM media
 WHERE event_id = :event_id AND (
    user_id = :user_id OR group_id = :group_id
);
""",
                params={
                    "event_id": self.event_id,
                    "user_id": self.user_id,
                    "group_id": self.group_id,
                },
            )
        except Error:
            raise ApiError

        return [Media(*media) for media in media_list]

    @property
    def days_before_delete(self) -> int:
        """
        Вычисляет количество дней до удаления события из корзины.
        Если событие уже должно быть удалено, возвращает -1.
        """
        if sql_date_pattern.match(self.removal_time):
            _d1 = datetime.utcnow()
            _d2 = datetime.strptime(self.removal_time, "%Y-%m-%d")
            _days = 30 - (_d1 - _d2).days
            return -1 if _days < 0 else _days
        else:
            return 30

    def to_json(self) -> str:
        # TODO обновить
        return json.dumps(
            {
                "user_id": self.user_id,
                "event_id": self.event_id,
                "date": self.date,
                "text": self.text,
                "status": self.status,
                "removal_time": self.removal_time,
                "adding_time": self.adding_time,
                "recent_changes_time": self.recent_changes_time,
            },
            ensure_ascii=False,
        )

    def to_dict(self) -> dict:
        # TODO обновить
        return {
            "user_id": self.user_id,
            "event_id": self.event_id,
            "date": self.date,
            "text": self.text,
            "status": self.status,
            "removal_time": self.removal_time,
            "adding_time": self.adding_time,
            "recent_changes_time": self.recent_changes_time,
        }

    @staticmethod
    def de_json(json_string) -> "Event":
        return Event(**json.loads(json_string))


class Group:
    def __init__(
        self,
        group_id: str,
        name: str,
        token: str,
        token_create_time: str,
        admin_user_id: int,
        max_event_id: int,
        icon: bytes | None = None
    ):
        self.group_id = group_id
        self.name = name
        self.token = token
        self.token_create_time = token_create_time
        self.admin_user_id = admin_user_id
        self.max_event_id = max_event_id
        self.__icon = icon

    @property
    def icon(self) -> bytes | None:
        return self.__icon or None  # TODO select из database


class Member:
    def __init__(
        self,
        group_id: str,
        user_id: int,
        entry_date: str,
        member_status: int,
    ):
        self.group_id = group_id
        self.user_id = user_id
        self.entry_date = entry_date
        self.member_status = member_status


def allow_for(user: bool = False, member: bool = False):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not (user or member):
                raise ApiError("not allowed")
            if member and not user and not self.group_id:
                raise ApiError("allow only for group member")
            if user and not member and self.group_id:
                raise ApiError("allow only for user")

            return func(*args, **kwargs)

        return wrapper
    return decorator


class SafeUser:
    def __init__(
        self,
        user_id: int,
        username: str,
        user_status: int,
        reg_date: str,
        icon: bytes | None = None,
        group_id: str | None = None,
    ):
        self.user_id = user_id
        self.username = username
        self.user_status = user_status
        self.reg_date = reg_date
        self.__icon = icon
        self.__group_id = group_id

        if self.group_id and not self.is_group_member(self.group_id):
            raise NotGroupMember

    @property
    def icon(self) -> bytes | None:
        # TODO из базы данных
        return self.__icon or None

    @property
    def group_id(self) -> str:
        return self.__group_id

    @group_id.setter
    def group_id(self, group_id: str):
        if not self.is_group_member(group_id):
            raise NotGroupMember

        self.__group_id = group_id

    def get_my_member_status(self, group_id: str) -> int:
        try:
            return db.execute(
                """
SELECT member_status
  FROM member
 WHERE group_id = :group_id
       AND user_id = :user_id;
""",
                params={
                    "group_id": group_id,
                    "user_id": self.user_id,
                },
            )[0]
        except Error:
            raise ApiError
        except IndexError:
            raise NotGroupMember

    @property
    @allow_for(user=True)
    def is_admin(self) -> bool:
        return self.user_status >= 2

    @property
    @allow_for(user=True)
    def is_premium(self) -> bool:
        return self.user_status >= 1

    @property
    @allow_for(member=True)
    def is_moderator(self) -> bool:
        return False


class User(SafeUser):
    def __init__(
        self,
        user_id: int,
        username: str,
        user_status: int,
        reg_date: str,
        token: str | None = None,
        password: str | None = None,
        email: str | None = None,
        max_event_id: int | None = None,
        token_create_time: str | None = None,
        icon: bytes | None = None,
        *,
        group_id: str | None = None,
    ):
        super().__init__(user_id, username, user_status, reg_date, icon, group_id)
        self.token = token
        self.password = password
        self.email = email
        self.max_event_id = max_event_id
        self.token_create_time = token_create_time
        self.limit = Limit(user_id=user_id, status=user_status)

    @property
    def settings(self):
        return self.get_user_settings()

    @property
    def groups(self):
        return self.get_groups_by_user_id()

    def create_event(self, date: str, text: str) -> bool:
        text_len = len(text)

        if text_len >= 3800:
            raise TextIsTooBig

        if not re_date.match(date) or not is_valid_year(int(date[-4:])):
            raise WrongDate

        if self.limit.is_exceeded_events(
            date=date,
            event_count=1,
            symbol_count=text_len,
        ):
            # max(self.get_limits(date)[1]) >= 100:
            raise LimitExceeded

        try:
            db.execute(
                """
INSERT INTO events (
    event_id,
    user_id,
    group_id,
    date,
    text
)
VALUES (
    COALESCE(
        (
            SELECT max_event_id
              FROM users
             WHERE user_id = :user_id
        ),
        (
            SELECT max_event_id
              FROM groups
             WHERE group_id = :group_id
        ),
        1
    ),
    :user_id,
    :group_id,
    :date,
    :text
);
""",
                params={
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                    "date": date,
                    "text": text,
                },
                commit=True,
            )
            if self.group_id:
                db.execute(
                    """
UPDATE groups
   SET max_event_id = max_event_id + 1
 WHERE group_id = :group_id;
    """,
                    params={"group_id": self.group_id},
                    commit=True,
                )
            else:
                db.execute(
                    """
UPDATE users
   SET max_event_id = max_event_id + 1
 WHERE user_id = :user_id;
    """,
                    params={"user_id": self.user_id},
                    commit=True,
                )
        except Error:
            raise ApiError

        return True

    def get_event(self, event_id: int, in_bin: bool = False) -> "Event":
        return self.get_events([event_id], in_bin)[0]

    def get_events(self, event_ids: list[int], in_bin: bool = False) -> list["Event"]:
        if len(event_ids) > 400:
            raise ApiError

        try:
            events = db.execute(
                f"""
SELECT *
  FROM events
 WHERE (user_id = ? AND group_id = ?)
       AND event_id IN ({','.join('?' for _ in event_ids)})
       AND (removal_time = "") = ?;
""",
                params=(
                    self.user_id if not self.group_id else None,
                    self.group_id,
                    *event_ids,
                    in_bin,
                ),
            )
        except Error:
            raise ApiError

        if not events:
            raise EventNotFound

        return [Event(*event) for event in events]

    def edit_event_text(self, event_id: int, text: str) -> bool:
        if len(text) >= 3800:
            raise TextIsTooBig

        event = self.get_event(event_id)

        # Вычисляем количество добавленных символов
        old_text_len, new_text_len = len(event.text), len(text)
        new_symbol_count = (
            0 if new_text_len < old_text_len else new_text_len - old_text_len
        )

        if self.limit.is_exceeded_events(date=event.date, symbol_count=new_symbol_count):
            raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET text = :text
 WHERE event_id = :event_id
       AND (user_id = :user_id AND group_id = :group_id);
""",
                params={
                    "text": text,
                    "event_id": event_id,
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def edit_event_date(self, event_id: int, date: str) -> bool:
        if not re_date.match(date) or not is_valid_year(int(date[-4:])):
            raise WrongDate

        event = self.get_event(event_id)

        if self.limit.is_exceeded_events(date=event.date, event_count=1, symbol_count=len(event.text)):
            raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET date = :date
 WHERE event_id = :event_id
       AND (user_id = :user_id AND group_id = :group_id);
""",
                params={
                    "date": date,
                    "event_id": event_id,
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def edit_event_status(self, event_id: int, status: str = "⬜️") -> bool:
        self.get_event(event_id)

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
            raise StatusConflict

        statuses = status.split(",")

        # Статусов не может быть больше 5
        # Длинна одного обычного статуса не может быть больше 3 символов
        # Язык кода ("💻") не может быть больше 6 символов
        if (
            len(statuses) > 5
            or max(
                # Если длинна больше 6, то сумма булева (>) значения и 3 будет больше 3
                (3 + (len(s.removeprefix("💻")) > 6)) if s.startswith("💻") else len(s)
                for s in statuses
            )
            > 3
        ):
            raise StatusLengthExceeded

        if len(statuses) != len(set(statuses)):
            raise StatusRepeats

        try:
            db.execute(
                """
UPDATE events
   SET status = :status
 WHERE (user_id = :user_id AND group_id = :group_id) AND 
       event_id = :event_id;
""",
                params={
                    "status": status,
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                    "event_id": event_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def delete_event(self, event_id: int) -> bool:
        self.get_event(event_id, in_bin=True)

        try:
            db.execute(
                """
DELETE FROM events
      WHERE (user_id = :user_id AND group_id = :group_id)
            AND event_id = :event_id;
""",
                params={
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                    "event_id": event_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def delete_event_to_bin(self, event_id: int) -> bool:
        if not self.is_premium:
            raise NotEnoughPermissions

        self.get_event(event_id, in_bin=True)

        try:
            db.execute(
                """
UPDATE events
   SET removal_time = DATE() 
 WHERE (user_id = :user_id AND group_id = :group_id)
       AND event_id = :event_id;
""",
                params={
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                    "event_id": event_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def recover_event(self, event_id: int) -> bool:
        event = self.get_event(event_id, in_bin=True)

        if self.limit.is_exceeded_events(date=event.date, event_count=1, symbol_count=len(event.text)):
            raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET removal_time = ''
 WHERE (user_id = :user_id AND group_id = :group_id)
       AND event_id = :event_id;
""",
                params={
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                    "event_id": event_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def clear_basket(self) -> bool:
        try:
            db.execute(
                """
DELETE FROM events
      WHERE (user_id = :user_id AND group_id = :group_id)
            AND removal_time != '';
""",
                params={
                    "user_id": self.user_id if not self.group_id else None,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def export_data(
        self, user_id: int | None = None, group_id: str | None = None
    ) -> StringIO:
        pass

    def add_event_media(self, event_id: int, media: bytes):
        pass

    def get_event_media_url(self, media_id: str) -> str:
        pass

    def delete_event_media(self, media_id: str) -> bool:
        pass

    def edit_user_username(self) -> bool:
        try:
            pass
        except Error:
            raise ApiError

        return True

    def edit_user_password(self) -> bool:
        pass

    def edit_user_icon(self) -> bool:
        pass

    def reset_user_token(self) -> bool:
        pass

    @allow_for(user=True)
    def delete_user(self) -> bool:
        try:
            db.execute(
                """
DELETE FROM users
      WHERE user_id = :user_id;
""",
                params={"user_id": self.user_id},
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def get_user_settings(self) -> Settings:
        try:
            settings = db.execute(
                """
SELECT lang,
       sub_urls,
       city,
       timezone,
       direction,
       notifications,
       notifications_time,
       theme
  FROM users_settings
 WHERE user_id = :user_id;
""",
                params={"user_id": self.user_id},
            )[0]
        except Error:
            raise ApiError

        if not settings:
            raise ApiError

        return Settings(*settings)

    def set_user_settings(self) -> Settings:
        pass

    @classmethod
    def get_group(cls, group_id: str) -> Group:
        return cls.get_groups([group_id])[0]

    @classmethod
    def get_groups(cls, group_id: list[str]) -> list[Group]:
        # TODO проверка прав
        try:
            groups = db.execute(
                """
SELECT *
  FROM groups
 WHERE group_id = :group_id;
""",
                params={"group_id": group_id},
            )
        except Error:
            raise ApiError

        if not groups:
            raise GroupNotFound

        return [Group(*group) for group in groups]

    def get_groups_by_user_id(self, user_id: int | None = None) -> list[Group]:
        try:
            groups = db.execute(
                """
SELECT *
  FROM groups
 WHERE group_id = (
    SELECT group_id
      FROM members
     WHERE user_id = :user_id
);
""",
                params={"user_id": user_id or getattr(self, "user_id")},
            )
        except Error:
            raise ApiError

        return [Group(*group) for group in groups]

    def edit_group_name(self, group_id: str, name: str) -> bool:
        # TODO проверка прав
        if getattr(self, "user_status", 0) > 0:
            raise NotEnoughPermissions

        # TODO проверка существования группы

        try:
            db.execute(
                """
UPDATE groups
   SET name = :name
 WHERE group_id = :group_id;
""",
                params={"group_id": group_id, "name": name},
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def edit_group_icon(self, group_id: str, icon: bytes) -> bool:
        # TODO проверка прав
        if getattr(self, "user_status", 0) > 0:
            raise NotEnoughPermissions

        try:
            db.execute(
                """
UPDATE groups
   SET icon = :icon
 WHERE group_id = :group_id;
""",
                params={"group_id": group_id, "icon": icon},
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def get_group_member(self, group_id: str, user_id: int) -> "SafeGroupMember":
        pass

    def get_group_members(self, group_id: str, user_id_list: list[int] = None) -> list["SafeGroupMember"]:
        pass

    def add_group_member(self, group_id: str, user_id: int) -> bool:
        pass




    def create_group(self, name: str, icon: bytes = None) -> bool:
        # TODO Проверка лимита на количество групп
        try:
            db.execute(
                """
INSERT INTO groups (group_id, admin_user_id, token, name, icon)
VALUES (:group_id, :admin_user_id, :token, :name, :icon);
""",
                params={
                    "group_id": uuid4(),
                    "admin_user_id": self.user_id,
                    "token": generate_token(length=32),
                    "name": name,
                    "icon": icon,
                },
            )
        except Error:
            raise ApiError

        return True

    def get_groups_where_i_admin(self) -> list["Group"]:
        try:
            groups = db.execute(
                """
SELECT group_id,
       name,
       token,
       token_create_time,
       admin_user_id,
       max_event_id
  FROM groups
 WHERE group_id = (
    SELECT group_id
      FROM members
     WHERE user_id = :user_id AND member_status >= 1;
);
""",
                params={"user_id": self.user_id},
            )
        except Error:
            raise ApiError

        return [Group(*group) for group in groups]

    def edit_group_member_status(self, group_id: str, user_id: int, status: int) -> bool:
        group = self.get_group(group_id)

        if group.is_owner(user_id) or not group.is_moderator(getattr(self, "user_id")):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
UPDATE members
   SET member_status = :status
 WHERE group_id = :group_id
       AND user_id = :user_id;
""",
                params={
                    "status": status,
                    "group_id": group_id,
                    "user_id": user_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def delete_group_member(self, group_id: str, user_id: int) -> bool:
        group = self.get_group(group_id)

        if group.is_owner(user_id) or not group.is_moderator(getattr(self, "user_id")):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
DELETE FROM members
      WHERE group_id = :group_id
            AND user_id = :user_id;
""",
                params={
                    "group_id": group_id,
                    "user_id": user_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def delete_group(self, group_id: str) -> bool:
        group = self.get_group(group_id)
        user_id = getattr(self, "user_id")

        if not group.is_moderator(user_id):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
DELETE FROM groups
      WHERE group_id = :group_id;
""",
                params={"group_id": group_id},
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def edit_group_owner(self, group_id: str, new_owner_id: int) -> bool:
        group = self.get_group(group_id)
        user_id = getattr(self, "user_id")

        if not group.is_owner(user_id):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
UPDATE groups
   SET user_id = :new_owner_id
 WHERE group_id = :group_id
       AND user_id = :owner_id;
""",
                params={
                    "group_id": group_id,
                    "owner_id": user_id,
                    "new_owner_id": new_owner_id,
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True










def create_user(email: str, username: str, password: str) -> bool:
    if not re_email.match(email) or not re_username.match(username) or not password:
        raise ApiError

    try:
        db.execute(
            """
INSERT INTO users (user_id, token, email, username, password)
VALUES (
(SELECT IFNULL(MAX(user_id), 0) + 1 FROM users),
:token,
:email,
:username,
:password
);
""",
            params={
                "token": generate_token(length=32),
                "email": email,
                "username": username,
                "password": password,
            },
            commit=True,
        )
    except Error:
        raise ApiError

    return True

def get_user(token: str, group_id: str | None = None) -> User:
    # TODO защита от перебора брутфорса и количества попыток
    try:
        user = db.execute(
            """
SELECT *
FROM users
WHERE token = :token;
""",
            params={"token": token},
        )[0]
    except Error:
        raise ApiError
    except IndexError:
        raise UserNotFound

    return User(*user, group_id=group_id)

def get_user_from_password(username: str, password: str, group_id: str | None = None) -> User:
    # TODO защита от перебора брутфорса и количества попыток
    try:
        user = db.execute(
            """
SELECT user_id,
   username,
   user_status,
   reg_date,
   token,
   password,
   email,
   max_event_id,
   token_create_time
FROM users
WHERE username = :username
   AND password = :password;
""",
            params={
                "username": username,
                "password": password,
            },
        )[0]
    except Error:
        raise ApiError
    except IndexError:
        raise UserNotFound

    return User(*user, group_id=group_id)

def get_user_from_user_id(user_id: int) -> SafeUser:
    """
    Делает то же самое, что и get_user, но заполняет только публичные поля.
    """
    try:
        user = db.execute(
            """
SELECT username,
   user_status,
   reg_date
FROM users
WHERE user_id = :user_id;
""",
            params={"user_id": user_id},
        )[0]
    except Error:
        raise ApiError
    except IndexError:
        raise UserNotFound

    return SafeUser(user_id, *user)





db = DataBase()
# create_user("example@gmail.com", "EgorKhabarov", "<password>")
__user = get_user_from_password("EgorKhabarov", "<password>")
# __user.create_event("21.03.2024", ".")
# print(__user.get_event(1).to_json())
print(__user.is_moderator)
