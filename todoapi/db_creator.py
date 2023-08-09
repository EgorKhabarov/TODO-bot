from sqlite3 import Error
from todoapi.types import db


def create_tables() -> None:
    """
    Создание нужных таблиц
    # ALTER TABLE table ADD COLUMN new_column TEXT
    """
    with db.connection(), db.cursor():
        try:
            db.execute(
                """
SELECT event_id,
       user_id,
       date,
       text,
       status,
       removal_time,
       adding_time,
       recent_changes_time
  FROM events
 LIMIT 1;
"""
            )
        except Error as e:
            if str(e) == "no such table: events":
                db.execute(
                    """
CREATE TABLE events (
    user_id             INT  NOT NULL,
    event_id            INT  NOT NULL,
    date                TEXT NOT NULL,
    text                TEXT NOT NULL,
    status              TEXT DEFAULT '⬜️',
    removal_time        TEXT DEFAULT (0),
    adding_time         TEXT DEFAULT (DATETIME()),
    recent_changes_time TEXT DEFAULT (0),
    CONSTRAINT unique_user_id_and_event_id UNIQUE (
        user_id,
        event_id
    )
);
""",
                    commit=True,
                )
                db.execute(
                    """
CREATE TRIGGER trigger_recent_changes_time
         AFTER UPDATE OF date,
                         text,
                         status
            ON events
      FOR EACH ROW
BEGIN
    UPDATE events
       SET recent_changes_time = DATETIME() 
     WHERE event_id = NEW.event_id;
END;
""",
                    commit=True,
                )
            else:
                quit(f"{e}")

        try:
            db.execute(
                """
SELECT user_id,
       userinfo,
       registration_date,
       lang,
       sub_urls,
       city,
       timezone,
       direction,
       user_status,
       notifications,
       notifications_time,
       user_max_event_id,
       add_event_date
  FROM settings
 LIMIT 1;
"""
            )
        except Error as e:
            if str(e) == "no such table: settings":
                db.execute(
                    """
CREATE TABLE settings (
    user_id            INT  NOT NULL
                            UNIQUE ON CONFLICT ROLLBACK,
    userinfo           TEXT DEFAULT (''),
    registration_date  TEXT DEFAULT (DATETIME()),
    lang               TEXT DEFAULT 'ru',
    sub_urls           INT  DEFAULT (1) 
                            CHECK (sub_urls IN (0, 1)),
    city               TEXT DEFAULT 'Москва',
    timezone           INT  DEFAULT (3) 
                            CHECK (-13 < timezone < 13),
    direction          TEXT DEFAULT 'DESC'
                            CHECK (direction IN ('DESC', 'ASC')),
    user_status        INT  DEFAULT (0),
    notifications      INT  DEFAULT (0) 
                            CHECK (notifications IN (0, 1)),
    notifications_time TEXT DEFAULT '08:00',
    user_max_event_id  INT  DEFAULT (1),
    add_event_date     INT  DEFAULT (0) 
);
""",
                    commit=True,
                )
            else:
                quit(f"{e}")
