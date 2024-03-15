import json
import logging
from time import time
from uuid import uuid4
from io import StringIO
from datetime import datetime
from typing import Callable, Any
from sqlite3 import Error, connect
from contextlib import contextmanager

from vedis import Vedis
from oauthlib.common import generate_token

import config
from todoapi.exceptions import *
from todoapi.utils import sql_date_pattern, re_email, re_username

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
        self.sqlite_connection = connect(config.DATABASE_PATH)
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


class Cooldown:
    """
    Возвращает True если прошло больше времени
    MyCooldown = Cooldown(cooldown_time, {})
    MyCooldown.check(chat_id)
    """

    def __init__(self, vedis_path: str, time_sec: int):
        self._db = Vedis(vedis_path)
        self._time_sec = time_sec

    def check(self, key: str | int, update_dict: bool):
        """
        :param key: Ключ по которому проверять словарь
        :param update_dict: Отвечает за обновление словаря
        Если True то после каждого обновления время будет обнуляться
        :return: (bool, int(time_difference))
        """
        key = f"{key}"
        t = time()
        result = True, 0

        try:
            if (localtime := (t - float(self._db[key]))) < self._time_sec:
                result = False, int(self._time_sec - int(localtime))
        except KeyError:
            pass

        if update_dict or result[0]:
            with self._db.transaction():
                self._db[key] = t
                self._db.commit()

        return result


db = DataBase()
export_cooldown = Cooldown(config.VEDIS_PATH, 30 * 60)


class Limit:
    def __init__(self, *, user_id: int = None, group_id: str = None, status: int):
        self.user_id = user_id
        self.group_id = group_id
        self.status = status
        self.user_max_limits = event_limits[status]

    def get_event_limits(self, date: str | datetime = None) -> list[tuple[int]]:
        date = date if date else datetime.now().strftime("%d.%m.%Y")

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

        limits_event_count = zip(actual_limits[::2], self.user_max_limits[::2])
        limits_symbol_count = zip(actual_limits[1::2], self.user_max_limits[1::2])

        return (
            any(
                actual_limit + event_count >= (max_limit or inf)
                for actual_limit, max_limit in limits_event_count
            ) or any(
                actual_limit + symbol_count >= (max_limit or inf)
                for actual_limit, max_limit in limits_symbol_count
            )
        )

    def test_edit_group(self) -> bool:
        pass

    def now_limit_percent(self, date: str | datetime = None) -> list[int, int, int, int, int, int, int, int]:
        actual_limits = self.get_event_limits(date)

        # noinspection PyTypeChecker
        return [
            int((actual_limit / max_limit) * 100)
            for actual_limit, max_limit in zip(actual_limits, self.user_max_limits)
        ]


class DataBaseUser:
    def __init__(
        self,
        user_id: int,
        token: str,
        username: str,
        password: str,
        email: str,
        user_status: int = 0,
        max_event_id: int = 1,
        icon: bytes = None,
        reg_date: str = "",
        token_create_time: str = "",
        chat_id: int = None,
    ):
        self.user_id = user_id
        self.token = token
        self.username = username
        self.password = password
        self.email = email
        self.user_status = user_status
        self.max_event_id = max_event_id
        self.icon = icon
        self.reg_date = reg_date
        self.token_create_time = token_create_time
        self.chat_id = chat_id


class DataBaseGroup:
    def __init__(
        self,
        group_id: str,
        user_id: int,
        chat_id: int,
        token: str,
        name: str,
        icon: bytes = None,
        max_event_id: int = 1,
        token_create_time: str = "",
    ):
        self.group_id = group_id
        self.user_id = user_id
        self.chat_id = chat_id
        self.token = token
        self.name = name
        self.icon = icon
        self.max_event_id = max_event_id
        self.token_create_time = token_create_time


class CanInteractEvents:
    def create_event(
        self,
        date: str,
        text: str,
        user_status: str | None = None,
        user_id: int | None = None,
        group_id: str | None = None,
    ) -> bool:
        if not (
            (user_id or getattr(self, "user_id"))
            or (group_id or getattr(self, "group_id"))
        ):
            raise EventNotFound

        # TODO проверка на лимит
        is_exceed = ...
        if is_exceed:
            raise LimitExceeded

        try:
            db.execute(
                """
INSERT
""",
                params={
                    "date": date,
                    "text": text,
                    "user_status": user_status,
                    "user_id": user_id or getattr(self, "user_id"),
                    "group_id": group_id or getattr(self, "group_id"),
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def get_event(
        self, event_id: int, user_id: int = None, group_id: str = None
    ) -> "Event":
        return self.get_events([event_id], user_id, group_id)[0]

    def get_events(
        self, event_ids: list[int], user_id: int = None, group_id: str = None
    ) -> list["Event"]:
        if not (
            (user_id or getattr(self, "user_id", 0))
            or (group_id or getattr(self, "group_id", 0))
        ):
            raise EventNotFound

        try:
            events = db.execute(
                """
SELECT *
  FROM events
 WHERE event_id IN :event_id
       AND (
           user_id = :user_id
           OR group_id = :group_id
       )
""",
                params={
                    "event_id": event_ids,
                    "user_id": user_id or getattr(self, "user_id", 0),
                    "group_id": group_id or getattr(self, "group_id", 0),
                },
            )[0]
        except Error:
            raise ApiError

        if not events:
            raise EventNotFound

        return [Event(*event) for event in events]

    def edit_event_text(self, event_id: int, text: str) -> bool:
        if len(text) >= 3800:
            raise TextIsTooBig

        event = self.get_event(event_id)
        if not event:
            raise EventNotFound

        # Вычисляем количество добавленных символов
        old_text_len, new_text_len = len(event.text), len(text)
        new_symbol_count = (
            0 if new_text_len < old_text_len else new_text_len - old_text_len
        )

        # TODO проверка лимита
        # if self.entity.check_limit(event.date, symbol_count=new_symbol_count)[1] is True:
        #     raise LimitExceeded

        try:
            db.execute(
                """
UPDATE events
   SET text = :text
 WHERE event_id = :event_id
       AND (user_id = :user_id OR group_id = :group_id);
""",
                params={
                    "text": text,
                    "event_id": event_id,
                    "user_id": getattr(self, "user_id"),
                    "group_id": getattr(self, "group_id"),
                },
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def edit_event_date(self, event_id: int, date: str) -> bool:
        pass

    def edit_event_status(self, event_id: int, status: str) -> bool:
        pass

    def delete_event(self, event_id: int) -> bool:
        pass

    def delete_event_to_bin(self, event_id: int) -> bool:
        pass

    def recover_event(self, event_id: int) -> bool:
        pass

    def clear_basket(
        self, user_id: int | None = None, group_id: str | None = None
    ) -> bool:
        pass

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


class CanInteractUsers(DataBaseUser):
    @staticmethod
    def get_user(token: str) -> "User":
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

        if not user:
            raise UserNotFound

        return User(*user)

    @staticmethod
    def get_user_from_password(username: str, password: str) -> "User":
        # TODO защита от перебора брутфорса и количества попыток
        try:
            user = db.execute(
                """
SELECT *
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

        return User(*user)

    @staticmethod
    def get_user_from_user_id(user_id: int) -> "User":
        """
        Делает тоже самое, что и get_user, но заполняет только публичные поля.
        """
        try:
            user = db.execute(
                """
SELECT username,
       user_status,
       icon,
       reg_date,
       chat_id
  FROM users
 WHERE user_id = :user_id;
""",
                params={"user_id": user_id},
            )[0]
        except Error:
            raise ApiError
        except IndexError:
            raise UserNotFound

        username, user_status, icon, reg_date, chat_id = user
        return User(
            user_id=user_id,
            token=None,
            username=username,
            password=None,
            email=None,
            user_status=user_status,
            max_event_id=None,
            icon=icon,
            reg_date=reg_date,
            token_create_time=None,
            chat_id=chat_id,
        )

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

    def delete_user(self, user_id: int = None) -> bool:
        user_id = user_id or getattr(self, "user_id")
        self.get_user_from_user_id(user_id)  # raise UserNotFound if user not found
        try:
            db.execute(
                """
DELETE FROM users
      WHERE user_id = :user_id;
""",
                params={"user_id": user_id},
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def get_user_settings(self, user_id: int = None) -> "Settings":
        user_id = user_id or getattr(self, "user_id")
        self.get_user_from_user_id(user_id)  # raise UserNotFound if user not found

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
                params={"user_id": user_id},
            )[0]
        except Error:
            raise ApiError

        if not settings:
            raise ApiError

        return Settings(*settings)

    def set_user_settings(self) -> "Settings":
        pass

    @staticmethod
    def create_user(email: str, username: str, password: str) -> bool:
        if not re_email.match(email):
            raise ApiError

        if not re_username.match(username):
            raise ApiError

        try:
            db.execute(
                """
INSERT INTO users (user_id, token, email, username, password)
VALUES ((SELECT IFNULL(MAX(user_id), 0) + 1 FROM users), :token, :email, :username, :password);
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


class CanInteractTelegramUsers(CanInteractUsers):
    @staticmethod
    def get_user_from_telegram_chat_id(chat_id: int) -> "User":
        try:
            user = db.execute(
                """
SELECT user_id,
       username,
       user_status,
       icon,
       reg_date
  FROM users
 WHERE chat_id = :chat_id;
""",
                params={"chat_id": chat_id},
            )[0]
        except Error:
            raise ApiError
        except IndexError:
            raise UserNotFound

        user_id, username, user_status, icon, reg_date = user
        return User(
            user_id=user_id,
            token=None,
            username=username,
            password=None,
            email=None,
            user_status=user_status,
            max_event_id=None,
            icon=icon,
            reg_date=reg_date,
            token_create_time=None,
            chat_id=chat_id,
        )

    def set_user_telegram_chat_id(self, chat_id: int | None = None, user_id: int = None) -> bool:
        user_id = user_id or getattr(self, "user_id")

        # TODO Определиться с системой изменений и требуемых аргументов
        # TODO Проверка на существование пользователя
        try:
            db.execute(
                """
UPDATE users
   SET chat_id = :chat_id
 WHERE user_id = :user_id;
""",
                params={"chat_id": chat_id, "user_id": user_id},
                commit=True,
            )
        except Error:
            raise ApiError

        return True

    def delete_user_telegram_chat_id(self) -> bool:
        pass


class CanInteractGroups:
    def get_group(self, group_id: str) -> "Group":
        return self.get_groups([group_id])[0]

    @classmethod
    def get_groups(cls, group_id: list[str]) -> list["Group"]:
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

    def get_groups_by_user_id(self, user_id: int | None = None) -> list["Group"]:
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

    def get_group_member(self, group_id: str, user_id: int) -> "Member":
        pass

    def get_group_members(self, group_id: str, user_id_list: list[int] = None) -> list["Member"]:
        pass

    def add_group_member(self, group_id: str, user_id: int) -> bool:
        pass


class CanAdministerGroups(CanInteractGroups):
    def create_group(self, name: str, icon: bytes = None) -> bool:
        # TODO Проверка лимита на количество групп
        user_id = getattr(self, "user_id")
        try:
            db.execute(
                """
INSERT INTO groups (group_id, user_id, token, name, icon)
VALUES (:group_id, :user_id, :token, :name, :icon);
""",
                params={
                    "group_id": uuid4(),
                    "user_id": user_id,
                    "token": generate_token(length=32),
                    "name": name,
                    "icon": icon,
                },
            )
        except Error:
            raise ApiError

        return True

    def get_groups_where_i_admin(self, user_id: int | None = None) -> list["Group"]:
        user_id = user_id or getattr(self, "user_id")
        try:
            groups = db.execute(
                """
SELECT *
  FROM groups
 WHERE group_id = (
    SELECT group_id
      FROM members
     WHERE user_id = :user_id AND member_status >= 1;
);
""",
                params={"user_id": user_id},
            )
        except Error:
            raise ApiError

        return groups

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


class CanInteractTelegramGroups(CanInteractGroups):
    @staticmethod
    def get_group_from_telegram_chat_id(chat_id: int) -> "Group":
        try:
            group = db.execute(
                """
SELECT group_id,
       user_id,
       chat_id,
       token,
       name,
       icon,
       max_event_id,
       token_create_time
  FROM groups
 WHERE chat_id = :chat_id;
""",
                params={"chat_id": chat_id},
            )[0]
        except Error:
            raise ApiError

        if not group:
            raise UserNotFound

        group_id, user_id, chat_id, token, name, icon, max_event_id, token_create_time = group
        return Group(
            group_id=group_id,
            user_id=user_id,
            chat_id=chat_id,
            token=token,
            name=name,
            icon=icon,
            max_event_id=max_event_id,
            token_create_time=token_create_time
        )

    def set_group_telegram_chat_id(self) -> bool:
        pass

    def delete_group_telegram_chat_id(self) -> bool:
        pass

    def get_group_settings(self, group_id: str = None) -> "Settings":
        pass

    def set_group_settings(self) -> bool:
        pass


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


class Group(CanInteractTelegramGroups):
    def __init__(
        self,
        group_id: str,
        user_id: int,
        chat_id: int,
        token: str,
        name: str,
        icon: bytes = None,
        max_event_id: int = 1,
        token_create_time: str = "",
    ):
        self.group_id = group_id
        self.user_id = user_id
        self.chat_id = chat_id
        self.token = token
        self.name = name
        self.icon = icon
        self.max_event_id = max_event_id
        self.token_create_time = token_create_time

    def is_owner(self, user_id: int) -> bool:
        return self.user_id == user_id

    def is_moderator(self, user_id: int) -> bool:
        try:
            result = db.execute(
                """
SELECT member_status
  FROM member
 WHERE group_id = :group_id
       AND user_id = :user_id;
""",
                params={
                    "user_id": user_id,
                    "group_id": self.group_id,
                },
            )
        except ApiError:
            raise ApiError

        if not result:
            raise NotGroupMember

        member_status = result[0]
        return member_status > 1 or self.is_owner(user_id)

    @property
    def members(self) -> list["Member"]:
        return self.get_group_members(self.group_id)


class Event:
    def __init__(
        self,
        event_id: int,
        user_id: int = None,
        group_id: str = None,
        date: str = None,
        text: str = None,
        status: str = "⬜️",
        adding_time: str = "",
        recent_changes_time: str = "",
        removal_time: str = "",
        history: str = "[]",
    ):
        self.event_id = event_id
        self.user_id = user_id
        self.group_id = group_id
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


class User(CanInteractEvents, CanInteractTelegramUsers, CanAdministerGroups):
    def __init__(
        self,
        user_id: int,
        token: str,
        username: str,
        password: str,
        email: str,
        user_status: int = 0,
        max_event_id: int = 1,
        icon: bytes = None,
        reg_date: str = "",
        token_create_time: str = "",
        chat_id: int = None,
    ):
        super().__init__(
            user_id,
            token,
            username,
            password,
            email,
            user_status,
            max_event_id,
            icon,
            reg_date,
            token_create_time,
            chat_id,
        )

    @property
    def settings(self):
        return self.get_user_settings()

    @property
    def groups(self):
        return self.get_groups_by_user_id()
