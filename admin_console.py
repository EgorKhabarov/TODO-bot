import os
import csv
import subprocess
from pprint import pprint, pformat
from datetime import datetime, timezone
from typing import Literal, Any, Callable

from IPython import embed
from table2string import Table, Themes, Theme

from config import WSGI_PATH
from todoapi.types import db, Account  # noqa
from tgbot.types import TelegramAccount  # noqa


def execute(
    query: str,
    params: dict | tuple = (),
    commit: bool = False,
    functions: tuple[tuple[str, Callable]] | None = None,
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
    :param functions: (func_name, func) or None
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
    if functions:
        functions = tuple(
            # noinspection PyUnresolvedReferences
            (lambda fn, ff: (fn, ff.__code__.co_argcount, ff))(*func)
            for func in functions
        )

    result = db.execute(query, params, commit, column_names=True, functions=functions)

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
terminal_size() -> tuple[int, int]
restart_server()
"""


if __name__ == "__main__":
    embed(colors="Linux")
