import re
from typing import Any, Literal, TypeAlias
from datetime import datetime


__data_types: TypeAlias = Literal["str", "int", "float", "date", "long str"]


class __CommandRegex:
    def __init__(self):
        self.username = None
        self.__regex = None
        self.set_username()

    def set_username(self, raw_bot_username: str | None = None):
        self.username = (
            re.escape(raw_bot_username) if raw_bot_username else "[a-zA-Z0-9_]{5,32}"
        )
        self.__regex = re.compile(
            r"(?s)\A/(?P<command>[a-zA-Z0-9_]+)"
            rf"(?P<username>@{self.username}\b)?"
            r"(?:\s|$)(?P<arguments>.+)?\Z"
        )

    def __getattr__(self, item):
        if item in ("username", "set_bot_username"):
            return self.username if item == "username" else self.set_username

        return getattr(self.__regex, item)


command_regex = __CommandRegex()


def get_command_arguments(message: str, **kwargs: str | tuple[str, Any]) -> dict:
    """
    >>> try:
    ...     get_command_arguments("/c@namebot arg1 arg2", arg1="long str", arg2="str")
    ... except SyntaxError as e:
    ...     str(e)
    'parameter after or before "long str"'
    >>> try:
    ...     get_command_arguments("/c@namebot arg1 arg2", arg1="long str", arg2="long str")
    ... except SyntaxError as e:
    ...     str(e)
    'multiple starred expressions in assignment'
    >>> get_command_arguments("")
    {}
    >>> get_command_arguments("", arg1="str", arg2=("str", 1))
    {'arg1': None, 'arg2': None}
    >>> get_command_arguments("/c", arg1="str", arg2=("str", 1))
    {'arg1': None, 'arg2': 1}
    >>> get_command_arguments("/c@namebot", arg1="str", arg2=("str", 1))
    {'arg1': None, 'arg2': 1}
    >>> get_command_arguments("/c@namebot arg1", arg1="str", arg2=("str", 1))
    {'arg1': 'arg1', 'arg2': 1}
    >>> get_command_arguments("/c@namebot arg1 arg2", arg1="str", arg2=("str", 1))
    {'arg1': 'arg1', 'arg2': 'arg2'}
    >>> get_command_arguments("/c@namebot arg1 arg2 arg3", arg1="str", arg2=("str", 1))
    {'arg1': 'arg1', 'arg2': 'arg2'}
    >>> get_command_arguments("/c@namebot arg1 arg2", text="long str")
    {'text': 'arg1 arg2'}
    >>> get_command_arguments("abrakadabra")
    {}
    >>> get_command_arguments("abrakadabra", text="long str")
    {'text': None}
    """
    types = [(t[0] if isinstance(t, tuple) else t) for t in kwargs.values()]

    if types.count("long str") > 1:
        raise SyntaxError("multiple starred expressions in assignment")

    if types.count("long str") and len(set(types)) > 1:
        raise SyntaxError('parameter after or before "long str"')

    if not kwargs:
        return {}

    match = command_regex.match(message)

    if match is None:
        return {k: None for k in kwargs}

    groups = match.groupdict()
    if groups["arguments"] is None:
        return {k: (v[1] if isinstance(v, tuple) else None) for k, v in kwargs.items()}

    args = [groups["arguments"]] if "long str" in types else groups["arguments"].split()

    result = {k: None for k in kwargs}
    defaults = ((d[1] if isinstance(d, tuple) else None) for d in kwargs.values())

    for i, (n, t, d) in enumerate(zip(kwargs, types, defaults)):
        try:
            arg = args[int(i)]
        except IndexError:
            arg = d
        else:
            arg = __process_value(t, arg, d)
        result[n] = arg
    return result


def parse_command(
    message: str, **kwargs: str | tuple[str, Any]
) -> dict[str:str, str:str, str:dict]:
    """
    >>> try:
    ...     parse_command("/c@namebot arg1 arg2", arg1="long str", arg2="str")
    ... except SyntaxError as e:
    ...     str(e)
    'parameter after or before "long str"'
    >>> try:
    ...     parse_command("/c@namebot arg1 arg2", arg1="long str", arg2="long str")
    ... except SyntaxError as e:
    ...     str(e)
    'multiple starred expressions in assignment'
    >>> parse_command("")
    {'command': None, 'username': None, 'arguments': {}}
    >>> parse_command("/c@namebot")
    {'command': 'c', 'username': '@namebot', 'arguments': {}}
    >>> parse_command("/c@namebot arg1")
    {'command': 'c', 'username': '@namebot', 'arguments': {}}
    >>> parse_command("/c@namebot arg1 arg2")
    {'command': 'c', 'username': '@namebot', 'arguments': {}}

    >>> parse_command("", arg1="str", arg2=("str", 1))
    {'command': None, 'username': None, 'arguments': {'arg1': None, 'arg2': None}}
    >>> parse_command("/c@namebot", arg1="str", arg2=("str", 1))
    {'command': 'c', 'username': '@namebot', 'arguments': {'arg1': None, 'arg2': 1}}
    >>> parse_command("/c@namebot arg1", arg1="str", arg2=("str", 1))
    {'command': 'c', 'username': '@namebot', 'arguments': {'arg1': 'arg1', 'arg2': 1}}
    >>> parse_command("/c@namebot arg1 arg2", arg1="str", arg2=("str", 1))
    {'command': 'c', 'username': '@namebot', 'arguments': {'arg1': 'arg1', 'arg2': 'arg2'}}
    """
    arguments = get_command_arguments(message, **kwargs)
    match = command_regex.match(message)
    if match:
        groups = match.groupdict()
        return {
            "command": groups["command"],
            "username": groups["username"],
            "arguments": arguments,
        }
    else:
        return {
            "command": None,
            "username": None,
            "arguments": {k: None for k in kwargs},
        }


def __process_value(
    arg_type: __data_types, value: str, default: Any = None
) -> str | int | float | None | datetime:
    match arg_type:
        case "str":
            return value
        case "int" | "float":
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return None
        case "date":
            try:
                return datetime.strptime(value, "%d.%m.%Y")
            except ValueError:
                try:
                    return datetime.strptime(value, "%Y.%m.%d")
                except ValueError:
                    return default
        case "long str":
            return value
