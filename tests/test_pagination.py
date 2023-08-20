from unittest import mock

import pytest

from sql_utils import pagination
from tests.mocks import execute


@mock.patch("todoapi.types.DataBase.execute", execute)
@pytest.mark.parametrize(
    "mock_sql_return, expected_result",
    [
        (
            [
                (1, 42),
                (2, 155),
                (3, 1835),
                (4, 3448),
                (5, 1999),
                (6, 2),
                (7, 1),
                (8, 1),
                (9, 1),
            ],
            ["1,2", "3", "4", "5", "6,7,8", "9"],
        ),
        ([(1, 42)], ["1"]),
        ([(1, 2555)], ["1"]),
        ([], []),
    ],
)
def test_pagination(mock_sql_return, expected_result):
    execute.return_value = mock_sql_return
    result = pagination("1==1", max_group_len=3, max_group_symbols_count=2000)
    assert result == expected_result
