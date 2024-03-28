# noinspection PyPackageRequirements
from contextvars import ContextVar
from dataclasses import dataclass

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery
from tgbot.types import TelegramAccount


@dataclass
class EntityType:
    user: bool = False
    member: bool = False

    def __repr__(self):
        return "user" if self.user else "member"


class Request:
    """
    Класс контекстных переменных
    """
    _entity = ContextVar("entity", default=None)
    _entity_type = ContextVar("entity_type", default=None)
    _chat_id = ContextVar("chat_id", default=None)
    _query = ContextVar("query", default=None)

    @property
    def entity(self) -> TelegramAccount:
        return self._entity.get()  # type: ignore

    @entity.setter
    def entity(self, entity: TelegramAccount) -> None:
        self._entity.set(entity)  # type: ignore

    @property
    def entity_type(self) -> EntityType:
        return self._entity_type.get()  # type: ignore

    @entity_type.setter
    def entity_type(self, entity_type: EntityType) -> None:
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
        return self.entity_type.user

    @property
    def is_member(self):
        return self.entity_type.member


request = Request()
