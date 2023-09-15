import re
import json
import logging
from time import time
from typing import Literal
from datetime import datetime
from sqlite3 import Error, connect
from contextlib import contextmanager

from vedis import Vedis

import todoapi.config as config


limits = {
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
        "max_symbol_month": 50000,
        "max_event_year": 1000,
        "max_symbol_year": 120000,
        "max_event_all": 2000,
        "max_symbol_all": 200000,
    },
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
    ) -> list[tuple[int | str | bytes, ...], ...]:
        """
        Выполняет SQL запрос
        Пробовал через with, но оно не закрывало файл

        :param query: Запрос
        :param params: Параметры запроса (необязательно)
        :param commit: Нужно ли сохранить изменения? (необязательно, по умолчанию False)
        :param column_names: Названия столбцов вставить в результат.
        :return: Результат запроса
        """
        self.sqlite_connection = connect(config.DATABASE_PATH)
        self.sqlite_cursor = self.sqlite_connection.cursor()
        logging.debug(
            "    " + " ".join([line.strip() for line in query.split("\n")]).strip()
        )

        self.sqlite_cursor.execute(query, params)
        if commit:
            self.sqlite_connection.commit()
        result = self.sqlite_cursor.fetchall()
        if column_names:
            description = [column[0] for column in self.sqlite_cursor.description]
            result = [description] + result
        # self.sqlite_cursor.close()
        self.sqlite_connection.close()
        return result


class Event:
    """
    Событие
    """

    def __init__(
        self,
        event_id: int,
        date: str = "now",
        text: str = "",
        status: str = "⬜️",
        removal_time: str = "0",
        adding_time: str = "",
        recent_changes_time: str = "",
    ):
        self.event_id = event_id
        self.date = date
        self.text = text
        self.status = status
        self.removal_time = removal_time
        self.adding_time = adding_time
        self.recent_changes_time = recent_changes_time
        self._sql_date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")

    def days_before_delete(self) -> int:
        """
        Вычисляет количество дней до удаления события из корзины.
        Если событие уже должно быть удалено, возвращает -1.
        """
        if self._sql_date_pattern.match(self.removal_time):
            _d1 = datetime.utcnow()
            _d2 = datetime(*[int(i) for i in self.removal_time.split("-")])
            _days = 30 - (_d1 - _d2).days
            return -1 if _days < 0 else _days
        else:
            return 30

    def to_json(self) -> str:
        return json.dumps(
            {
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


class UserSettings:
    """
    Настройки для пользователя

    Параметры:
    .user_id            ID пользователя
    .lang               Язык
    .sub_urls           Сокращать ли ссылки
    .city               Город
    .timezone           Часовой пояс
    .direction          Направление вывода на языке sql
    .user_status        Обычный, Премиум, Админ (0, 1, 2)
    .notifications      1 or 0
    .notifications_time 08:00  08:00;09:30

    Функции
    .get_user_settings()
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        (
            self.lang,
            self.sub_urls,
            self.city,
            self.timezone,
            self.direction,
            self.user_status,
            self.notifications,
            self.notifications_time,
        ) = self._get_user_settings()

    def _get_user_settings(
        self,
    ) -> tuple[str, int, str, int, str, Literal[-1, 0, 1, 2], int, str]:
        """
        Возвращает список из настроек для пользователя self.user_id
        """
        query = """
SELECT lang,
       sub_urls,
       city,
       timezone,
       direction,
       user_status,
       notifications,
       notifications_time
  FROM settings
 WHERE user_id = ?;
"""

        try:
            return db.execute(query, params=(self.user_id,))[0]
        except (Error, IndexError):
            logging.info(f"Добавляю нового пользователя ({self.user_id})")
            db.execute(
                """
INSERT INTO settings (user_id)
VALUES (?);
""",
                params=(self.user_id,),
                commit=True,
            )
        return db.execute(query, params=(self.user_id,))[0]

    # def __setattr__(self, key, value):
    #     setattr(self, key, value)
    def log(self, action: str, text: str):
        text = text.replace("\n", "\\n")
        logging.info(f"[{self.user_id:<10}][{self.user_status}] {action:<7} {text}")

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "lang": self.lang,
            "sub_urls": self.sub_urls,
            "city": self.city,
            "timezone": self.timezone,
            "direction": self.direction,
            "user_status": self.user_status,
            "notifications": self.notifications,
            "notifications_time": self.notifications_time,
        }


class Limit:
    def __init__(self, user_id: int, user_status: int, date=None):
        self.user_id = user_id

        if not date:
            self.date = datetime.now().strftime("%d.%m.%Y")
        else:
            self.date = date

        (
            self.limit_event_day,
            self.limit_symbol_day,
            self.limit_event_month,
            self.limit_symbol_month,
            self.limit_event_year,
            self.limit_symbol_year,
            self.limit_event_all,
            self.limit_symbol_all,
        ) = self.get_limits()

        self.user_status = user_status
        user_limits = limits[self.user_status]

        self.max_event_day = user_limits["max_event_day"]
        self.max_symbol_day = user_limits["max_symbol_day"]
        self.max_event_month = user_limits["max_event_month"]
        self.max_symbol_month = user_limits["max_symbol_month"]
        self.max_event_year = user_limits["max_event_year"]
        self.max_symbol_year = user_limits["max_symbol_year"]
        self.max_event_all = user_limits["max_event_all"]
        self.max_symbol_all = user_limits["max_symbol_all"]

    def is_exceeded(self, *, event_count: int = 0, symbol_count: int = 0) -> bool:
        inf = float("inf")  # Бесконечность

        # Если хоть один лимит нарушен, то возвращает False
        # Если лимит отсутствует, то он бесконечный
        return (
            self.limit_event_day + event_count >= (self.max_event_day or inf)
            or self.limit_symbol_day + symbol_count >= (self.max_symbol_day or inf)
            or self.limit_event_month + event_count >= (self.max_event_month or inf)
            or self.limit_symbol_month + symbol_count >= (self.max_symbol_month or inf)
            or self.limit_event_year + event_count >= (self.max_event_year or inf)
            or self.limit_symbol_year + symbol_count >= (self.max_symbol_year or inf)
            or self.limit_event_all + event_count >= (self.max_event_all or inf)
            or self.limit_symbol_all + symbol_count >= (self.max_symbol_all or inf)
        )

    def now_limit_percent(self) -> list[int, int, int, int, int, int, int, int]:
        return [
            int((self.limit_event_day / self.max_event_day) * 100),
            int((self.limit_symbol_day / self.max_symbol_day) * 100),
            int((self.limit_event_month / self.max_event_month) * 100),
            int((self.limit_symbol_month / self.max_symbol_month) * 100),
            int((self.limit_event_year / self.max_event_year) * 100),
            int((self.limit_symbol_year / self.max_symbol_year) * 100),
            int((self.limit_event_all / self.max_event_all) * 100),
            int((self.limit_symbol_all / self.max_symbol_all) * 100),
        ]

    def get_limits(self):
        return db.execute(
            """
SELECT 
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               date = :date
    ) AS count_today,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               date = :date
    ) AS sum_length_today,
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 4, 7) = :date_3
    ) AS count_month,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 4, 7) = :date_3
    ) AS sum_length_month,
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 7, 4) = :date_6
    ) AS count_year,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 7, 4) = :date_6
    ) AS sum_length_year,
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id
    ) AS total_count,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id
    ) AS total_length;
""",
            params={
                "user_id": self.user_id,
                "date": self.date,
                "date_3": self.date[3:],
                "date_6": self.date[6:],
            },
        )[0]


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
