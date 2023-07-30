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
SELECT event_id, user_id, date, text,
status, isdel, adding_time, recent_changes
FROM events LIMIT 1;
"""
        )
    except Error as e:
        if str(e) == "no such table: events":
            SQL(
                """
CREATE TABLE events (
    event_id       INT,
    user_id        INT,
    date           TEXT,
    text           TEXT,
    status         TEXT DEFAULT '⬜️',
    isdel          INT  DEFAULT (0),
    adding_time    TEXT,
    recent_changes TEXT DEFAULT (0)
);
""",
                commit=True,
            )
        else:
            quit(f"{e}")

    try:
        SQL(
            """
SELECT user_id, userinfo, lang, sub_urls, city,
timezone, direction, user_status, notifications,
notifications_time, user_max_event_id, add_event_date
FROM settings LIMIT 1;
"""
        )
    except Error as e:
        if str(e) == "no such table: settings":
            SQL(
                """
CREATE TABLE settings (
    user_id            INT  NOT NULL UNIQUE ON CONFLICT ROLLBACK,
    userinfo           TEXT DEFAULT '',
    lang               TEXT DEFAULT 'ru',
    sub_urls           INT  DEFAULT (1),
    city               TEXT DEFAULT 'Москва',
    timezone           INT  DEFAULT (3),
    direction          TEXT DEFAULT '⬇️',
    user_status        INT  DEFAULT (0),
    notifications      INT  DEFAULT (0),
    notifications_time TEXT DEFAULT '08:00',
    user_max_event_id  INT  DEFAULT (1),
    add_event_date     INT  DEFAULT (0)
);
""",
                commit=True,
            )
        else:
            quit(f"{e}")
