from typing import Literal

from todoapi.types import db
from todoapi.utils import sqlite_format_date


def sqlite_format_date2(_date):
    """12.34.5678 -> 5678-34-12"""
    return "-".join(_date.split(".")[::-1])


def pagination(
    WHERE: str,
    direction: Literal["ASC", "DESC"] = "DESC",
    max_group_len=10,
    max_group_symbols_count=2500,
) -> list[str]:
    data = db.execute(
        f"""
SELECT event_id,
       LENGTH(text) 
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
