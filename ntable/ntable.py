import re
import unicodedata
from io import StringIO
from typing import TypeAlias, Literal, Generator, Any

AlignType: TypeAlias = Literal[
    "<", ">", "^", "*", "<<", "<^", "<>", "^<", "^^", "^>", "><", ">^", ">>"
]


def get_text_width_in_console(text: str) -> int:
    """Определяет количество позиций, которое займет строка в консоли."""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ("W", "F"):
            width += 2  # Широкие символы
        else:
            width += 1  # Узкие символы
    return width


def decrease_numbers(
    row_lengths: list[int], max_width: int = 120, min_value: int = 10
) -> list[int]:
    """

    :param row_lengths:
    :param max_width:
    :param min_value:
    :return:
    """
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
    column_count: int, align: tuple[AlignType | str, ...] | AlignType | str = "*"
) -> tuple[AlignType]:
    """

    :param column_count:
    :param align:
    :return:
    """
    # Преобразуем align в подходящий вид
    if isinstance(align, str):
        align = (align, *(align,) * (column_count - 1))
    else:
        align = (*align, *("*",) * (column_count - len(align)))

    return align[:column_count]


def transform_width(width: int | tuple[int, ...] | None, column_count: int, row_lengths: list[int]) -> list[int]:
    if width is not None and isinstance(width, tuple):
        width: tuple[int]
        if len(width) < column_count:
            width: tuple = tuple(
                (*width, *(width[-1],) * (column_count - len(width)))
            )
        width: int = sum(width) + (3 * len(width)) + 1

    if width is not None and width < column_count + (3 * column_count) + 1:
        width: int = (
            sum(1 if rl > 1 else 0 for rl in row_lengths) + (3 * column_count) + 1
        )

    # Вычисляем ширину каждой колонки
    if width:
        sum_column_width = width - (3 * column_count) - 1
        max_widths = decrease_numbers(row_lengths, sum_column_width)
    else:
        max_widths = row_lengths

    return max_widths


def line_spliter(
    text: str,
    width: int = 126,
    height: int = 20,
    line_break_symbol: str = "↩",
) -> tuple[list[str], list[str]]:
    """

    :param text:
    :param width:
    :param height:
    :param line_break_symbol:
    :return:
    """
    lines = text.split("\n")
    result_lines = []
    result_breaks = []
    for line in lines:
        if get_text_width_in_console(line) == 0:
            result_lines.append(" ")
            result_breaks.append(" ")
        else:
            while line:
                if get_text_width_in_console(line) <= width:
                    result_lines.append(line)
                    result_breaks.append(" ")
                    line = ""
                else:
                    w = 0
                    while get_text_width_in_console(line[:w]) <= width - 1:
                        w += 1
                    result_lines.append(line[:w])
                    result_breaks.append(line_break_symbol)
                    line = line[w:]

    if len(result_lines) > height:
        result_lines = result_lines[:height]
        result_breaks = result_breaks[:height]
        result_breaks[-1] = chr(8230)  # "…"

    return result_lines, result_breaks


def fill_line(
    rows: list[list[str]],
    symbols: list[list[str]],
    widths: list[int],
    align: tuple[AlignType | str, ...],
) -> str:
    """

    :param rows:
    :param symbols:
    :param widths:
    :param align:
    :return:
    """
    # noinspection PyTypeChecker
    align_left, align_right = map(
        list, zip(*(a * 2 if len(a) == 1 else a for a in align))
    )

    # Делаем каждый элемент одинаковой ширины по максимальному элементу
    for n, row in enumerate(rows):
        if align_left[n] == "*" or align_right[n] == "*":
            try:
                float("\n".join(row))
                align_left[n] = ">"
                align_right[n] = ">"
            except ValueError:
                align_left[n] = "<"
                align_right[n] = "<"

    lines = []
    symbol = list(zip(*symbols))

    for rn, row in enumerate(zip(*rows)):
        if rn == 0:
            align = align_left
        else:
            align = align_right

        def get_width(index: int):
            return widths[index] - (
                get_text_width_in_console(row[index]) - len(row[index])
            )

        template = "|" + "".join(
            f" {{:{align[cn]}{get_width(cn)}}}{symbol[rn][cn]}|"
            for cn in range(len(row))
        )
        lines.append(template.format(*row))

    return "\n".join(lines)


def write_table_to_file(
    file: StringIO,
    table: list[tuple[str, ...]],
    align: tuple[AlignType | str] | AlignType | str = "*",
    name: str = None,
    name_align: Literal["<", ">", "^"] | str = None,
    max_width: int | tuple[int, ...] = None,
    max_height: int = None,
    line_break_symbol: str = "↩",
) -> None:
    """

    :param file:
    :param table:
    :param align:
    :param name:
    :param name_align:
    :param max_width:
    :param max_height:
    :param line_break_symbol:
    :return:
    """
    row_lengths: list[int] = []

    for column in zip(*table):
        cell_widths = []
        for cell in column:
            if cell:
                lines = str(cell).splitlines() or [""]
                cell_width = get_text_width_in_console(
                    max(lines, key=get_text_width_in_console)
                )
                cell_widths.append(cell_width)
            else:
                cell_widths.append(1)

        row_lengths.append(max(cell_widths))

    column_count = max(map(len, table))
    align = transform_align(column_count, align)
    max_widths = transform_width(max_width, column_count, row_lengths)
    max_height = max_height or 20

    # Обрезаем длинные строки
    table = [
        [
            line_spliter(column, max_widths[n], max_height, line_break_symbol)
            for n, column in enumerate(map(str, row))
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
            max_width: int = sum(row_lengths) + (3 * column_count) + 1

        rows, symbols = zip(
            line_spliter(name, max_width - 4, max_height, line_break_symbol)
        )
        file.write(
            fill_line(
                rows,
                symbols,
                [max_width - 4],
                name_align,
            )
            + "\n"
        )

    for n, row in enumerate(table):
        file.write(sep)
        max_row_height = max(map(len, list(zip(*row))[0]))

        for column in row:
            extend_data = (" ",) * (max_row_height - len(column[0]))
            column[0].extend(extend_data)
            column[1].extend(extend_data)

        rows, symbols = zip(*row)
        line = fill_line(rows, symbols, max_widths, align)
        file.write(line + "\n")

    file.write(sep.rstrip("\n"))
    file.seek(0)


def read_table_from_file(
    file: StringIO,
    name: bool = False,
    line_break_symbol: str = "↩",
) -> Generator[list[str], Any, None]:
    """

    :param file:
    :param name:
    :param line_break_symbol:
    :return:
    """
    regex_column_sep = re.compile(r"\| ")
    regex_column_strip = re.compile(r"\| (.+[ ↩…])|")

    def next_func() -> bool:
        res = bool(file.read(1))
        file.seek(file.tell() - 1)
        return res

    def prepare_lines(rls: list[str]):
        lines = [[] for _ in range(column_count)]
        rls = [
            regex_column_sep.split(regex_column_strip.match(row).group(1))
            for row in rls
        ]

        for nr, row in enumerate(rls):
            for nc, column in enumerate(row):
                if column.endswith("…"):
                    column = f"\n{column.removesuffix('…').strip()}…"
                else:
                    column = f"\n{column.strip()}"
                lines[nc].append(column)

        return tuple(
            "".join(line).strip().replace(f"{line_break_symbol}\n", "")
            for line in lines
        )

    # Первый разделитель
    column_count = file.readline().count("+") - 1

    if name and column_count == 1:
        raw_name_lines = [file.readline().removesuffix("\n")]

        while raw_name_lines[-1].endswith("|"):
            raw_name_lines.append(file.readline().removesuffix("\n"))

        raw_lines = raw_name_lines[:-1]
        yield prepare_lines(raw_lines)

    # Пока мы можем прочитать ещё одну линию
    while next_func():
        # Читаем одну линию
        raw_lines = [file.readline().removesuffix("\n")]

        while raw_lines[-1].endswith("|"):
            raw_lines.append(file.readline().removesuffix("\n"))

        column_count = raw_lines[-1].count("+") - 1
        raw_lines = raw_lines[:-1]
        yield prepare_lines(raw_lines)
