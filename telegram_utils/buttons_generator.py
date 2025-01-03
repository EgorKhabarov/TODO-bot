from typing import Literal, Any, Union

# noinspection PyPackageRequirements
from telebot.types import (
    ForceReply,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


buttons_data_types = Union[
    list[list[dict[str, str | dict]]], list[list[str]], dict[str, Any], None
]
return_buttons_types = Union[
    ForceReply, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, None
]
keyboard_types = Union[Literal["inline", "reply", "force_reply", "reply_remove"], str]


def generate_buttons(
    buttons_data: buttons_data_types, keyboard_type: keyboard_types = "inline"
) -> return_buttons_types:
    """
    >>> from pprint import pprint
    >>> def inline_buttons_printer(buttons: return_buttons_types):
    ...     result = [isinstance(buttons, InlineKeyboardMarkup)]
    ...     for r in buttons.keyboard:
    ...         result.append([])
    ...         for b in r:
    ...             result[-1].append(b.to_dict())
    ...     pprint(result)
    ...
    >>> inline_buttons_printer(
    ...     generate_buttons(
    ...         [
    ...             [
    ...                 {"button text": "call data"},  # simple button
    ...             ],
    ...             [
    ...                 {
    ...                     "button text": {
    ...                         "url": None,
    ...                         "callback_data": "call data",
    ...                         "web_app": None,
    ...                         "switch_inline_query": None,
    ...                         "switch_inline_query_current_chat": None,
    ...                         "callback_game": None,
    ...                         "pay": None,
    ...                         "login_url": None,
    ...                         "**kwargs": {},
    ...                     }
    ...                 },
    ...                 {
    ...                     "text": "button text",
    ...                     "url": None,
    ...                     "callback_data": "call data",
    ...                     "web_app": None,
    ...                     "switch_inline_query": None,
    ...                     "switch_inline_query_current_chat": None,
    ...                     "callback_game": None,
    ...                     "pay": None,
    ...                     "login_url": None,
    ...                     "**kwargs": {},
    ...                 },
    ...             ],
    ...         ]
    ...     )
    ... )
    [True,
     [{'callback_data': 'call data', 'text': 'button text'}],
     [{'callback_data': 'call data', 'text': 'button text'},
      {'callback_data': 'call data', 'text': 'button text'}]]
    >>> def reply_buttons_printer(buttons):
    ...     print((isinstance(buttons, ReplyKeyboardMarkup), buttons.keyboard))
    >>> reply_buttons_printer(generate_buttons([["1", "2", "3"]], keyboard_type="reply"))
    (True, [[{'text': '1'}, {'text': '2'}, {'text': '3'}]])
    """

    if isinstance(buttons_data, InlineKeyboardMarkup):
        return buttons_data

    match keyboard_type:
        case "inline":
            keyboard = []
            for row in buttons_data:
                keyboard.append([])
                for button in row:
                    if button == {}:
                        continue

                    if len(button.keys()) == 1:
                        [(text, data)] = button.items()
                        if isinstance(data, str):
                            keyboard[-1].append(
                                InlineKeyboardButton(text, callback_data=data)
                            )
                        elif isinstance(data, dict):
                            [(text, data)] = button.items()
                            keyboard[-1].append(InlineKeyboardButton(text=text, **data))
                        else:
                            return None
                    else:
                        keyboard[-1].append(InlineKeyboardButton(**button))

            return InlineKeyboardMarkup(keyboard=keyboard)

        case "reply":
            markup = ReplyKeyboardMarkup()
            for row in buttons_data:
                markup.add(*row)
            return markup

        case "force_reply":
            return ForceReply(**{} if buttons_data is None else buttons_data)

        case "reply_remove":
            return ReplyKeyboardRemove(**{} if buttons_data is None else buttons_data)

        case _:
            return None


def edit_button_data(
    markup: InlineKeyboardMarkup,
    row: int,
    column: int,
    callback_data: str = ...,
    text: str = ...,
) -> None:
    if callback_data is not ...:
        markup.keyboard[row][column].callback_data = callback_data
    if text is not ...:
        markup.keyboard[row][column].text = text
