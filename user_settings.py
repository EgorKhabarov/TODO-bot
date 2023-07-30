from typing import Literal
from sqlite3 import Error

import logging
from db.db import SQL


class UserSettings:
    """
    Настройки для пользователя

    Параметры:
    .user_id            ID пользователя
    .lang               Язык
    .sub_urls           Сокращать ли ссылки
    .city               Город
    .timezone           Часовой пояс
    .direction          Направление вывода
    .direction_sql      Направление вывода на языке sql
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
        self.direction_sql = {"⬇️": "DESC", "⬆️": "ASC"}[self.direction]

    def _get_user_settings(
        self,
    ) -> tuple[str, int, str, int, str, Literal[-1, 0, 1, 2], int, str]:
        """
        Возвращает список из настроек для пользователя self.user_id
        """
        query = f"""
SELECT 
    lang, sub_urls, city, timezone, direction,
    user_status, notifications, notifications_time
FROM settings WHERE user_id={self.user_id};
"""
        try:
            return SQL(query)[0]
        except (Error, IndexError):
            logging.info(f"Добавляю нового пользователя ({self.user_id})")
            SQL(f"INSERT INTO settings (user_id) VALUES ({self.user_id});", commit=True)
        return SQL(query)[0]

    def log(self, action: str, text: str):
        text = text.replace("\n", "\\n")
        logging.info(f"[{self.user_id:<10}][{self.user_status}] {action:<7} {text}")
