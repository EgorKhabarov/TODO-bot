#!/usr/bin/env python3
import os
import csv
import subprocess
from pprint import pprint, pformat
from datetime import datetime, timezone
from typing import Literal, Any

from IPython import embed
from table2string import Table, Themes, Theme

from config import WSGI_PATH, __version__
from notes_api.types import db, Account as notes_api_Account
from tgbot.types import TelegramAccount  # noqa


def execute(
    query: str,
    params: dict | tuple = (),
    commit: bool = False,
    mode: Literal["table", "raw", "pprint"] = "table",
    max_width: int | type(max) | type(max) | None = max,
    max_height: int | type(max) | type(max) | None = max,
    maximize_height: bool = False,
    align: tuple[str, ...] | str = "*",
    name: str = None,
    name_align: str = "^",
    return_data: bool = False,
    theme: Theme = Themes.ascii_thin,
) -> None | str | list[tuple[int | str | bytes | Any, ...], ...]:
    """

    :param query: SQL query
    :param params: tuple[str | int] or dict[str, str | int]
    :param commit: bool
    # :param functions: (func_name, func) or None
    :param mode: "table" - ASCII table "raw" "pprint"
    :param max_width:
    :param max_height:
    :param maximize_height:
    :param align:
    :param name:
    :param name_align:
    :param return_data:
    :param theme:
    :return:
    """

    with db.connect():
        result = db.execute(
            query,
            params,
            commit,
            column_names=True,
        )

    if mode == "table":
        if max_width is max or max_height is max:
            _max_width, _max_height = terminal_size()
            if max_width is max:
                max_width = _max_width

            if max_height is max:
                max_height = _max_height

        if max_width is min:
            max_width = None
        if max_height is min:
            max_height = None

        if result and len(result) > 1:
            table = result[1:]
            column_names = result[0]
        else:
            table = result or [["ok"]]
            column_names = None

        Table(
            table,
            name=name,
            column_names=column_names,
        ).print(
            h_align=align,
            name_h_align=name_align,
            max_width=max_width,
            max_height=max_height,
            maximize_height=maximize_height,
            theme=theme,
            line_break_symbol="\\",
        )
    elif mode == "raw":
        if return_data:
            return result
        print(result)
    else:
        if return_data:
            return pformat(result)
        pprint(result)


def export(query: str = "SELECT * FROM events;", params: dict | tuple = ()) -> str:
    path = f"data/exports/{datetime.now(timezone.utc):%Y-%m-%d_%H-%M-%S}.csv"

    try:
        os.mkdir("data/exports")
    except FileExistsError:
        pass

    with open(path, "w", newline="", encoding="UTF-8") as file:
        table = execute(query, params, mode="raw", return_data=True)
        file_writer = csv.writer(file)
        file_writer.writerows(table)

    return path


def terminal_size() -> tuple[int, int]:
    try:
        _terminal_size = os.get_terminal_size()
    except OSError:
        _terminal_size = os.terminal_size((120, 30))

    return _terminal_size.columns, _terminal_size.lines


def restart_server() -> None:
    if WSGI_PATH:
        subprocess.call(["touch", WSGI_PATH])
    else:
        print(f"{WSGI_PATH=}")


def chat_list(page: int = 1) -> None:
    execute(
        """
SELECT c.date,
       c.id,
       c.type,
       c.title,
       c.username,
       c.first_name,
       c.last_name,
       (
           SELECT group_concat(j.key || ': ' || j.value, char(10))
           FROM json_each(c.json) AS j
       ) AS json
  FROM chats AS c
 LIMIT :limit
OFFSET :offset;
""",
        params={
            "limit": 10,
            "offset": (page - 1) * 10,
        },
    )


def user_list(page: int = 1) -> None:
    execute(
        """
SELECT user_id,
       username,
       email,
       user_status,
       max_event_id - 1 as event_count,
       reg_date,
       chat_id
  FROM users
 LIMIT :limit
OFFSET :offset;
""",
        params={
            "limit": 10,
            "offset": (page - 1) * 10,
        },
    )


def group_list(page: int = 1) -> None:
    execute(
        """
SELECT group_id,
       name,
       owner_id,
       max_event_id - 1 as event_count,
       chat_id
  FROM groups
 LIMIT :limit
OFFSET :offset;
""",
        params={
            "limit": 10,
            "offset": (page - 1) * 10,
        },
    )


def user(*, user_id: int | None = None, chat_id: int | str | None = None) -> None:
    execute(
        """
SELECT user_id,
       username,
       email,
       user_status,
       max_event_id as event_count,
       reg_date,
       chat_id
  FROM users
 WHERE user_id = :user_id
       OR chat_id IS :chat_id;
""",
        params={
            "user_id": user_id,
            "chat_id": chat_id,
        },
    )


def ban(user_id: int, user_status: int = -1) -> None:
    execute(
        """
UPDATE users
   SET user_status = :user_status
 WHERE user_id = :user_id;
""",
        params={
            "user_id": user_id,
            "user_status": user_status,
        },
        commit=True,
    )
    print("\x1b[2A")
    user(user_id=user_id)


class Account(notes_api_Account):
    def __init__(self, user_id: int, group_id: str | None = None):
        with db.connect():
            super().__init__(user_id, group_id)
        self.conn = None

    def __enter__(self):
        self.conn = db.connect()
        self.conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.conn.__exit__(exc_type, exc_val, exc_tb)


HELP = """
exit -> Ctrl+D

execute(
    query: str,
    params: dict | tuple = (),
    commit: bool = False,
    mode: Literal["table", "raw", "pprint"] = "table",
    max_width: int | type(max) | type(max) | None = max,
    max_height: int | type(max) | type(max) | None = max,
    maximize_height: bool = False,
    align: tuple[str, ...] | str = "*",
    name: str = None,
    name_align: str = "^",
    return_data: bool = False,
    theme: Theme = Themes.ascii_thin,
)
export(
    query: str = "SELECT * FROM events;",
    params: dict | tuple = (),
) -> str  # file path
terminal_size() -> tuple[int, int]
restart_server()

chat_list(page: int = 1)
user_list(page: int = 1)
group_list(page: int = 1)
user(*, user_id: int | None = None, chat_id: int | str | None = None)
ban(user_id: int, user_status: int = -1)

with Account(user_id: int) as account:
    ...

db.register_function(name: str, func: (...) -> Any)
Account(user_id: int, group_id: str | None = None)
TelegramAccount(chat_id: int, group_chat_id: int | None = None)
"""


if __name__ == "__main__":
    print(f"notes-assistant {__version__}")
    embed(colors="Linux")
