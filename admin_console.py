import os
from io import StringIO
from pprint import pprint
from typing import TypeAlias, Literal
from textwrap import wrap as textwrap

from IPython import embed

from todoapi.types import db, Account  # noqa
from tgbot.types import TelegramAccount  # noqa


AlignType: TypeAlias = Literal[
    "<", ">", "^", "*", "<<", "<^", "<>", "^<", "^^", "^>", "><", ">^", ">>"
]


def decrease_numbers(numbers, max_width=120, min_value=10):
    # Рассчитываем среднее значение
    mean_value = sum(numbers) / len(numbers)
    new_numbers = []

    for num in numbers:
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


def fill_line(row: zip, widths: list[int], align: tuple[AlignType]) -> str:
    # noinspection PyTypeChecker
    align_left, align_right = map(
        list, zip(*(a * 2 if len(a) == 1 else a for a in align))
    )
    row = [list(r) for r in row]

    # Делаем каждый элемент одинаковой ширины по максимальному элементу
    for n, r in enumerate(zip(*row)):
        if "^" == align_left[n]:
            max_len = len(max(r))
            for column in row:
                column[n] = f"{column[n]:{align_right[n]}{max_len}}"
                align_right[n] = align_left[n]

    if "*" in align_left:
        for n, r in enumerate(zip(*row)):
            if align_left[n] == "*":
                try:
                    int("\n".join(r))
                    align_left[n] = ">"
                    align_right[n] = ">"
                except ValueError:
                    align_left[n] = "<"
                    align_right[n] = "<"

    template = "|" + "".join(f" {{:{a}{w}}} |" for a, w in zip(align_left, widths))
    line = template.format(*row[0])

    for r in row[1:]:
        template = "|" + "".join(f" {{:{a}{w}}} |" for a, w in zip(align_right, widths))
        line += "\n" + template.format(*r)

    return line


def write_table_to_str(
    file: StringIO,
    table: list[tuple[str]],
    align: tuple[AlignType] | AlignType = "*",
    name: str = None,
    name_align: Literal["<", ">", "^"] = None,
    max_width: int = None,
    max_height: int = None,
) -> None:
    row_len = max(len(row) for row in table)

    # Преобразуем align в подходящий вид
    if isinstance(align, str):
        align = (align, *(align,) * (row_len - 1))
    else:
        align = (*align, *("*",) * (row_len - len(align)))

    align = align[:row_len]

    if max_width:
        max_width = max_width - (3 * len(max(table, key=len))) - 1
        max_widths = decrease_numbers(
            [len(max((str(c) for c in column), key=len)) for column in zip(*table)],
            max_width,
        )
    else:
        max_widths = None

    # Обрезаем длинные строки до 126 символов (уменьшается размер файла)
    table = [
        [
            "\n".join(
                " \\\n".join(
                    textwrap(
                        line,
                        width=(max_widths[n] if max_widths[n] else 1)
                        if max_width
                        else 126,
                        replace_whitespace=False,
                        drop_whitespace=True,
                    )
                    or " "
                )
                for line in str(column).splitlines()
            )
            for n, column in enumerate((*row, *("",) * (row_len - len(row))))
        ]
        for row in table
    ]

    # Матрица максимальных длин и высот каждого столбца и строки
    w = [
        [max(len(line) for line in str(column or " ").splitlines()) for column in row]
        for row in table
    ]

    # Вычисляем максимальную ширину и высоту каждого столбца и строки
    widths = [max(column) for column in zip(*w)]
    sep = (
        "+" + "".join(("-" * (i + 2)) + "+" for i in widths) + "\n"
    )  # Разделитель строк

    if name:
        name = name.replace("\n", " ")
        file.write("+" + sep.replace("+", "-")[1:-2] + "+\n")
        file.write(f"| {name:{name_align or '^'}{len(sep) - len(name)+1}} |\n")

    for n, row in enumerate(table):
        file.write(sep)

        def func(lines: list[str]):
            lines[-1] = lines[-1].removesuffix("\\") + chr(8230)  # " …"
            return lines

        # Заполняем колонки
        row = [
            func(column.splitlines()[: max_height or 20])
            if column.count("\n") >= (max_height or 20)
            else column.splitlines()
            for column in row
        ]
        max_row_count = len(max(row, key=len))

        for column in row:
            column.extend(("",) * (max_row_count - len(column)))

        file.write(fill_line(zip(*row), widths, align) + "\n")

    file.write(sep.rstrip("\n"))
    file.seek(0)


def execute(
    query: str,
    params: dict | tuple = (),
    commit: bool = False,
    mode: Literal["table", "raw", "pprint"] = "table",
    max_width: int = None,
    max_height: int = None,
    align: tuple[AlignType] | AlignType = "*",
    name: str = None,
    name_align: Literal["<", ">", "^"] = None,
):
    result = db.execute(query, params, commit, column_names=True)

    if mode == "table":
        if max_width is None or max_height is None:
            _max_width, _max_height = TERMINAL()
            if max_width is None:
                max_width = _max_width
            else:
                max_height = _max_height

        _file = StringIO()
        write_table_to_str(
            _file, result or [[" "]], align, name, name_align, max_width, max_height
        )
        [print(line, end="") for line in _file]
    elif mode == "raw":
        print(result)
    else:
        pprint(result)


def TERMINAL():
    return os.get_terminal_size()


HELP = """
exit -> Ctrl+D

execute(
    query: str,
    params: dict | tuple = (),
    commit: bool = False,
    mode: Literal["table", "raw", "pprint"] = "table",
    max_width: int = None,
    max_height: int = None,
    align: tuple[AlignType] | AlignType = "*",
    name: str = None,
    name_align: Literal["<", ">", "^"] = None,
)
Account(user_id: int, group_id: str = None)
TelegramAccount(chat_id: int, group_chat_id: int = None)
TERMINAL() -> tuple[int, int]
""".strip()

embed(header=HELP)
