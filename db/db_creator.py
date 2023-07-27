from sqlite3 import Error

from db.db import SQL


def create_tables() -> None:
    """
    Создание нужных таблиц
    # ALTER TABLE table ADD COLUMN new_column TEXT
    """
    try:
        SQL(
            """
SELECT event_id, user_id, date, text, isdel, status
FROM events LIMIT 1;
"""
        )
    except Error as e:
        if str(e) == "no such table: events":
            SQL(
                """
CREATE TABLE events (
    event_id  INTEGER,
    user_id   INT,
    date      TEXT,
    text      TEXT,
    isdel     INTEGER DEFAULT (0),
    status    TEXT    DEFAULT '⬜️'
);
""",
                commit=True,
            )
        else:
            quit(f"{e}")

    try:
        SQL(
            """
SELECT
user_id, lang, sub_urls, city, timezone, direction, 
user_status, notifications, notifications_time, user_max_event_id, add_event_date
FROM settings LIMIT 1;
"""
        )
    except Error as e:
        if str(e) == "no such table: settings":
            SQL(
                """
CREATE TABLE settings (
    user_id            INT  NOT NULL UNIQUE ON CONFLICT ROLLBACK,
    lang               TEXT DEFAULT 'ru',
    sub_urls           INT  DEFAULT (1),
    city               TEXT DEFAULT 'Москва',
    timezone           INT  DEFAULT (3),
    direction          TEXT DEFAULT '⬇️',
    user_status        INT  DEFAULT (0),
    notifications      INT DEFAULT (0),
    notifications_time TEXT DEFAULT '08:00',
    user_max_event_id  INT  DEFAULT (1),
    add_event_date     INT  DEFAULT (0)
);
""",
                commit=True,
            )
        else:
            quit(f"{e}")
