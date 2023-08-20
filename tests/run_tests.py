import subprocess


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
    run_pytest()
