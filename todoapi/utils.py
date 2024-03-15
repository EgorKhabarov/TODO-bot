import re

import config


re_email = re.compile(".+@.+\..+")
re_username = re.compile("^[a-zA-Z](?!.*__)[a-zA-Z0-9_]{2,29}[a-zA-Z0-9]$")
re_date = re.compile(r"\A\d{2}\.\d{2}\.\d{4}\Z")
sql_date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")


def sqlite_format_date(_column):
    """
    Столбец sql базы данных превращает из формата
    dd.mm.yyyy в yyyy.mm.dd в виде sql выражения

    :param _column: Столбец для превращения.
    :return: SQL выражение
    """
    return f"""
SUBSTR({_column}, 7, 4) || '-' ||
SUBSTR({_column}, 4, 2) || '-' ||
SUBSTR({_column}, 1, 2)"""


def is_admin_id(chat_id: int) -> bool:
    """
    Проверка на админа
    Админом могут быть только люди, чьи id записаны в config.admin_id
    """
    return chat_id in config.ADMIN_IDS


def is_premium_user(user) -> bool:
    """
    Является ли премиум пользователем
    """
    return user.user_status >= 1 or is_admin_id(user.chat_id)


def is_valid_year(year: int) -> bool:
    """
    Является ли год валидным (находится в диапазоне от 1900 до 2300)
    """
    return 1900 <= year <= 2300


def isdigit(string: str) -> bool:
    """Замена str.isdigit()"""
    return string.isdigit() if string[:1] != "-" else string[1:].isdigit()
