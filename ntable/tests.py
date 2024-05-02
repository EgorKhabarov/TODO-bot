from typing import Callable

from ntable.ntable import *


def test_decrease_numbers():
    assert decrease_numbers([2, 2, 3], 10) == [3, 3, 4]
    assert decrease_numbers([2, 2, 3], 11) == [3, 4, 4]
    assert decrease_numbers([20, 2, 3], 10) == [3, 3, 4]
    assert decrease_numbers([20, 2, 3], 100) == [44, 27, 27]


def test_transform_align():
    assert transform_align(2, "*") == ("*", "*")
    assert transform_align(2, "<>") == ("<>", "<>")
    assert transform_align(3, "<") == ("<", "<", "<")
    assert transform_align(2, ("*",)) == ("*", "*")
    assert transform_align(2, ("<>",)) == ("<>", "*")
    assert transform_align(3, ("<",)) == ("<", "*", "*")
    assert transform_align(3, ("<", "<", "<")) == ("<", "<", "<")


def test_line_spliter():
    assert line_spliter("", 1) == ([" "], [" "])
    assert line_spliter("1", 1) == (["1"], [" "])
    assert line_spliter("123\n456", 1) == (
        ["1", "2", "3", "4", "5", "6"],
        ["↩", "↩", " ", "↩", "↩", " "],
    )
    assert line_spliter("123\n\n456", 1) == (
        ["1", "2", "3", " ", "4", "5", "6"],
        ["↩", "↩", " ", " ", "↩", "↩", " "],
    )
    assert line_spliter("123\n456", 2) == (["12", "3", "45", "6"], ["↩", " ", "↩", " "])
    assert line_spliter("123\n456", 3) == (["123", "456"], [" ", " "])
    assert line_spliter("123\n\n456", 3) == (["123", " ", "456"], [" ", " ", " "])


def test_fill_line():
    assert (
        fill_line(
            [["1", "2", "3", "4", "5", "6"]],
            [["↩", "↩", " ", "↩", "↩", " "]],
            [1],
            ("<",),
        )
        == """| 1↩|
| 2↩|
| 3 |
| 4↩|
| 5↩|
| 6 |"""
    )
    assert (
        fill_line(
            [["1", "2", "3", " ", "4", "5", "6"]],
            [["↩", "↩", " ", " ", "↩", "↩", " "]],
            [1],
            ("<",),
        )
        == """| 1↩|
| 2↩|
| 3 |
|   |
| 4↩|
| 5↩|
| 6 |"""
    )
    assert (
        fill_line([["12", "3", "45", "6"]], [["↩", " ", "↩", " "]], [2], ("<",))
        == """| 12↩|
| 3  |
| 45↩|
| 6  |"""
    )
    assert (
        fill_line([["12", "3", "45", "6"]], [["↩", " ", "↩", " "]], [2], (">",))
        == """| 12↩|
|  3 |
| 45↩|
|  6 |"""
    )
    assert (
        fill_line([["123", "456"]], [[" ", " "]], [3], ("<",))
        == """| 123 |
| 456 |"""
    )
    assert (
        fill_line([["123"], ["456"]], [[" "], [" "]], [3, 3], ("<", "<"))
        == """| 123 | 456 |"""
    )


def test_write_table_to_str():
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            file = StringIO()
            func(file, *args, **kwargs)
            return file.read()

        return wrapper

    string_table = decorator(write_table_to_file)
    table_1 = [(1, 2, 3), ("123", "456\n567", "")]
    assert (
        string_table(table_1)
        == """+-----+-----+---+
|   1 |   2 | 3 |
+-----+-----+---+
| 123 | 456 |   |
|     | 567 |   |
+-----+-----+---+"""
    )
    table_2 = [(1, 2, 3), ("12345", "456\n\n567", ""), ("q", "NULL", "NULL")]
    assert (
        string_table(table_2)
        == """+-------+------+------+
|     1 |    2 |    3 |
+-------+------+------+
| 12345 | 456  |      |
|       |      |      |
|       | 567  |      |
+-------+------+------+
| q     | NULL | NULL |
+-------+------+------+"""
    )
    assert (
        string_table(table_2, align="<", name="Table Name")
        == """+---------------------+
|     Table Name      |
+-------+------+------+
| 1     | 2    | 3    |
+-------+------+------+
| 12345 | 456  |      |
|       |      |      |
|       | 567  |      |
+-------+------+------+
| q     | NULL | NULL |
+-------+------+------+"""
    )
    assert (
        string_table(table_2, align=">", name="Table Name")
        == """+---------------------+
|     Table Name      |
+-------+------+------+
|     1 |    2 |    3 |
+-------+------+------+
| 12345 |  456 |      |
|       |      |      |
|       |  567 |      |
+-------+------+------+
|     q | NULL | NULL |
+-------+------+------+"""
    )
    table_3 = [("coll 1", "coll 2")]
    assert (
        string_table(table_3, name="Table\nName", name_align="<")
        == """+-----------------+
| Table           |
| Name            |
+--------+--------+
| coll 1 | coll 2 |
+--------+--------+"""
    )
    assert (
        string_table(table_3, name="Table\nName", name_align="^")
        == """+-----------------+
|      Table      |
|      Name       |
+--------+--------+
| coll 1 | coll 2 |
+--------+--------+"""
    )
    assert (
        string_table(table_3, name="Table\nName", name_align=">")
        == """+-----------------+
|           Table |
|            Name |
+--------+--------+
| coll 1 | coll 2 |
+--------+--------+"""
    )
    assert (
        string_table(table_3, name="Table\nName", name_align="<<")
        == """+-----------------+
| Table           |
| Name            |
+--------+--------+
| coll 1 | coll 2 |
+--------+--------+"""
    )
    assert (
        string_table(table_3, name="Table\nName", name_align=">>")
        == """+-----------------+
|           Table |
|            Name |
+--------+--------+
| coll 1 | coll 2 |
+--------+--------+"""
    )
    assert (
        string_table(table_3, name="Table\nName", name_align="<>")
        == """+-----------------+
| Table           |
|            Name |
+--------+--------+
| coll 1 | coll 2 |
+--------+--------+"""
    )
    assert (
        string_table(table_3, name="Table\nName", name_align="><")
        == """+-----------------+
|           Table |
| Name            |
+--------+--------+
| coll 1 | coll 2 |
+--------+--------+"""
    )
    table_4 = [("",)]
    assert (
        string_table(table_4)
        == """+---+
|   |
+---+"""
    )
    table_5 = [("\n1",)]
    assert (
        string_table(table_5)
        == """+---+
|   |
| 1 |
+---+"""
    )
    table_6 = [("123",)]
    assert (
        string_table(table_6, max_width=(1,))
        == """+---+
| 1↩|
| 2↩|
| 3 |
+---+"""
    )
    table_7 = [("123",)]
    assert (
        string_table(table_7, max_width=(2,))
        == """+----+
| 12↩|
| 3  |
+----+"""
    )
    table_7 = [("123",)]
    assert (
        string_table(table_7, max_width=(1,), max_height=2)
        == """+---+
| 1↩|
| 2…|
+---+"""
    )
    table_8 = [("1",), ("q",), ("👍",)]
    assert (
        string_table(table_8)
        == """+----+
|  1 |
+----+
| q  |
+----+
| 👍 |
+----+"""
    )
    table_9 = [("123456\n\n789000",)]
    assert (
        string_table(table_9, max_width=(3,), max_height=4)
        == """+-----+
| 123↩|
| 456 |
|     |
| 789…|
+-----+"""
    )
    table_10 = [("1234567\n\n891\n234",)]
    assert (
        string_table(table_10, max_width=(2,), max_height=7)
        == """+----+
| 12↩|
| 34↩|
| 56↩|
| 7  |
|    |
| 89↩|
| 1 …|
+----+"""
    )
    table_11 = [("1234567\n\n891\n234", "qwe" * 20)]
    assert (
        string_table(table_11, max_width=(2,), max_height=7)
        == """+----+----+
| 12↩| qw↩|
| 34↩| eq↩|
| 56↩| we↩|
| 7  | qw↩|
|    | eq↩|
| 89↩| we↩|
| 1 …| qw…|
+----+----+"""
    )


def test_read_table_from_str():
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            file = StringIO(args[0])
            return list(func(file, *args[1:], **kwargs))

        return wrapper

    read_table = decorator(read_table_from_file)

    table_1 = """+-------+------+------+
|     1 |    2 |    3 |
+-------+------+------+
| 12345 |  456 |      |
|       |      |      |
|       |  567 |      |
+-------+------+------+
|     q | NULL | NULL |
|     q | NULL | NULL |
|     q | NULL | NULL |
+-------+------+------+"""
    assert read_table(table_1) == [
        ("1", "2", "3"),
        ("12345", "456\n\n567", ""),
        ("q\nq\nq", "NULL\nNULL\nNULL", "NULL\nNULL\nNULL"),
    ]
    table_2 = """+---------------------+
|        Table        |
|        Name         |
+-------+------+------+
|     1 |    2 |    3 |
+-------+------+------+
| 12345 |  456 |      |
|       |      |      |
|       |  567 |      |
+-------+------+------+
|     q | NULL | NULL |
|     q | NULL | NULL |
|     q | NULL | NULL |
+-------+------+------+"""
    assert read_table(table_2, name=True) == [
        ("Table\nName",),
        ("1", "2", "3"),
        ("12345", "456\n\n567", ""),
        ("q\nq\nq", "NULL\nNULL\nNULL", "NULL\nNULL\nNULL"),
    ]
    table_3 = """+-----+---+
| 123↩| 1 |
| 456 |   |
|     |   |
| 789…|   |
+-----+---+"""
    assert read_table(table_3) == [("123456\n\n789…", "1")]
    table_4 = """+----+
| 12↩|
| 34↩|
| 56↩|
| 7  |
|    |
| 89↩|
| 1 …|
+----+"""
    assert read_table(table_4) == [("1234567\n\n891…",)]
