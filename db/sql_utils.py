from typing import Literal
from sqlite3 import Error

import logging
from db.db import SQL


def sqlite_format_date(_column, _quotes="", _sep="-"):
    """SUBSTR({column}, 7, 4) || '{sep}' || SUBSTR({column}, 4, 2) || '{sep}' || SUBSTR({column}, 1, 2)"""
    return f"""
SUBSTR({_quotes}{_column}{_quotes}, 7, 4) || '{_sep}' || 
SUBSTR({_quotes}{_column}{_quotes}, 4, 2) || '{_sep}' || 
SUBSTR({_quotes}{_column}{_quotes}, 1, 2)
"""


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
INSERT INTO events(event_id, user_id, date, text)
VALUES(
  COALESCE((SELECT user_max_event_id FROM settings WHERE user_id = {user_id}), 1),
  {user_id}, '{date}', '{text}'
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
            f'[func.py -> create_event] Error "{e}"  arg: {user_id=}, {date=}, {text=}'
        )
        return False


def get_values(
    column_to_limit: str,
    column_to_order: str,
    column_to_return: str,
    WHERE: str,
    table: str,
    MAXLEN: int = 2500,
    MAXEVENTCOUNT: int = 10,
    direction: Literal["ASC", "DESC"] = "DESC",
) -> list[tuple[int | str | bytes, ...], ...]:
    """
    Возвращает результаты по условиям WHERE, разделённые по условиям MAXLEN и MAXEVENTCOUNT на 'страницы'

    :param column_to_limit: Столбец для ограничения
    :param column_to_order: Столбец для сортировки (например id)
    :param column_to_return: Столбец для return (например id)
    :param WHERE:           Условие выбора строк из таблицы
    :param table:           Название таблицы
    :param MAXLEN:          Максимальная длинна символов в одном диапазоне
    :param MAXEVENTCOUNT:   Максимальное количество строк в диапазоне
    :param direction:       Направление сбора строк ("ASC" or "DESC")
    """
    column = "end_id" if direction == "DESC" else "start_id"
    query = f"""
WITH numbered_table AS (
  SELECT 
      ROW_NUMBER() OVER (ORDER BY {column_to_order} {direction}) AS row_num, 
      {column_to_return} AS order_column, 
      LENGTH({column_to_limit}) as len
  FROM {table}
  WHERE {WHERE}
  LIMIT 400
),
temp_table AS (
  SELECT
      numbered_table.row_num,
      numbered_table.order_column,
      numbered_table.len,
      numbered_table.order_column AS {column},
      numbered_table.len AS sum_len,
      1 AS group_id,
      1 AS event_count
  FROM numbered_table 
  WHERE numbered_table.row_num = 1
  UNION ALL
  SELECT
      numbered_table.row_num,
      numbered_table.order_column,
      numbered_table.len,
    CASE 
        WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} 
        THEN temp_table.{column}                     
        ELSE numbered_table.order_column 
    END AS {column},
    CASE 
        WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} 
        THEN temp_table.sum_len + numbered_table.len 
        ELSE numbered_table.len          
    END AS sum_len,
    CASE 
        WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} 
        THEN temp_table.group_id                     
        ELSE temp_table.group_id + 1     
    END AS group_id,
    CASE 
        WHEN temp_table.sum_len + numbered_table.len <= {MAXLEN} AND temp_table.event_count < {MAXEVENTCOUNT} 
        THEN temp_table.event_count + 1              
        ELSE 1                           
    END AS event_count
  FROM numbered_table JOIN temp_table ON numbered_table.row_num = temp_table.row_num + 1
)
SELECT 
    GROUP_CONCAT(COALESCE(numbered_table.order_column, ''), ',') AS ids
    -- , SUM(numbered_table.len) AS sum_len
FROM numbered_table
JOIN temp_table ON numbered_table.row_num = temp_table.row_num
GROUP BY temp_table.group_id;
"""
    data = SQL(query)
    return data


def pagination(
    WHERE: str,
    direction: Literal["ASC", "DESC"] = "DESC",
    max_group_len=10,
    max_group_symbols_count=2500,
) -> list[str]:
    data = SQL(
        f"""
SELECT event_id, LENGTH(text) FROM events
WHERE {WHERE}
ORDER BY {sqlite_format_date('date')} {direction}
LIMIT 400
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
