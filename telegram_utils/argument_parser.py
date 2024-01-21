from typing import Any, Literal, TypeAlias, Callable
from datetime import datetime


_data_types: TypeAlias = (
    str
    | Literal[
        "str",
        "int",
        "float",
        "date",
        "long str",
    ]
)
_return_types: TypeAlias = str | int | float | datetime | list[int] | None | Any


def get_arguments(
    text: str, arguments: dict[str, _data_types | tuple[_data_types, Any]]
) -> dict[str, _return_types]:
    """
    >>> try: get_arguments("", {"arg1": "long str", "arg2": "str"})
    ... except SyntaxError as e: str(e)
    'parameter after or before "long str"'
    >>> try: get_arguments("", {"arg1": "long str", "arg2": "long str"})
    ... except SyntaxError as e: str(e)
    'multiple starred expressions in assignment'

    >>> get_arguments("", {})
    {}
    >>> get_arguments("abrakadabra", {})
    {}

    >>> arguments_1 = {"text": "long str"}
    >>> get_arguments("arg1 arg2", arguments_1)
    {'text': 'arg1 arg2'}
    >>> get_arguments("abrakadabra", arguments_1)
    {'text': 'abrakadabra'}

    >>> arguments_2 = {"arg1": "str", "arg2": ("str", "string")}
    >>> get_arguments("", arguments_2)
    {'arg1': None, 'arg2': 'string'}
    >>> get_arguments("arg1", arguments_2)
    {'arg1': 'arg1', 'arg2': 'string'}
    >>> get_arguments("arg1 arg2", arguments_2)
    {'arg1': 'arg1', 'arg2': 'arg2'}
    >>> get_arguments("arg1 arg2 arg3", arguments_2)
    {'arg1': 'arg1', 'arg2': 'arg2'}

    >>> arguments_3 = {"arg1": "str", "arg2": ("int", 1)}
    >>> get_arguments("", arguments_3)
    {'arg1': None, 'arg2': 1}
    >>> get_arguments("123 123", arguments_3)
    {'arg1': '123', 'arg2': 123}
    >>> get_arguments("arg1 123", arguments_3)
    {'arg1': 'arg1', 'arg2': 123}
    >>> get_arguments("arg1", arguments_3)
    {'arg1': 'arg1', 'arg2': 1}
    >>> get_arguments("arg1 arg2", arguments_3)
    {'arg1': 'arg1', 'arg2': None}

    >>> arguments_4 = {"arg1": "float"}
    >>> get_arguments("123", arguments_4)
    {'arg1': 123}
    >>> get_arguments("123.456", arguments_4)
    {'arg1': 123.456}

    >>> arguments_5 = {"arg1": "date"}
    >>> get_arguments("01012000", arguments_5)
    {'arg1': None}
    >>> get_arguments("text", arguments_5)
    {'arg1': None}
    >>> get_arguments("01/02/2000", arguments_5)
    {'arg1': None}
    >>> get_arguments("01:02:2000", arguments_5)
    {'arg1': None}
    >>> get_arguments("01.02.2000", arguments_5)
    {'arg1': datetime.datetime(2000, 2, 1, 0, 0)}
    >>> get_arguments("2000.02.01", arguments_5)
    {'arg1': datetime.datetime(2000, 2, 1, 0, 0)}
    """
    types = [(t[0] if isinstance(t, tuple) else t) for t in arguments.values()]

    if types.count("long str") > 1:
        raise SyntaxError("multiple starred expressions in assignment")

    if types.count("long str") and len(set(types)) > 1:
        raise SyntaxError('parameter after or before "long str"')

    if not arguments:
        return {}

    if not text:
        return {
            k: (v[1] if isinstance(v, tuple) else None) for k, v in arguments.items()
        }

    args = [text.strip()] if "long str" in types else text.strip().split()

    result = {k: None for k in arguments}
    defaults = ((d[1] if isinstance(d, tuple) else None) for d in arguments.values())

    for i, (n, t, d) in enumerate(zip(arguments, types, defaults)):
        try:
            arg = args[int(i)]
        except IndexError:
            arg = d
        else:
            arg = __process_value(t, arg, d)
        result[n] = arg

    return result


def __process_value(
    arg_type: _data_types, value: str, default: Any = None
) -> _return_types | None:
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


def getargs(
    __func: Callable, text: str
) -> Callable[
    [dict[str, _data_types | tuple[_data_types, Any]]], dict[str, _return_types]
]:
    def closure(
        arg: dict[str, _data_types | tuple[_data_types, Any]]
    ) -> dict[str, _return_types]:
        return get_arguments(text, arg)

    return closure
