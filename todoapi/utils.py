import re
import random
import string
from time import time
from functools import wraps
from typing import Callable

from cachetools import LRUCache
from cachetools.keys import hashkey

# noinspection PyPackageRequirements
from argon2 import PasswordHasher

# noinspection PyPackageRequirements
from argon2.exceptions import VerifyMismatchError, InvalidHashError

import config


re_username = re.compile("^[a-zA-Z](?!.*__)[a-zA-Z0-9_]{2,29}[a-zA-Z0-9]$")
re_date = re.compile(r"\A\d{2}\.\d{2}\.\d{4}\Z")
sql_date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
sql_datetime_pattern = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
password_hasher = PasswordHasher()


def sqlite_format_date(_column: str) -> str:
    """
    Database sql column converts from format
    dd.mm.yyyy to yyyy.mm.dd for sql expression

    :param _column: Column for transformation.
    :return: SQL expression
    """
    return f"""
SUBSTR({_column}, 7, 4) || '-' || SUBSTR({_column}, 4, 2) || '-' || SUBSTR({_column}, 1, 2)
""".strip()


def is_admin_id(chat_id: int) -> bool:
    """
    Check for admin
    Only people whose id is written in config.admin_id can be an admin
    """
    return chat_id in config.ADMIN_IDS


def is_valid_year(year: int) -> bool:
    """
    Is the year valid (in the range from config.MIN_CALENDAR_YEAR to config.MAX_CALENDAR_YEAR)?
    """
    return config.MIN_CALENDAR_YEAR <= year <= config.MAX_CALENDAR_YEAR


def chunks(lst: tuple | list, n: int):
    """
    Yield successive n-sized chunks from lst

    >>> for chunk in chunks(list(range(20)), 3):
    ...     print(chunk)
    ...
    [0, 1, 2]
    [3, 4, 5]
    [6, 7, 8]
    [9, 10, 11]
    [12, 13, 14]
    [15, 16, 17]
    [18, 19]

    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(hashed_password: str, password: str) -> bool:
    try:
        password_hasher.verify(hashed_password, password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def rate_limit(
    storage: LRUCache,
    max_calls: int,
    seconds: int,
    key_func: Callable = hashkey,
    else_func: Callable = lambda args, kwargs, key, sec: (key, sec),
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs)
            contains = key in storage
            t = time()

            if contains:
                storage[key] = [call for call in storage[key] if t - call < seconds]

                if len(storage[key]) >= max_calls:
                    sec = seconds - int(t - storage[key][0])
                    return else_func(args, kwargs, key=key, sec=sec)

            storage.setdefault(key, []).append(t)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def generate_token(length: int = 32):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))
