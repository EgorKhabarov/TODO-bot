# noinspection PyPackageRequirements
from contextvars import ContextVar
from typing import Literal

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery

from todoapi.types import User, Group


class Request:
    """
    Класс контекстных переменных

    request.user: todoapi.api.User

    request.chat_id: todoapi.api.User

    request.query: telebot.types.Message | telebot.types.CallbackQuery
    """

    _entity = ContextVar("entity", default=None)
    _entity_type = ContextVar("entity_type", default=None)
    _chat_id = ContextVar("chat_id", default=None)
    _query = ContextVar("query", default=None)

    @property
    def entity(self) -> User | Group:
        return self._entity.get()  # type: ignore

    @entity.setter
    def entity(self, entity: User | Group) -> None:
        self._entity.set(entity)  # type: ignore

    @property
    def entity_type(self) -> Literal["user", "group"]:
        return self._entity_type.get()  # type: ignore

    @entity_type.setter
    def entity_type(self, entity_type: Literal["user", "group"]) -> None:
        self._entity_type.set(entity_type)  # type: ignore

    @property
    def chat_id(self) -> int:
        return self._chat_id.get()  # type: ignore

    @chat_id.setter
    def chat_id(self, chat_id: int) -> None:
        self._chat_id.set(chat_id)  # type: ignore

    @property
    def query(self) -> Message | CallbackQuery:
        return self._query.get()  # type: ignore

    @query.setter
    def query(self, query: Message | CallbackQuery) -> None:
        self._query.set(query)  # type: ignore

    @property
    def is_user(self):
        return self.entity_type == "user"

    @property
    def is_group(self):
        return self.entity_type == "group"


request = Request()
