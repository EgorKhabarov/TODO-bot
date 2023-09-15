from unittest import mock

import pytest

from todoapi.api import User
from tests.mocks import settings_mock, execute


@mock.patch("todoapi.types.DataBase.execute", execute)
@pytest.mark.parametrize(
    "mock_sql_return, expected_result",
    [
        ([(1, 1, 1, 1, 1, 1, 1, 1)], False),  # Превышения лимита не должно быть
        (
            [(20, 4000, 20, 4000, 20, 4000, 20, 4000)],
            True,
        ),  # Тестируем превышение лимита
        ([(19, 3999, 19, 3999, 19, 3999, 20, 4000)], True),  # Превышение лимита
    ],
)
def test_is_exceeded_limit(mock_sql_return, expected_result):
    user = User(1, settings_mock)
    execute.return_value = mock_sql_return

    # Пытаемся добавить одно событие
    result = user.check_limit("01.01.2000", event_count=1)[1] is True
    assert result is expected_result

    # Пытаемся добавить один символ
    result = user.check_limit("01.01.2000", symbol_count=1)[1] is True
    assert result is expected_result
