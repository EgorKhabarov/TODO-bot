import re
from time import time
from hashlib import sha256
from functools import wraps
from typing import Callable

from cachetools import LRUCache
from cachetools.keys import hashkey

import config


re_username = re.compile("^[a-zA-Z](?!.*__)[a-zA-Z0-9_]{2,29}[a-zA-Z0-9]$")
re_date = re.compile(r"\A\d{2}\.\d{2}\.\d{4}\Z")
sql_date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")


def sqlite_format_date(_column):
    """
    Database sql column converts from format
    dd.mm.yyyy to yyyy.mm.dd as an sql expression

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


def is_premium_user(user) -> bool:
    """
    Is a premium user
    """
    return user.user_status >= 1 or is_admin_id(user.chat_id)


def is_valid_year(year: int) -> bool:
    """
    Is the year valid (in the range from 1900 to 2300)?
    """
    return 1900 <= year <= 2300


def isdigit(string: str) -> bool:
    """
    Replacing str.isdigit()
    """
    return string.isdigit() if string[:1] != "-" else string[1:].isdigit()


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def hash_password(password: str):
    return sha256(password.encode("utf-8")).hexdigest()


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
