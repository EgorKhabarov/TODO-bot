import subprocess

# TODO Убрать если https://github.com/eternnoir/pyTelegramBotAPI/pull/2083 будет добавлен
from unittest import mock
from telegram_utils.patch import PathedMessage


import sys

sys.path.append("../")


def run_pytest():
    try:
        # Запуск pytest с использованием subprocess
        result = subprocess.run(["pytest"], capture_output=True, text=True)

        # Вывод результатов тестирования
        print(result.stdout)

        # Проверка кода возврата pytest (0 - успех, иначе - ошибка)
        if result.returncode == 0:
            print("Тесты успешно пройдены.")
        else:
            print("Тесты не пройдены. Код возврата:", result.returncode)
    except Exception as e:
        print("Произошла ошибка:", e)


if __name__ == "__main__":
    with mock.patch("telebot.types.Message", PathedMessage):
        run_pytest()
