import os
import csv
from datetime import datetime
from io import StringIO
from pprint import pprint, pformat
from typing import TypeAlias, Literal, Any, Callable

import unicodedata
from IPython import embed

from todoapi.types import db, Account  # noqa
from tgbot.types import TelegramAccount  # noqa


AlignType: TypeAlias = Literal[
    "<", ">", "^", "*", "<<", "<^", "<>", "^<", "^^", "^>", "><", ">^", ">>"
]


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def console_width(text: str):
    """Определяет количество позиций, которое займет строка в консоли."""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ("W", "F"):
            width += 2  # Широкие символы
        else:
            width += 1  # Узкие символы
    return width


def decrease_numbers(row_lengths: list[int], max_width: int = 120, min_value: int = 10):
    # Рассчитываем среднее значение
    mean_value = sum(row_lengths) / len(row_lengths)
    new_numbers = []

    for num in row_lengths:
        # Определяем насколько это число больше или меньше среднего
        diff_from_mean = num - mean_value

        if diff_from_mean > 0:
            reduction_percent = 0.4
        else:
            reduction_percent = 0.01

        reduced_num = num - (mean_value * reduction_percent)

        new_num = max(int(reduced_num), min_value)
        new_numbers.append(new_num)

    # Если общая сумма новых чисел превышает max_width, уменьшаем наибольшее число на 1
    while sum(new_numbers) > max_width:
        new_numbers[new_numbers.index(max(new_numbers))] -= 1

    # Рассчитываем коэффициент для пропорционального увеличения, если сумма меньше max_sum
    if sum(new_numbers) < max_width:
        new_numbers = [int(num * (max_width / sum(new_numbers))) for num in new_numbers]

    # Если общая сумма новых чисел меньше max_width, увеличиваем наименьшее число на 1
    while sum(new_numbers) < max_width and min(new_numbers) < min_value:
        new_numbers[new_numbers.index(min(new_numbers))] += 1

    return new_numbers


def transform_align(
    column_count: int, align: tuple[AlignType | str] | AlignType | str = "*"
):
    # Преобразуем align в подходящий вид
    if isinstance(align, str):
        align = (align, *(align,) * (column_count - 1))
    else:
        align = (*align, *("*",) * (column_count - len(align)))

    return align[:column_count]


def line_spliter(
    text: str,
    width: int = 126,
    height: int = 20,
    console_mode: bool = False,
    line_break_symbol: str = "↩",
):
    if console_mode:
        sub_lines = []
        line_arr = []
        line_length_arr = []

        if console_width(text or " ") > width:
            width -= 2

        for char in text or " ":
            if char == "\n" or (sum(line_length_arr) > width):
                sub_lines.append("".join(line_arr))
                line_arr.clear()
                line_length_arr.clear()
            line_arr.append(char)
            line_length_arr.append(console_width(char))

        sub_lines.append(f"{''.join(line_arr):<{width}}")
        split_text = f"{line_break_symbol}\n".join(sub_lines)
    else:
        split_text = f"{line_break_symbol}\n".join(chunks(text or " ", width))

    lines = split_text.replace(f"\n{line_break_symbol}\n", "\n\n").splitlines()
    lines[-1] = lines[-1].removesuffix(line_break_symbol)
    if len(lines) > height:
        lines = lines[:height]
        lines[-1] = lines[-1].removesuffix(line_break_symbol) + chr(8230)  # " …"

    return [line.strip() for line in lines]


def fill_line(
    rows: list[list[str]],
    widths: list[int],
    align: tuple[AlignType | str],
    console_mode: bool,
) -> str:
    # noinspection PyTypeChecker
    align_left, align_right = map(
        list, zip(*(a * 2 if len(a) == 1 else a for a in align))
    )
    len_func = console_width if console_mode else len

    # Делаем каждый элемент одинаковой ширины по максимальному элементу
    for n, r in enumerate(zip(*rows)):
        if align_left[n] == "^":
            max_len = len_func(max(r))
            for column in rows:
                column[n] = f"{column[n]:{align_right[n]}{max_len}}"
                align_right[n] = align_left[n]

        if align_left[n] == "*":
            try:
                int("\n".join(r))
                align_left[n] = ">"
                align_right[n] = ">"
            except ValueError:
                align_left[n] = "<"
                align_right[n] = "<"

    lines = []

    for rn, row in enumerate(rows):
        if rn == 0:
            align = align_left
        else:
            align = align_right

        def get_width(index: int):
            return widths[index] - (len_func(row[index]) - len(row[index]))

        template = "|" + "".join(
            f" {{:{align[n]}{get_width(n)}}} |" for n in range(len(row))
        )
        lines.append(template.format(*row))

    return "\n".join(lines)


def write_table_to_str(
    file: StringIO,
    table: list[tuple[str, ...]],
    align: tuple[AlignType | str] | AlignType | str = "*",
    name: str = None,
    name_align: Literal["<", ">", "^"] | str = None,
    max_width: int = None,
    max_height: int = None,
    console_mode: bool = False,
    line_break_symbol: str = "↩",
) -> None:
    max_height = max_height or 20
    len_func = console_width if console_mode else len
    column_count = max(map(len, table))
    align = transform_align(column_count, align)
    row_lengths = [
        max(map(lambda c: len_func(str(c)), column)) for column in zip(*table)
    ]

    # Вычисляем ширину каждой колонки
    if max_width:
        sum_column_width = max_width - (3 * column_count) - 1
        max_widths = decrease_numbers(row_lengths, sum_column_width)
    else:
        max_widths = row_lengths

    # Обрезаем длинные строки
    table = [
        [
            line_spliter(
                column, max_widths[n], max_height, console_mode, line_break_symbol
            )
            for n, column in enumerate(
                (*map(str, row), *("",) * (column_count - len(row)))
            )
        ]
        for row in table
    ]

    # Разделитель строк
    sep = "+" + "".join(("-" * (i + 2)) + "+" for i in max_widths) + "\n"

    if name:
        # noinspection PyTypeChecker
        name_align = transform_align(1, name_align or "^")
        file.write("+" + sep.replace("+", "-")[1:-2] + "+\n")

        if not max_width:
            max_width = sum(row_lengths) + (3 * column_count) + 1

        name = line_spliter(
            name, max_width - 4, max_height, console_mode, line_break_symbol
        )
        file.write(
            fill_line(
                [[n] for n in name],
                [max_width - 4],
                name_align,
                console_mode,
            )
            + "\n"
        )

    for n, row in enumerate(table):
        file.write(sep)

        max_row_height = max(map(len, row))
        for column in row:
            column.extend(("",) * (max_row_height - len(column)))

        # noinspection PyTypeChecker
        file.write(
            fill_line(list(map(list, zip(*row))), max_widths, align, console_mode)
            + "\n"
        )

    file.write(sep.rstrip("\n"))
    file.seek(0)


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
    console_mode: bool = True,
) -> None | str | list[tuple[int | str | bytes | Any, ...], ...]:
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

        _file = StringIO()
        write_table_to_str(
            _file,
            result or [["ok"]],
            align,
            name,
            name_align,
            max_width,
            max_height,
            console_mode,
        )
        if return_data:
            return _file.read()
        [print(line, end="") for line in _file]
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
def export(query: str = "SELECT * FROM events;", params: dict | tuple = ())
Account(user_id: int, group_id: str = None)
TelegramAccount(chat_id: int, group_chat_id: int = None)
TERMINAL() -> tuple[int, int]
"""

embed(colors="Linux")
