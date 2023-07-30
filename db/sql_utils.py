from typing import Literal
from sqlite3 import Error

import logging
from db.db import SQL


def sqlite_format_date(_column, _quotes="", _sep="-"):
    """SUBSTR({column}, 7, 4) || '{sep}' || SUBSTR({column}, 4, 2) || '{sep}' || SUBSTR({column}, 1, 2)"""
    return f"""
SUBSTR({_quotes}{_column}{_quotes}, 7, 4) || '{_sep}' || 
SUBSTR({_quotes}{_column}{_quotes}, 4, 2) || '{_sep}' || 
SUBSTR({_quotes}{_column}{_quotes}, 1, 2)"""


def sqlite_format_date2(_date):
    """12.34.5678 -> 5678-34-12"""
    return "-".join(_date.split(".")[::-1])


def create_event(user_id: int, date: str, text: str) -> bool:
    """
    Создание события
    """
    try:
        SQL(
            f"""
INSERT INTO events (event_id, user_id, date, text, adding_time)
VALUES (
  COALESCE(
    (
      SELECT user_max_event_id
      FROM settings
      WHERE user_id = {user_id}
    ),
    1
  ),
  {user_id}, '{date}', '{text}', DATETIME()
);
""",
            commit=True,
        )
        SQL(
            f"""
UPDATE settings
SET user_max_event_id = user_max_event_id + 1
WHERE user_id = {user_id};
""",
            commit=True,
        )
        return True
    except Error as e:
        logging.info(
            f'[sql_utils.py -> create_event] Error "{e}"  arg: {user_id=}, {date=}, {text=}'
        )
        return False


def pagination(
    WHERE: str,
    direction: Literal["ASC", "DESC"] = "DESC",
    max_group_len=10,
    max_group_symbols_count=2500,
) -> list[str]:
    data = SQL(
        f"""
SELECT event_id, LENGTH(text)
FROM events
WHERE {WHERE}
ORDER BY {sqlite_format_date('date')} {direction}
LIMIT 400;
"""
    )
    _result = []
    group = []
    group_sum = 0

    for event_id, text_len in data:
        event_id = str(event_id)
        if (
            len(group) < max_group_len
            and group_sum + text_len <= max_group_symbols_count
        ):
            group.append(event_id)
            group_sum += text_len
        else:
            if group:
                _result.append(",".join(group))
            group = [event_id]
            group_sum = text_len

    if group:
        _result.append(",".join(group))

    return _result
