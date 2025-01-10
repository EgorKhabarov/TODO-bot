import csv
import json
import arrow
import datetime
from uuid import uuid4
from arrow import Arrow
from io import StringIO, BytesIO
from dataclasses import dataclass
from sqlite3 import Error, connect
import xml.etree.ElementTree as xml  # noqa
from functools import cached_property
from contextlib import contextmanager
from typing import Callable, Any, Literal

from vedis import Vedis

import config
from todoapi.exceptions import (
    ApiError,
    Forbidden,
    WrongDate,
    TextIsTooBig,
    UserNotFound,
    GroupNotFound,
    MediaNotFound,
    EventNotFound,
    LimitExceeded,
    StatusRepeats,
    NotGroupMember,
    NotUniqueEmail,
    NotUniqueUsername,
    NotEnoughPermissions,
    StatusLengthExceeded,
)
from todoapi.utils import (
    re_date,
    re_username,
    hash_password,
    is_valid_year,
    generate_token,
    verify_password,
    sql_date_pattern,
)


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
        "max_groups_participate": 50,  # count of groups you can be a member of
        "max_groups_creator": 1,  # count of groups you can own
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
repetition_dict = {
    "repeat never": "🔕",
    "repeat every day": "📬",
    "repeat every week": "🗞",
    "repeat every month": "📅",
    "repeat every year": "📆",
    "repeat every weekdays": "👨‍💻",
}


class DataBase:
    def __init__(self):
        self.sqlite_connection = None
        self.sqlite_cursor = None
        # self.sqlite_connection = connect(config.DATABASE_PATH)
        # self.sqlite_connection.close()

    @contextmanager
    def connection(self):
        # self.sqlite_connection = connect(config.DATABASE_PATH)
        # logger.debug("connection.start()")
        yield
        # logger.debug("connection.close()")
        # self.sqlite_connection.close()

    @contextmanager
    def cursor(self):
        # self.sqlite_cursor = self.sqlite_connection.cursor()
        # logger.debug("cursor.start()")
        yield
        # logger.debug("cursor.close()")
        # self.sqlite_cursor.close()

    def execute(
        self,
        query: str,
        params: tuple | dict = (),
        commit: bool = False,
        column_names: bool = False,
        functions: tuple[tuple[str, Callable]] = None,
        script: bool = False,
    ) -> list[tuple[int | str | bytes | Any, ...], ...]:
        """
        Executes SQL query
        I tried with, but it didn't close the file

        :param query: SQL Query.
        :param params: Query parameters (optional)
        :param commit: Should I save my changes? (optional, defaults to False)
        :param column_names: Insert column names into the result.
        :param functions: Window functions. (function name, function)
        :param script: Query consists of several requests
        :return: Query result
        """
        self.sqlite_connection = connect(config.DATABASE_PATH)
        self.sqlite_cursor = self.sqlite_connection.cursor()

        if functions:
            for func in functions:
                fn, ff = func
                # noinspection PyUnresolvedReferences
                self.sqlite_connection.create_function(fn, ff.__code__.co_argcount, ff)

        # logger.debug(
        #     "SQLite3.EXECUTE: "
        #     + " ".join([line.strip() for line in query.split("\n")]).strip()
        # )

        if script:
            self.sqlite_cursor.executescript(query)
        else:
            self.sqlite_cursor.execute(query, params)

        if commit:
            self.sqlite_connection.commit()
        result = self.sqlite_cursor.fetchall()
        if column_names and self.sqlite_cursor.description:
            description = [column[0] for column in self.sqlite_cursor.description]
            result = [description] + result
        # self.sqlite_cursor.close()
        self.sqlite_connection.close()
        # noinspection PyTypeChecker
        return result


class VedisCache:
    def __init__(self, table: str):
        self.table = table

    def __getitem__(self, key: Any) -> None | str:
        with vdb.transaction():
            data = vdb.hget(self.table, key)
            return data.decode() if data else None

    def __setitem__(self, key, value):
        with vdb.transaction():
            vdb.hset(self.table, key, value)

    def __delitem__(self, key):
        with vdb.transaction():
            vdb.hdel(self.table, key)


class Limit:
    def __init__(self, status: int, user_id: int = None, group_id: str = None):
        self.user_id = user_id
        self.group_id = group_id
        self.status = status
        self.user_max_limits = event_limits[status]

    def get_event_limits(self, date: arrow.Arrow | None = None) -> list[tuple[int]]:
        date = date if date else arrow.utcnow()

        try:
            return db.execute(
                """
SELECT (
    SELECT IFNULL(COUNT( * ), 0)
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND DATE(datetime) = :date
) AS count_today,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0)
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND DATE(datetime) = :date
) AS sum_length_today,
(
    SELECT IFNULL(COUNT( * ), 0)
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND STRFTIME('%Y-%m', datetime) = :date_Y_M
) AS count_month,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0)
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND STRFTIME('%Y-%m', datetime) = :date_Y_M
) AS sum_length_month,
(
    SELECT IFNULL(COUNT( * ), 0)
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND STRFTIME('%Y', datetime) = :date_Y
) AS count_year,
(
    SELECT IFNULL(SUM(LENGTH(text)), 0)
      FROM events
     WHERE user_id IS :user_id
           AND group_id IS :group_id
           AND STRFTIME('%Y', datetime) = :date_Y
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
                    "date": f"{date:YYYY-MM-DD}",
                    "date_Y_M": f"{date:YYYY-MM}",
                    "date_Y": f"{date:YYYY}",
                },
            )[0]
        except Error as e:
            raise ApiError(e)

    def is_exceeded_for_events(
        self, date: Arrow | None = None, event_count: int = 0, symbol_count: int = 0
    ) -> bool:
        inf = float("inf")
        actual_limits = self.get_event_limits(date)

        limits_event_count = zip(
            actual_limits[::2],
            tuple(self.user_max_limits.values())[::2],
        )
        limits_symbol_count = zip(
            actual_limits[1::2],
            tuple(self.user_max_limits.values())[1::2],
        )

        return any(
            actual_limit + event_count >= (max_limit or inf)
            for actual_limit, max_limit in limits_event_count
        ) or any(
            actual_limit + symbol_count >= (max_limit or inf)
            for actual_limit, max_limit in limits_symbol_count
        )

    def is_exceeded_for_groups(
        self, create: bool = False, participate: bool = False
    ) -> bool:
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

        return (
            groups_participate + participate > max_groups_participate
            or groups_creator + create > max_groups_creator
        )

    def now_limit_percent(
        self, date: Arrow | None = None
    ) -> list[int, int, int, int, int, int, int, int]:
        actual_limits = self.get_event_limits(date)

        # noinspection PyTypeChecker
        return [
            int((actual_limit / max_limit) * 100)
            for actual_limit, max_limit in zip(
                actual_limits, tuple(self.user_max_limits.values())
            )
        ]


class ExportData:
    def __init__(
        self,
        filename: str,
        user_id: int = None,
        group_id: str = None,
        __sql_where: str = None,
        __sql_params: tuple = None,
    ):
        self.user_id, self.group_id = user_id, group_id
        self.filename = filename
        self.query = f"""
SELECT event_id,
       text,
       datetime,
       statuses,
       adding_time,
       recent_changes_time,
       history
  FROM events
 WHERE user_id IS ?
       AND group_id IS ?
       AND removal_time IS NULL{f" AND ({__sql_where}) LIMIT 400" if __sql_where else ""};
"""
        self.params = (
            user_id,
            group_id,
            *(__sql_params or ()),
        )
        try:
            self.table = db.execute(self.query, params=self.params, column_names=True)
        except Error as e:
            raise ApiError(e)

        self.row_count = len(self.table)

    def csv(self) -> StringIO:
        file = StringIO()
        file.name = self.filename
        file_writer = csv.writer(file)
        file_writer.writerows(self.table)
        file.seek(0)
        return file

    def xml(self) -> BytesIO:
        file = BytesIO()
        file.name = self.filename

        xml_events = xml.Element("events")
        for i, d, s, t, a, r, h in self.table:
            xml_event = xml.SubElement(xml_events, "event")
            xml.SubElement(xml_event, "i").text = f"{i}"
            xml.SubElement(xml_event, "d").text = d
            xml.SubElement(xml_event, "s").text = s
            xml.SubElement(xml_event, "t").text = t
            xml.SubElement(xml_event, "a").text = a
            xml.SubElement(xml_event, "r").text = r
            xml.SubElement(xml_event, "h").text = h
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
        file.write(json.dumps(self.table, ensure_ascii=False))
        file.seek(0)
        return file

    def jsonl(self) -> StringIO:
        file = StringIO()
        file.name = self.filename
        file.writelines(
            json.dumps(line, ensure_ascii=False) + "\n" for line in self.table
        )
        file.seek(0)
        return file

    def export(self, file_format: str = "csv") -> tuple[StringIO | BytesIO, int]:
        if file_format not in ("csv", "xml", "json", "jsonl"):
            raise ValueError('file_format not in ("csv", "xml", "json", "jsonl")')

        return getattr(self, file_format)(), self.row_count


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
    lang: str = "en"
    sub_urls: bool = True
    city: str = "London"
    timezone: int = 0
    notifications: bool = 0
    notifications_time: str = "08:00"
    theme: int = 0

    def get(self, param: str):
        return self.__dict__[param]


@dataclass
class Event:
    """
    user_id: int

    group_id: str

    event_id: int

    text: str

    _datetime: str

    _status: str

    repetition: str

    reference_event_id: int | None

    adding_time: str

    recent_changes_time: str

    removal_time: str

    _history: str = None
    """

    user_id: int
    group_id: str
    event_id: int
    text: str
    _datetime: str
    _status: str
    repetition: str
    reference_event_id: int | None
    adding_time: str
    recent_changes_time: str
    removal_time: str
    _history: str = None

    @property
    def is_delete(self) -> bool:
        return bool(self.removal_time)

    @property
    def date(self) -> str:
        return f"{self.datetime:YYYY-MM-DD}"

    @property
    def time(self) -> str:
        return f"{self.datetime:HH:mm}"

    @property
    def datetime(self) -> Arrow:
        return arrow.get(self._datetime)

    @property
    def history(self) -> list[list[str, list[str, str], str]]:
        return json.loads(self._history)

    @property
    def statuses(self) -> list[str]:
        return json.loads(self._status)

    @property
    def string_statuses(self) -> str:
        return ",".join(self.statuses)

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
 WHERE event_id = :event_id
       AND (
           user_id IS :user_id
           AND group_id IS :group_id
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
        Calculates the number of days until an event is removed from the trash.
        If the event should already be deleted, returns -1.
        """
        if sql_date_pattern.match(self.removal_time):
            _d1 = arrow.utcnow().date()
            _d2 = arrow.get(self.removal_time).date()
            _days = 30 - (_d1 - _d2).days
            return -1 if _days < 0 else _days
        else:
            return 30

    def days_before_event(self, timezone_: int = 0) -> int:
        _date = self.datetime
        n_time = arrow.utcnow().shift(hours=timezone_)
        n_time = arrow.get(n_time.year, n_time.month, n_time.day)
        dates = []

        def prepare_date(date: datetime) -> int:
            return (date - n_time).days

        # Every day
        if self.repetition == "repeat every day":
            return 0

        if self.repetition == "repeat every weekdays":
            weekday = _date.weekday()  # Mon == 0

            if 0 <= weekday <= 4:
                return prepare_date(n_time)

            if weekday == 5:
                return 2

            if weekday == 6:
                return 1

        # Every week
        if self.repetition == "repeat every week":
            now_wd, event_wd = n_time.weekday(), _date.weekday()
            next_date = n_time.shift(days=(event_wd - now_wd + 7) % 7)
            dates.append(next_date)

        # Every month
        elif self.repetition == "repeat every month":
            dt = arrow.get(n_time.year, n_time.month, _date.day)
            day_diff = prepare_date(dt)
            month, year = dt.month, dt.year
            if day_diff >= 0:
                dates.append(dt)
            else:
                if month < 12:
                    dates.append(dt.replace(month=month + 1))
                else:
                    dates.append(dt.replace(year=year + 1, month=1))

        # Every year
        elif self.repetition == "repeat every year":
            dt = arrow.get(n_time.year, _date.month, _date.day)
            if dt.date() < n_time.date():
                dates.append(dt.replace(year=n_time.year + 1))
            else:
                dates.append(dt.replace(year=n_time.year))

        else:
            return prepare_date(self.datetime)

        return prepare_date(min(dates))

    def to_json(self) -> str:
        return json.dumps(
            {
                "user_id": self.user_id,
                "group_id": self.group_id,
                "event_id": self.event_id,
                "text": self.text,
                "datetime": self._datetime,
                "statuses": self.statuses,
                "repetition": self.repetition,
                "reference_event_id": self.reference_event_id,
                "adding_time": self.adding_time,
                "recent_changes_time": self.recent_changes_time,
                "removal_time": self.removal_time,
                "history": self.history,
            },
            ensure_ascii=False,
        )

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "group_id": self.group_id,
            "event_id": self.event_id,
            "text": self.text,
            "datetime": self._datetime,
            "statuses": self.statuses,
            "repetition": self.repetition,
            "reference_event_id": self.reference_event_id,
            "adding_time": self.adding_time,
            "recent_changes_time": self.recent_changes_time,
            "removal_time": self.removal_time,
            "history": self.history,
        }

    @staticmethod
    def de_json(json_string) -> "Event":
        return Event(**json.loads(json_string))

    @property
    def string_repetition(self):
        return repetition_dict.get(self.repetition, "🔕")


@dataclass
class Group:
    group_id: str
    name: str
    owner_id: int
    max_event_id: int
    entry_date: str = None
    member_status: int = None
    token: str = None
    token_create_time: str = None
    icon: bytes = None


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

    @classmethod
    def get_from_token(cls, token: str) -> "User":
        # TODO защита от перебора брутфорса и количества попыток
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
       reg_date
  FROM users
 WHERE token = :token;
""",
                params={"token": token},
            )[0]
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return User(*user)

    @classmethod
    def get_from_user_id(cls, user_id: int) -> "User":
        # TODO защита от перебора брутфорса и количества попыток
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
       reg_date
  FROM users
 WHERE user_id = :user_id;
""",
                params={"user_id": user_id},
            )[0]
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return User(*user)

    @classmethod
    def get_from_password(cls, username: str, password: str) -> "User":
        # TODO защита от перебора брутфорса и количества попыток
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
       reg_date
  FROM users
 WHERE username = :username;
""",
                params={"username": username},
            )[0]

            if not verify_password(user[4], password):
                raise IndexError
        except Error as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return User(*user)

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())})"


class Account:
    def __init__(self, user_id: int, group_id: str = None):
        self.user_id, self.group_id = user_id, group_id
        self.limit = Limit(
            self.user.user_status if not group_id else 0,
            user_id,
            self.group.group_id if group_id else None,
        )
        self.settings: Settings = self.get_settings()

    def __str__(self):
        d = {
            x: y.__dict__ if hasattr(y, "__dict__") else y
            for x, y in self.__dict__.items()
        }
        return str(d)

    @cached_property
    def user(self) -> User:
        return User.get_from_user_id(self.user_id)

    @cached_property
    def group(self) -> Group | None:
        if self.group_id:
            return self.get_group(self.group_id)
        else:
            return None

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

    def now_time(self) -> Arrow:
        """
        Returns arrow.utcnow() taking into account the user's time zone
        """
        return arrow.utcnow().shift(hours=self.settings.timezone)

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

    def create_event(self, text: str, date: Arrow) -> int:
        """

        :param text:
        :param date:
        :return: event_id
        :raise TextIsTooBig: if len(text) >= 3800
        :raise WrongDate:
        :raise LimitExceeded:
        :raise ApiError: sqlite3.Error
        """
        text_len = len(text)

        if text_len >= 3800:
            raise TextIsTooBig

        # TODO
        if not re_date.match(f"{date:DD.MM.YYYY}") or not is_valid_year(date.year):
            raise WrongDate

        if self.limit.is_exceeded_for_events(date, 1, text_len):
            raise LimitExceeded

        # TODO проверка статуса

        try:
            db.execute(
                """
INSERT INTO events (
    event_id,
    user_id,
    group_id,
    text,
    datetime,
    statuses
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
    :text,
    :datetime,
    :statuses
);
""",
                params={
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                    "datetime": f"{date:YYYY-MM-DD HH:mm:ss}",
                    "text": text,
                    "statuses": '["⬜"]',
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

    def get_events(
        self, event_ids: list[int], in_bin: bool = False, order: str = "usual"
    ) -> list[Event]:
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
       AND (removal_time IS NOT NULL) = ?
 ORDER BY {config.sql_order_dict[order]};
""",
                params=(
                    self.safe_user_id,
                    self.group_id,
                    *event_ids,
                    in_bin,
                    self.settings.timezone,
                    self.settings.timezone,
                    self.settings.timezone,
                ),
                functions=(
                    (
                        "DAYS_BEFORE_EVENT",
                        lambda date, repetition: Event(
                            0, "", 0, "", date, "", repetition, None, "", "", "", ""
                        ).days_before_event(self.settings.timezone),
                    ),
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

        # Calculate the number of added characters
        old_text_len, new_text_len = len(event.text), len(text)
        new_symbol_count = (
            0 if new_text_len < old_text_len else new_text_len - old_text_len
        )

        if self.limit.is_exceeded_for_events(event.datetime, 0, new_symbol_count):
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

    def edit_event_datetime(self, event_id: int, date: Arrow) -> None:
        # TODO
        if not is_valid_year(date.year):
            print(date.year)
            raise WrongDate

        event = self.get_event(event_id)

        if self.limit.is_exceeded_for_events(event.datetime, 1, len(event.text)):
            raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET datetime = :datetime
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "datetime": f"{date:YYYY-MM-DD HH:mm:ss}",
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_event_repetition(self, event_id: int, repetition: str | None) -> None:
        try:
            db.execute(
                """
UPDATE events
   SET repetition = :repetition
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "repetition": repetition or "repeat never",
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_event_notification(
        self, event_id: int, notifications_list: list[dict[str, str]]
    ) -> None:
        try:
            db.execute(
                """
UPDATE events
   SET notifications = :notifications
 WHERE event_id = :event_id
       AND user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "notifications": json.dumps(notifications_list, ensure_ascii=False),
                    "event_id": event_id,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_event_status(self, event_id: int, statuses: list[str]) -> None:
        if not self.check_event_exists(event_id):
            raise EventNotFound

        # There cannot be more than 5 statuses
        # The length of one regular status cannot be more than 3 characters\
        # Code language ("💻") cannot be more than 6 characters
        if (
            len(statuses) > 5
            or max(
                # If the length is greater than 6, then the sum of the Boolean (>) value
                # and 3 + result of (>) will be greater than 3
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
                f"""
UPDATE events
   SET statuses = JSON_ARRAY({','.join('?' for _ in statuses)})
 WHERE event_id = ?
       AND user_id IS ?
       AND group_id IS ?;
""",
                params=(
                    *statuses,
                    event_id,
                    self.safe_user_id,
                    self.group_id,
                ),
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def delete_event(self, event_id: int, in_bin=False) -> None:
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

        if self.limit.is_exceeded_for_events(event.datetime, 1, len(event.text)):
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

    def event_history_clear(self, event_id: int) -> None:  # add_time
        if not self.check_event_exists(event_id):
            raise EventNotFound

        try:
            db.execute(
                """
UPDATE events
   SET history = '[]'
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

    def clear_event_history(self, event_id: int) -> None:  # master
        if not self.check_event_exists(event_id):
            raise EventNotFound

        try:
            db.execute(
                """
UPDATE events
   SET history = '[]'
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

    def export_data(
        self,
        filename: str,
        file_format: str = "csv",
        __sql_where: str = None,
        __sql_params: str = None,
    ) -> tuple[StringIO | BytesIO, int]:
        if file_format not in ("csv", "xml", "json", "jsonl"):
            raise ValueError("Format Is Not Valid")

        return ExportData(
            filename, self.safe_user_id, self.group_id, __sql_where, __sql_params
        ).export(file_format)

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

    def add_event_media(
        self, event_id: int, filename: str, media_type: str, media: bytes
    ):
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

        if group_id is not None and group_id != self.group_id:
            return self.get_group_member(user_id, group_id).member_status >= 1

        if self.group_id and self.group.member_status:
            return self.group.member_status >= 1

        return False

    def is_owner(self, group_id: str = None, user_id: int = None) -> bool:
        user_id = user_id or self.user_id

        if (group_id is not None) and group_id != self.group_id:
            return self.get_group_member(user_id, group_id).member_status >= 2

        if self.group_id and self.group.member_status:
            return self.group.member_status >= 2

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
            members = db.execute(
                f"""
SELECT entry_date,
       member_status
  FROM members
 WHERE group_id IN ({','.join('?' for _ in group_ids)})
       AND user_id = :user_id;
""",
                params=(
                    *group_ids,
                    self.user_id,
                ),
            )
        except Error as e:
            raise ApiError(e)

        if not groups or not len(groups) == len(members):
            raise GroupNotFound

        if not members:
            raise NotGroupMember

        lst = []
        for (*group, token, token_create_time), member in zip(groups, members):
            lst.append(Group(*group, *member, token, token_create_time))

        return lst

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

    def get_groups_where_i_member(self, page: int = 1) -> list[Group]:
        page -= 1
        try:
            groups = db.execute(
                """
SELECT groups.group_id,
       groups.name,
       groups.owner_id,
       groups.max_event_id,
       members.entry_date,
       members.member_status,
       groups.token,
       groups.token_create_time
  FROM groups
  JOIN members ON groups.group_id = members.group_id
 WHERE members.user_id = :user_id
       AND members.member_status < 1
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
SELECT groups.group_id,
       groups.name,
       groups.owner_id,
       groups.max_event_id,
       members.entry_date,
       members.member_status,
       groups.token,
       groups.token_create_time
  FROM groups
  JOIN members ON groups.group_id = members.group_id
 WHERE members.user_id = :user_id
       AND members.member_status >= 1
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
SELECT groups.group_id,
       groups.name,
       groups.owner_id,
       groups.max_event_id,
       members.entry_date,
       members.member_status,
       groups.token,
       groups.token_create_time
  FROM groups
  JOIN members ON groups.group_id = members.group_id
 WHERE members.user_id = :user_id
       AND members.member_status >= 2
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

    def get_group_members(
        self, user_ids: list[int], group_id: str = None
    ) -> list[Member]:
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

    def edit_group_member_status(
        self, member_status: int, user_id: int, group_id: str = None
    ) -> None:
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
   SET member_status = :member_status
 WHERE group_id = :group_id
       AND user_id = :user_id;
""",
                params={
                    "member_status": member_status,
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

        if user_id != self.user_id and not self.is_moderator(group_id):
            raise NotEnoughPermissions

        if not self.check_member_exists(user_id, group_id):
            raise NotGroupMember

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
                params={"group_id": group_id},
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

    def get_settings(self):
        return self.get_user_settings()

    def get_user_settings(self) -> Settings:
        try:
            settings = db.execute(
                """
SELECT lang,
       sub_urls,
       city,
       timezone,
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
        timezone_: int = None,
        notifications: Literal[0, 1, 2] | bool = None,
        notifications_time: str = None,
        theme: int = None,
    ) -> None:
        """
        user_id            INT  UNIQUE NOT NULL,
        lang               TEXT DEFAULT 'en',
        sub_urls           INT  CHECK (sub_urls IN (0, 1)) DEFAULT (1),
        city               TEXT DEFAULT 'London',
        timezone           INT  CHECK (-13 < timezone < 13) DEFAULT (0),
        notifications      INT  CHECK (notifications IN (0, 1, 2)) DEFAULT (0),
        notifications_time TEXT DEFAULT "08:00",
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

        if timezone_ is not None:
            if timezone_ not in [j for i in range(-11, 12) for j in (i, str(i))]:
                raise ValueError("timezone must be -12 and less 12")

            update_list.append("timezone")
            self.settings.timezone = int(timezone_)

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
                    "timezone": timezone_,
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
            raise ValueError

        try:
            count_username = db.execute(
                """
SELECT COUNT(username)
  FROM users
 WHERE username = :username;
""",
                params={
                    "username": username,
                },
            )[0][0]
        except Error as e:
            raise ApiError(e)

        if count_username != 0:
            raise NotUniqueUsername

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
                commit=True,
            )
        except Error as e:
            raise ApiError(e)

    def edit_user_password(self, old_password: str, new_password: str) -> None:
        if self.group_id:
            raise Forbidden

        if (not new_password) or (not old_password):
            raise ValueError

        if not verify_password(self.user.password, old_password):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
UPDATE users
   SET password = :password
 WHERE user_id = :user_id;
""",
                params={
                    "password": hash_password(new_password),
                    "user_id": self.user_id,
                },
                commit=True,
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
                commit=True,
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
                commit=True,
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
    if "@" not in email or not re_username.match(username) or not password:
        raise ApiError

    try:
        count_email, count_username = db.execute(
            """
SELECT (
    SELECT COUNT(email)
      FROM users
     WHERE email = :email
),
(
    SELECT COUNT(username)
      FROM users
     WHERE username = :username
);
""",
            params={
                "email": email,
                "username": username,
            },
        )[0]
    except Error as e:
        raise ApiError(e)

    if count_email != 0:
        raise NotUniqueEmail

    if count_username != 0:
        raise NotUniqueUsername

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


def get_account_from_password(
    username: str, password: str, group_id: str = None
) -> Account:
    try:
        user = db.execute(
            """
SELECT user_id,
       password
  FROM users
 WHERE username = :username;
""",
            params={"username": username},
        )[0]

        if not verify_password(user[1], password):
            raise IndexError
    except Error as e:
        raise ApiError(e)
    except IndexError:
        raise UserNotFound

    return Account(user[0], group_id)


def set_user_status(user_id: int, user_status: int) -> None:
    """
    Sets the status for the user with user_id.
    Does NOT conduct any checks
    """
    try:
        db.execute(
            """
UPDATE users
   SET user_status = :user_status
 WHERE user_id = :user_id;
""",
            params={
                "user_status": user_status,
                "user_id": user_id,
            },
            commit=True,
        )
    except Error as e:
        raise ApiError(e)


db = DataBase()
vdb = Vedis(config.VEDIS_PATH)
