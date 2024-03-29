import csv
import html
import json
import logging
from uuid import uuid4
from datetime import datetime
from io import StringIO, BytesIO
from dataclasses import dataclass
from sqlite3 import Error, connect
import xml.etree.ElementTree as xml  # noqa
from functools import cached_property
from contextlib import contextmanager
from typing import Callable, Any, Literal

from oauthlib.common import generate_token
from vedis import Vedis

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
    GroupNotFound,
    NotGroupMember, Forbidden, MediaNotFound,
)
from config import DATABASE_PATH, VEDIS_PATH
from todoapi.utils import re_date, is_valid_year, sql_date_pattern, re_username, re_email, hash_password


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
        "max_groups_participate": 0,
        "max_groups_creator": 0,
    },
    0: {
        "max_groups_participate": 50,  # количество групп, в которых пользователь может состоять
        "max_groups_creator": 1,  # сколько групп можно иметь
    },
    1: {
        "max_groups_participate": 100,
        "max_groups_creator": 10,
    },
    2: {
        "max_groups_participate": 200,
        "max_groups_creator": 50,
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
        func: tuple[str, int, Callable] = None,
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


class Cache:
    def __init__(self, table: str):
        self.table = table

    def __getitem__(self, key: Any) -> None | str:
        with vedisdb.transaction():
            data = vedisdb.hget(self.table, key)
            return data.decode() if data else None

    def __setitem__(self, key, value):
        with vedisdb.transaction():
            vedisdb.hset(self.table, key, value)

    def __delitem__(self, key):
        with vedisdb.transaction():
            vedisdb.hdel(self.table, key)


class Limit:
    def __init__(self, status: int, user_id: int = None, group_id: str = None):
        self.user_id = user_id
        self.group_id = group_id
        self.status = status
        self.user_max_limits = event_limits[status]

    def get_event_limits(self, date: str | datetime = None) -> list[tuple[int]]:
        date = date if date else datetime.now().strftime("%d.%m.%Y")

        # TODO Убрать из выборки события в корзине
        try:
            return db.execute(
                """
SELECT (
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND date = :date
) AS count_today,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND date = :date
) AS sum_length_today,
(
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND SUBSTR(date, 4, 7) = :date_3
) AS count_month,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND SUBSTR(date, 4, 7) = :date_3
) AS sum_length_month,
(
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND SUBSTR(date, 7, 4) = :date_6
) AS count_year,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND SUBSTR(date, 7, 4) = :date_6
) AS sum_length_year,
(
    SELECT IFNULL(COUNT( * ), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
) AS total_count,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0) 
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
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
        except Error as e:
            raise ApiError(e)

    def is_exceeded_for_events(self, date: str | datetime = None, event_count: int = 0, symbol_count: int = 0) -> bool:
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

    def is_exceeded_for_groups(self, create: bool = False, participate: bool = False) -> bool:
        if not create and not participate:
            raise ApiError

        max_groups_participate, max_groups_creator = tuple(
            group_limits[self.status].values()
        )

        try:
            groups_participate, groups_creator = db.execute(
                """
SELECT (
    SELECT COUNT(1)
      FROM members
     WHERE user_id = :user_id
) as groups_participate,
(
    SELECT COUNT(1)
      FROM groups
     WHERE owner_id = :user_id
) as groups_creator;
""",
                params={"user_id": self.user_id},
            )[0]
        except (Error, IndexError):
            raise ApiError

        return groups_participate + participate > max_groups_participate or groups_creator + create > max_groups_creator

    def now_limit_percent(self, date: str | datetime = None) -> list[int, int, int, int, int, int, int, int]:
        actual_limits = self.get_event_limits(date)

        # noinspection PyTypeChecker
        return [
            int((actual_limit / max_limit) * 100)
            for actual_limit, max_limit in zip(actual_limits, tuple(self.user_max_limits.values()))
        ]


class ExportData:
    def __init__(self, filename: str, user_id: int = None, group_id: str = None):
        self.user_id, self.group_id = user_id, group_id
        self.filename = filename
        self.query = """
SELECT event_id,
       date,
       status,
       text
  FROM events
 WHERE user_id = :user_id
       AND group_id = :group_id
       AND removal_time IS NULL;
"""
        self.params = {
            "user_id": user_id,
            "group_id": group_id,
        }
        try:
            self.table = db.execute(self.query, params=self.params, column_names=True)
        except Error as e:
            raise ApiError(e)

    def csv(self) -> StringIO:
        file = StringIO()
        file.name = self.filename
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
            for event_id, event_date, event_status, event_text in self.table
        ]
        file.seek(0)
        return file

    def xml(self) -> BytesIO:
        file = BytesIO()
        file.name = self.filename

        xml_events = xml.Element("events")
        for event_id, date, status, text in self.table:
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
        return file

    def json(self) -> StringIO:
        file = StringIO()
        file.name = self.filename
        d = tuple(
            {
                "event_id": event_id,
                "date": event_date,
                "status": event_status,
                "text": event_text,
            }
            for event_id, event_date, event_status, event_text in self.table
        )
        file.write(json.dumps(d, indent=4, ensure_ascii=False))
        file.seek(0)
        return file

    def jsonl(self) -> StringIO:
        file = StringIO()
        file.name = self.filename
        d = tuple(
            {
                "event_id": event_id,
                "date": event_date,
                "status": event_status,
                "text": event_text,
            }
            for event_id, event_date, event_status, event_text in self.table
        )
        file.writelines(json.dumps(line, ensure_ascii=False) + "\n" for line in d)
        file.seek(0)
        return file

    def export(self, file_format: str = "csv"):
        if file_format not in ("csv", "xml", "json", "jsonl"):
            raise ValueError('file_format not in ("csv", "xml", "json", "jsonl")')

        return getattr(self, file_format)()


@dataclass
class Media:
    media_id: str
    event_id: int
    user_id: int
    group_id: str
    filename: str
    media_type: str
    media: bytes
    url: str = ""
    url_create_time: str = ""


@dataclass
class Settings:
    lang: str = "ru"
    sub_urls: bool = True
    city: str = "Москва"
    timezone: int = 3
    direction: str = "DESC"
    notifications: bool = False
    notifications_time: str = "08:00"
    theme: int = 0


@dataclass
class TelegramSettings:
    user_id: int
    group_id: str
    lang: str = "ru"
    sub_urls: bool = True
    city: str = "Москва"
    timezone: int = 3
    direction: str = "DESC"
    notifications: bool = False
    notifications_time: str = "08:00"
    theme: int = 0


@dataclass
class Event:
    user_id: int
    group_id: str
    event_id: int
    date: str
    text: str
    status: str
    adding_time: str
    recent_changes_time: str
    removal_time: str
    history: str = None

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
    user_id IS :user_id AND group_id IS :group_id
);
""",
                params={
                    "event_id": self.event_id,
                    "user_id": self.user_id,
                    "group_id": self.group_id,
                },
            )
        except Error as e:
            raise ApiError(e)

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


@dataclass
class Group:
    group_id: str
    name: str
    owner_id: int
    max_event_id: int
    token: str = None
    token_create_time: str = None
    icon: bytes = None

    @classmethod
    def get_from_group_id(cls, group_id: str) -> "Group":
        try:
            group = db.execute(
                """
SELECT group_id,
       name,
       token,
       token_create_time,
       owner_id,
       max_event_id
  FROM groups
 WHERE group_id = :group_id;
""",
                params={"group_id": group_id},
            )[0]
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise GroupNotFound

        return Group(*group)


@dataclass
class Member:
    group_id: str
    user_id: int
    entry_date: str
    member_status: int


class User:
    def __init__(
        self,
        user_id: int,
        user_status: int,
        username: str,
        token: str = None,
        password: str = None,
        email: str = None,
        max_event_id: int = None,
        token_create_time: str = None,
        reg_date: str = None,
        icon: bytes = None,
        group_id: str = None,
        member_status: int = None,
    ):
        self.user_id = user_id
        self.user_status = user_status
        self.username = username
        self.token = token
        self.password = password
        self.email = email
        self.max_event_id = max_event_id
        self.token_create_time = token_create_time
        self.reg_date = reg_date
        self.icon = icon
        self.group_id = group_id
        self.member_status = member_status

        if group_id:
            group = Group.get_from_group_id(group_id)
        else:
            group = None

    @classmethod
    def get_from_token(cls, token: str, group_id: str = None) -> "User":
        # TODO защита от перебора брутфорса и количества попыток
        # TODO хеширование пароля
        try:
            user = db.execute(
                """
SELECT user_id,
       user_status,
       username,
       token,
       password,
       email,
       max_event_id,
       token_create_time,
       reg_date,
       :group_id,
       (
           SELECT member_status
             FROM members
            WHERE group_id = :group_id
       )
  FROM users
 WHERE token = :token;
""",
                params={
                    "token": token,
                    "group_id": group_id,
                },
            )[0]
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return User(*user, group_id=group_id)

    @classmethod
    def get_from_user_id(cls, user_id: int, group_id: str = None) -> "User":
        # TODO защита от перебора брутфорса и количества попыток
        # TODO хеширование пароля
        try:
            user = db.execute(
                """
SELECT user_id,
       user_status,
       username,
       token,
       password,
       email,
       max_event_id,
       token_create_time,
       reg_date,
       :group_id,
       (
           SELECT member_status
             FROM members
            WHERE group_id = :group_id
       )
  FROM users
 WHERE user_id = :user_id;
""",
                params={
                    "user_id": user_id,
                    "group_id": group_id,
                },
            )[0]
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return User(*user)

    @classmethod
    def get_from_password(cls, username: str, password: str, group_id: str = None) -> "User":
        # TODO защита от перебора брутфорса и количества попыток
        # TODO хеширование пароля
        try:
            user = db.execute(
                """
SELECT user_id,
       user_status,
       username,
       token,
       password,
       email,
       max_event_id,
       token_create_time,
       reg_date,
       :group_id,
       (
           SELECT member_status
             FROM members
            WHERE group_id = :group_id
       )
  FROM users
 WHERE username = :username
       AND password = :password;
""",
                params={
                    "username": username,
                    "password": hash_password(password),
                    "group_id": group_id,
                },
            )[0]
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return User(*user)


class Account:
    def __init__(self, user_id: int, group_id: str = None):
        self.user_id, self.group_id = user_id, group_id
        self.user = User.get_from_user_id(user_id, group_id)
        self.limit = Limit(self.user.user_status, user_id, group_id)

    @property
    def is_admin(self) -> bool:
        return self.user.user_status >= 2

    @property
    def is_premium(self) -> bool:
        return self.user.user_status >= 1 or self.is_admin

    @property
    def safe_user_id(self):
        """None if self.group_id else self.user_id"""
        return None if self.group_id else self.user_id

    def check_event_exists(self, event_id: int, in_bin: bool = False) -> bool:
        try:
            return bool(
                db.execute(
                    """
SELECT 1
  FROM events
 WHERE user_id IS :user_id
       AND group_id IS :group_id
       AND event_id = :event_id
       AND (removal_time IS NOT NULL) = :in_bin;
""",
                    params={
                        "user_id": self.safe_user_id,
                        "group_id": self.group_id,
                        "event_id": event_id,
                        "in_bin": in_bin,
                    },
                )
            )
        except Error as e:
            raise ApiError(e)

    def create_event(self, date: str, text: str, status: str = "⬜") -> int:
        text_len = len(text)

        if text_len >= 3800:
            raise TextIsTooBig

        if not re_date.match(date) or not is_valid_year(int(date[-4:])):
            raise WrongDate

        if self.limit.is_exceeded_for_events(date, 1, text_len):
            raise LimitExceeded

        try:
            db.execute(
                """
INSERT INTO events (
    event_id,
    user_id,
    group_id,
    date,
    text,
    status
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
    :text,
    :status
);
""",
                params={
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                    "date": date,
                    "text": text,
                    "status": status,
                },
                commit=True,
            )
            max_event_id: int = db.execute(
                """
SELECT COALESCE(
    (
        SELECT max_event_id
          FROM users
         WHERE user_id = :user_id
    ),
    (
        SELECT max_event_id
          FROM groups
         WHERE group_id = :group_id
    )
);
""",
                params={
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
            )[0][0]
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
        except Error as e:
            raise ApiError(e)

        return max_event_id

    def get_event(self, event_id: int, in_bin: bool = False) -> Event:
        return self.get_events([event_id], in_bin)[0]

    def get_events(self, event_ids: list[int], in_bin: bool = False) -> list[Event]:
        if len(event_ids) > 400:
            raise ApiError

        try:
            events = db.execute(
                f"""
SELECT *
  FROM events
 WHERE user_id IS ?
       AND group_id IS ?
       AND event_id IN ({','.join('?' for _ in event_ids)})
       AND (removal_time IS NOT NULL) = ?;
""",
                params=(
                    self.safe_user_id,
                    self.group_id,
                    *event_ids,
                    in_bin,
                ),
            )
        except Error as e:
            raise ApiError(e)

        if not events:
            raise EventNotFound

        return [Event(*event) for event in events]

    def edit_event_text(self, event_id: int, text: str) -> None:
        if len(text) >= 3800:
            raise TextIsTooBig

        event = self.get_event(event_id)

        # Вычисляем количество добавленных символов
        old_text_len, new_text_len = len(event.text), len(text)
        new_symbol_count = (
            0 if new_text_len < old_text_len else new_text_len - old_text_len
        )

        if self.limit.is_exceeded_for_events(event.date, 0, new_symbol_count):
            raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET text = :text
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "text": text,
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_event_date(self, event_id: int, date: str) -> None:
        if not re_date.match(date) or not is_valid_year(int(date[-4:])):
            raise WrongDate

        event = self.get_event(event_id)

        if self.limit.is_exceeded_for_events(event.date, 1, len(event.text)):
            raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET date = :date
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "date": date,
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_event_status(self, event_id: int, status: str = "⬜️") -> None:
        if not self.check_event_exists(event_id):
            raise EventNotFound

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
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "status": status,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                    "event_id": event_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def delete_event(self, event_id: int, in_bin=True) -> None:
        if not self.check_event_exists(event_id, in_bin=in_bin):
            raise EventNotFound

        try:
            db.execute(
                """
DELETE FROM events
      WHERE event_id = :event_id
            AND user_id IS :user_id
            AND group_id IS :group_id;
""",
                params={
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def delete_event_to_bin(self, event_id: int) -> None:
        if not self.is_premium:
            raise NotEnoughPermissions

        if not self.check_event_exists(event_id):
            raise EventNotFound

        try:
            db.execute(
                """
UPDATE events
   SET removal_time = DATE() 
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def recover_event(self, event_id: int) -> None:
        event = self.get_event(event_id, in_bin=True)

        if self.limit.is_exceeded_for_events(event.date, 1, len(event.text)):
            raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET removal_time = NULL
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def clear_basket(self) -> None:
        try:
            db.execute(
                """
DELETE FROM events
      WHERE removal_time IS NOT NULL
            AND user_id IS :user_id
            AND group_id IS :group_id;
""",
                params={
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def export_data(self, filename: str, file_format: str = "csv") -> StringIO | BytesIO:
        if file_format not in ("csv", "xml", "json", "jsonl"):
            raise ValueError("Format Is Not Valid")

        return ExportData(filename, self.safe_user_id, self.group_id).export(file_format)

    def check_media_exists(self, event_id: int, media_id: str) -> bool:
        try:
            return bool(
                db.execute(
                    """
SELECT 1
  FROM media
 WHERE event_id = :event_id
       AND media_id = :media_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                    params={
                        "event_id": event_id,
                        "media_id": media_id,
                        "user_id": self.safe_user_id,
                        "group_id": self.group_id,
                    },
                )
            )
        except Error as e:
            raise ApiError(e)

    def add_event_media(self, event_id: int, filename: str, media_type: str, media: bytes):
        if not media:
            raise ValueError

        try:
            db.execute(
                """
INSERT INTO media (media_id, event_id, user_id, group_id, filename, media_type, media)
VALUES (
    :media_id,
    :event_id,
    :user_id,
    :group_id,
    :filename,
    :media_type,
    :media
);
""",
                params={
                    "media_id": str(uuid4()).replace("-", ""),
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                    "filename": filename,
                    "media_type": media_type,
                    "media": media,
                },
            )
        except Error as e:
            raise ApiError(e)

    def get_event_media(self, event_id: int, media_id: str) -> Media:
        return self.get_event_medias(event_id, [media_id])[0]

    def get_event_medias(self, event_id: int, media_id: list[str]) -> list[Media]:
        try:
            medias = db.execute(
                """
SELECT media_id,
       event_id,
       user_id,
       group_id,
       filename,
       media_type,
       media,
       url,
       url_create_time
  FROM media
 WHERE event_id = :event_id
       AND media_id = :media_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "event_id": event_id,
                    "media_id": media_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
            )
        except Error as e:
            raise ApiError(e)

        if not medias:
            raise MediaNotFound

        return [Media(*media) for media in medias]

    def delete_event_media(self, event_id: int, media_id: str) -> None:
        if not self.check_media_exists(event_id, media_id):
            raise MediaNotFound

        try:
            db.execute(
                """
DELETE FROM media
      WHERE event_id = :event_id
            AND media_id = :media_id
            AND user_id IS :user_id
            AND group_id IS :group_id;
""",
                params={
                    "event_id": event_id,
                    "media_id": media_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def check_member_exists(self, user_id: int = None, group_id: str = None) -> bool:
        user_id = user_id or self.user_id
        group_id = group_id or self.group_id

        try:
            return bool(
                db.execute(
                    """
SELECT 1
  FROM members
 WHERE group_id = :group_id
       AND user_id = :user_id;
""",
                    params={
                        "group_id": group_id,
                        "user_id": user_id,
                    },
                )
            )
        except Error as e:
            raise ApiError(e)

    def is_moderator(self, group_id: str = None, user_id: int = None) -> bool:
        user_id = user_id or self.user_id

        if group_id is not None:
            return self.get_group_member(user_id, group_id).member_status >= 1

        if self.group_id and self.user.member_status:
            return self.user.member_status >= 1

        return False

    def is_owner(self, group_id: str = None, user_id: int = None) -> bool:
        user_id = user_id or self.user_id

        if group_id is not None:
            return self.get_group_member(user_id, group_id).member_status >= 2

        if self.group_id and self.user.member_status:
            return self.user.member_status >= 2

        return False

    def create_group(self, name: str, icon: bytes = None) -> str:
        if self.limit.is_exceeded_for_groups(create=True):
            raise LimitExceeded

        group_id = str(uuid4()).replace("-", "")

        try:
            db.execute(
                """
INSERT INTO groups (group_id, owner_id, token, name, icon)
VALUES (:group_id, :owner_id, :token, :name, :icon);
""",
                params={
                    "group_id": group_id,
                    "owner_id": self.user_id,
                    "token": generate_token(length=32),
                    "name": name,
                    "icon": icon,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

        return group_id

    def get_group(self, group_id: str) -> Group:
        return self.get_groups([group_id])[0]

    def get_groups(self, group_ids: list[str]) -> list[Group]:
        for group_id in group_ids:
            if not self.check_member_exists(group_id=group_id):
                raise NotGroupMember

        try:
            groups = db.execute(
                f"""
SELECT group_id,
       name,
       owner_id,
       max_event_id,
       token,
       token_create_time
  FROM groups
 WHERE group_id IN ({','.join('?' for _ in group_ids)})
 ORDER BY name ASC;
""",
                params=(*group_ids,),
            )
        except Error as e:
            raise ApiError(e)

        if not groups:
            raise GroupNotFound

        return [Group(*group) for group in groups]

    def get_my_groups(self, page: int = 1) -> list[Group]:
        page -= 1
        try:
            groups = db.execute(
                """
SELECT group_id,
       name,
       owner_id,
       max_event_id,
       token,
       token_create_time
  FROM groups
 WHERE group_id IN (
           SELECT group_id
             FROM members
            WHERE user_id = :user_id
       )
ORDER BY name ASC
LIMIT :limit OFFSET :offset;
""",
                params={
                    "user_id": self.user_id,
                    "limit": 12,
                    "offset": 12 * page,
                },
            )
        except Error as e:
            raise ApiError(e)

        return [Group(*group) for group in groups]

    def get_groups_where_i_moderator(self, page: int = 1) -> list[Group]:
        page -= 1
        try:
            groups = db.execute(
                """
SELECT group_id,
       name,
       owner_id,
       max_event_id,
       token,
       token_create_time
  FROM groups
 WHERE group_id IN (
           SELECT group_id
             FROM members
            WHERE user_id = :user_id
                  AND member_status >= 1
       )
ORDER BY name ASC
LIMIT :limit OFFSET :offset;
""",
                params={
                    "user_id": self.user_id,
                    "limit": 12,
                    "offset": 12 * page,
                },
            )
        except Error as e:
            raise ApiError(e)

        return [Group(*group) for group in groups]

    def get_groups_where_i_admin(self, page: int = 1) -> list[Group]:
        page -= 1
        try:
            groups = db.execute(
                """
SELECT group_id,
       name,
       owner_id,
       max_event_id,
       token,
       token_create_time
  FROM groups
 WHERE group_id IN (
           SELECT group_id
             FROM members
            WHERE user_id = :user_id
                  AND member_status >= 1
       )
ORDER BY name ASC
LIMIT :limit OFFSET :offset;
""",
                params={
                    "user_id": self.user_id,
                    "limit": 12,
                    "offset": 12 * page,
                },
            )
        except Error as e:
            raise ApiError(e)

        return [Group(*group) for group in groups]

    def edit_group_name(self, name: str, group_id: str = None) -> None:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        if not self.is_moderator(group_id):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
UPDATE groups
   SET name = :name
 WHERE group_id = :group_id;
""",
                params={
                    "name": name,
                    "group_id": group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_group_icon(self, icon: bytes, group_id: str = None) -> None:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        if not self.is_moderator(group_id):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
UPDATE groups
   SET icon = :icon
 WHERE group_id = :group_id;
""",
                params={
                    "icon": icon,
                    "group_id": group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def get_group_member(self, user_id: int, group_id: str = None) -> Member:
        group_id = group_id or self.group_id
        return self.get_group_members([user_id], group_id)[0]

    def get_group_members(self, user_ids: list[int], group_id: str = None) -> list[Member]:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        try:
            members = db.execute(
                f"""
SELECT group_id,
       user_id,
       entry_date,
       member_status
  FROM members
 WHERE group_id = ?
       AND user_id IN ({','.join('?' for _ in user_ids)});
""",
                params=(group_id, *user_ids),
            )
        except Error as e:
            raise ApiError(e)

        if not members:
            raise NotGroupMember

        return [Member(*member) for member in members]

    def add_group_member(self, user_id: int, group_id: str = None) -> None:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        try:
            db.execute(
                """
INSERT INTO members (group_id, user_id)
VALUES (:group_id, :user_id);
""",
                params={
                    "group_id": group_id,
                    "user_id": user_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_group_member_status(self, status: int, user_id: int, group_id: str = None) -> None:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        if not self.is_moderator(group_id):
            raise NotEnoughPermissions

        if not self.check_member_exists(user_id):
            raise NotGroupMember

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
                    "group_id": self.group_id,
                    "user_id": user_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def remove_group_member(self, user_id: int, group_id: str = None) -> None:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        if not self.is_moderator(group_id):
            raise NotEnoughPermissions

        if not self.check_member_exists(user_id):
            raise NotGroupMember

        try:
            db.execute(
                """
DELETE FROM members
      WHERE group_id = :group_id
            AND user_id = :user_id;
""",
                params={
                    "group_id": self.group_id,
                    "user_id": user_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def delete_group(self, group_id: str = None) -> None:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        if not self.is_owner(group_id):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
DELETE FROM groups
      WHERE group_id = :group_id;
""",
                params={"group_id": self.group_id},
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_group_owner(self, new_owner_id: int) -> None:
        if self.group_id is None:
            raise Forbidden

        if not self.is_owner:
            raise NotEnoughPermissions

        if not self.check_member_exists(new_owner_id):
            raise NotGroupMember

        try:
            db.execute(
                """
UPDATE groups
   SET owner_id = :new_owner_id
 WHERE group_id = :group_id
       AND owner_id = :owner_id;
""",
                params={
                    "new_owner_id": new_owner_id,
                    "group_id": self.group_id,
                    "owner_id": self.user_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    @cached_property
    def settings(self):
        return self.get_user_settings()

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
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return Settings(*settings)

    def set_user_settings(
        self,
        lang: Literal["ru", "en"] = None,
        sub_urls: Literal[0, 1] = None,
        city: str = None,
        timezone: int = None,
        direction: Literal["DESC", "ASC"] = None,
        notifications: Literal[0, 1, 2] | bool = None,
        notifications_time: str = None,
        theme: int = None,
    ) -> None:
        """
        user_id            INT  UNIQUE NOT NULL,
        lang               TEXT DEFAULT 'ru',
        sub_urls           INT  CHECK (sub_urls IN (0, 1)) DEFAULT (1),
        city               TEXT DEFAULT 'Moscow',
        timezone           INT  CHECK (-13 < timezone < 13) DEFAULT (3),
        direction          TEXT CHECK (direction IN ('DESC', 'ASC')) DEFAULT 'DESC',
        notifications      INT  CHECK (notifications IN (0, 1, 2)) DEFAULT (0),
        notifications_time TEXT DEFAULT '08:00',
        theme              INT  DEFAULT (0),
        """
        update_list = []

        if lang is not None:
            if lang not in ("ru", "en"):
                raise ValueError('lang must be in ["ru", "en"]')

            update_list.append("lang")
            self.settings.lang = lang

        if sub_urls is not None:
            if sub_urls not in (0, 1, "0", "1"):
                raise ValueError("sub_urls must be in [0, 1]")

            update_list.append("sub_urls")
            self.settings.sub_urls = int(sub_urls)

        if city is not None:
            if len(city) > 50:
                raise ValueError("length city must be less than 50 characters")

            update_list.append("city")
            self.settings.city = city

        if timezone is not None:
            if timezone not in [j for i in range(-11, 12) for j in (i, str(i))]:
                raise ValueError("timezone must be -12 and less 12")

            update_list.append("timezone")
            self.settings.timezone = int(timezone)

        if direction is not None:
            if direction not in ("DESC", "ASC"):
                raise ValueError('direction must be in ["DESC", "ASC"]')

            update_list.append("direction")
            self.settings.direction = direction

        if notifications is not None:
            if notifications not in (0, 1, 2, "0", "1", "2", True, False):
                raise ValueError("notifications must be in [0, 1, 2]")

            update_list.append("notifications")
            self.settings.notifications = int(notifications)

        if notifications_time is not None:
            hour, minute = [int(v) for v in notifications_time.split(":")]
            if not -1 < hour < 24:
                raise ValueError("hour must be more -1 and less 24")

            if minute not in (0, 10, 20, 30, 40, 50):
                raise ValueError("minute must be in [0, 10, 20, 30, 40, 50]")

            update_list.append("notifications_time")
            self.settings.notifications_time = notifications_time

        if theme is not None:
            if theme not in (0, 1, "0", "1"):
                raise ValueError("theme must be in [0, 1]")

            update_list.append("theme")
            self.settings.theme = int(theme)

        try:
            db.execute(
                """
UPDATE users_settings
   SET {}
 WHERE user_id = :user_id;
""".format(
                    ", ".join(f"{update} = :{update}" for update in update_list)
                ),
                params={
                    "lang": lang,
                    "sub_urls": sub_urls,
                    "city": city,
                    "timezone": timezone,
                    "direction": direction,
                    "notifications": notifications,
                    "notifications_time": notifications_time,
                    "theme": theme,
                    "user_id": self.user_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_user_username(self, username: str) -> None:
        if self.group_id:
            raise Forbidden

        if not re_username.match(username):
            raise ApiError

        try:
            db.execute(
                """
UPDATE users
   SET username = :username
 WHERE user_id = :user_id;
""",
                params={
                    "username": username,
                    "user_id": self.user_id,
                },
            )
        except Error as e:
            raise ApiError(e)

    def edit_user_password(self, password: str) -> None:
        if self.group_id:
            raise Forbidden

        if not password:
            raise ValueError

        if hash_password(password) != self.user.password:
            raise ApiError

        try:
            db.execute(
                """
UPDATE users
   SET password = :password
 WHERE user_id = :user_id;
""",
                params={
                    "password": hash_password(password),
                    "user_id": self.user_id,
                },
            )
        except Error as e:
            raise ApiError(e)

    def edit_user_icon(self, icon: bytes) -> None:
        if self.group_id:
            raise Forbidden

        if not icon:
            raise ApiError

        try:
            db.execute(
                """
UPDATE users
   SET icon = :icon
 WHERE user_id = :user_id;
""",
                params={
                    "icon": icon,
                    "user_id": self.user_id,
                },
            )
        except Error as e:
            raise ApiError(e)

    def reset_user_token(self) -> str:
        if self.group_id:
            raise Forbidden

        token = generate_token(length=32)

        try:
            db.execute(
                """
UPDATE users
   SET token = :token
 WHERE user_id = :user_id;
""",
                params={
                    "token": token,
                    "user_id": self.user_id,
                },
            )
        except Error as e:
            raise ApiError(e)

        return token

    def delete_user(self) -> None:
        if self.group_id:
            raise Forbidden

        try:
            db.execute(
                """
DELETE FROM users
      WHERE user_id = :user_id;
""",
                params={"user_id": self.user_id},
                commit=True,
            )
        except Error as e:
            raise ApiError(e)


def create_user(email: str, username: str, password: str) -> None:
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
                "password": hash_password(password),
            },
            commit=True,
        )
    except Error as e:
        raise ApiError(e)

def get_account_from_token(token: str, group_id: str = None) -> Account:
    try:
        user_id = db.execute(
            """
SELECT user_id
  FROM users
 WHERE token = :token;
""",
            params={
                "token": token,
                "group_id": group_id,
            },
        )[0][0]
    except Error as e:
        raise ApiError(e)
    except IndexError:
        raise UserNotFound

    return Account(user_id, group_id)

def get_account_from_password(username: str, password: str, group_id: str = None) -> Account:
    try:
        user_id = db.execute(
            """
SELECT user_id
  FROM users
 WHERE username = :username
       AND password = :password;
""",
            params={
                "username": username,
                "password": hash_password(password),
            },
        )[0][0]
    except Error as e:
        raise ApiError(e)
    except IndexError:
        raise UserNotFound

    return Account(user_id, group_id)

def get_account_from_id(user_id: int, group_id: str = None) -> Account:
    return Account(user_id, group_id)


db = DataBase()
vedisdb = Vedis(VEDIS_PATH)
