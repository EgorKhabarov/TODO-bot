# noinspection PyPackageRequirements
from contextvars import ContextVar
# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

from todoapi.api import User


class Request:
    """
    Класс контекстных переменных

    request.user: todoapi.api.User

    request.chat_id: todoapi.api.User  # TODO добавить в todoapi.api.User

    request.query: telebot.types.Message | telebot.types.CallbackQuery
    """
    _user = ContextVar("user", default=None)
    _chat_id = ContextVar("chat_id", default=None)
    _query = ContextVar("query", default=None)

    @property
    def user(self) -> User:
        return self._user.get()  # type: ignore

    @property
    def chat_id(self) -> int:
        return self._chat_id.get()  # type: ignore

    @property
    def query(self) -> Message | CallbackQuery:
        return self._query.get()  # type: ignore

    @user.setter
    def user(self, user: User):
        self._user.set(user)  # type: ignore

    @chat_id.setter
    def chat_id(self, chat_id: int):
        self._chat_id.set(chat_id)  # type: ignore

    @query.setter
    def query(self, query: Message | CallbackQuery):
        self._query.set(query)  # type: ignore


request = Request()
