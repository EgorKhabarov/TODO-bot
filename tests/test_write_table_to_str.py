from io import StringIO
from unittest.mock import patch

import pytest

from tests.mocks import execute
from tgbot.utils import write_table_to_str


parameters = pytest.mark.parametrize(
    "mock_sql_return, mock_sql_query, expected_result",
    [
        (
            [("column_1", "column_2"), ("value_1", "value_2")],
            "SELECT column_1, column_2 FROM table;",
            """
+----------+----------+
| column_1 | column_2 |
+----------+----------+
| value_1  | value_2  |
+----------+----------+
""".strip(),
        ),
        (
            [
                ("column_1", "column_2\n."),
                ("value_1\nvalue_3 12345", "value_2\n\nvalue_4"),
            ],
            "SELECT column_1, column_2 FROM table;",
            """
+---------------+----------+
| column_1      | column_2 |
|               | .        |
+---------------+----------+
| value_1       | value_2  |
| value_3 12345 |          |
|               | value_4  |
+---------------+----------+
""".strip(),
        ),
        (
            [
                ("column_1", "column_2"),
                ("value_1", "value_2"),
                ("value_3\n\n.", "value_4"),
                ("value_5", "value_6        ."),
                ("value_7", "value_8"),
            ],
            "SELECT column_1, column_2 FROM table;",
            """
+----------+------------------+
| column_1 | column_2         |
+----------+------------------+
| value_1  | value_2          |
+----------+------------------+
| value_3  | value_4          |
|          |                  |
| .        |                  |
+----------+------------------+
| value_5  | value_6        . |
+----------+------------------+
| value_7  | value_8          |
+----------+------------------+
""".strip(),
        ),
    ],
)


@patch("todoapi.types.DataBase.execute", execute)
@parameters
def test_is_exceeded_limit(mock_sql_return, mock_sql_query, expected_result):
    file = StringIO()
    write_table_to_str(file, table=mock_sql_return)
    file.seek(0)

    assert file.read() == expected_result

    execute.return_value = mock_sql_return

    file = StringIO()
    write_table_to_str(file, query=mock_sql_query)
    file.seek(0)

    assert file.read() == expected_result
