import os
import csv
import subprocess
from datetime import datetime
from io import StringIO
from pprint import pprint, pformat
from typing import Literal, Any, Callable

from IPython import embed

from config import WSGI_PATH
from ntable import write_table_to_file, AlignType
from todoapi.types import db, Account  # noqa
from tgbot.types import TelegramAccount  # noqa


def execute(
    query: str,
    params: dict | tuple = (),
    commit: bool = False,
    func: tuple[str, Callable] | None = None,
    mode: Literal["table", "raw", "pprint"] = "table",
    max_width: int | type(max) | type(max) | None = max,
    max_height: int | type(max) | type(max) | None = max,
    align: tuple[AlignType] | AlignType = "*",
    name: str = None,
    name_align: Literal["<", ">", "^"] = None,
    return_data: bool = False,
) -> None | str | list[tuple[int | str | bytes | Any, ...], ...]:
    """

    :param query: SQL query
    :param params: tuple[str | int] or dict[str, str | int]
    :param commit: bool
    :param func: (func_name, func) or None
    :param mode: "table" - ASCII table "raw" "pprint"
    :param max_width:
    :param max_height:
    :param align:
    :param name:
    :param name_align:
    :param return_data:
    :return:
    """
    if func:
        func_name, func_func = func
        # noinspection PyUnresolvedReferences
        func = (func_name, func_func.__code__.co_argcount, func_func)

    result = db.execute(query, params, commit, column_names=True, func=func)

    if mode == "table":
        if max_width is max or max_height is max:
            _max_width, _max_height = TERMINAL()
            if max_width is max:
                max_width = _max_width

            if max_height is max:
                max_height = _max_height

        if max_width is min:
            max_width = None
        if max_height is min:
            max_height = None

        file = StringIO()
        write_table_to_file(
            file=file,
            table=result or [["ok"]],
            align=align,
            name=name,
            name_align=name_align,
            max_width=max_width,
            max_height=max_height,
        )
        if return_data:
            return file.read()
        [print(line, end="") for line in file]
        print()
    elif mode == "raw":
        if return_data:
            return result
        print(result)
    else:
        if return_data:
            return pformat(result)
        pprint(result)


def export(query: str = "SELECT * FROM events;", params: dict | tuple = ()) -> str:
    path = f"data/exports/{datetime.utcnow():%Y-%m-%d_%H-%M-%S}.csv"

    try:
        os.mkdir("data/exports")
    except FileExistsError:
        pass

    with open(path, "w", newline="", encoding="UTF-8") as file:
        table = execute(query, params, mode="raw", return_data=True)
        file_writer = csv.writer(file)
        file_writer.writerows(table)

    return path


def TERMINAL():
    return os.get_terminal_size()


def RESTART_SERVER():
    if WSGI_PATH:
        subprocess.call(["touch", WSGI_PATH])
    else:
        print(f"{WSGI_PATH=}")


HELP = """
exit -> Ctrl+D

execute(
    query: str,
    params: dict | tuple = (),
    commit: bool = False,
    func: tuple[str, Callable] | None = None,
    mode: Literal["table", "raw", "pprint"] = "table",
    max_width: int | min | max | None = max,
    max_height: int | min | max | None = max,
    align: tuple[AlignType] | AlignType = "*",
    name: str = None,
    name_align: Literal["<", ">", "^"] = None,
    return_data: bool = False,
)
export(
    query: str = "SELECT * FROM events;",
    params: dict | tuple = (),
)
Account(user_id: int, group_id: str = None)
TelegramAccount(chat_id: int, group_chat_id: int = None)
TERMINAL() -> tuple[int, int]
"""

embed(colors="Linux")
