# noinspection PyPackageRequirements
from contextvars import ContextVar
from dataclasses import dataclass

# noinspection PyPackageRequirements
from telebot.types import Message, CallbackQuery
from notes_bot.types import TelegramAccount


@dataclass
class EntityType:
    user: bool = False
    member: bool = False

    def __repr__(self):
        return "user" if self.user else "member"


@dataclass
class QueryType:
    message: bool = False
    callback: bool = False

    def __repr__(self):
        return "message" if self.message else "callback"


class Request:
    """
    Context Variable Class
    """

    _entity = ContextVar("entity", default=None)
    _entity_type = ContextVar("entity_type", default=None)
    _chat_id = ContextVar("chat_id", default=None)
    _query = ContextVar("query", default=None)
    _message = ContextVar("message", default=None)
    _query_type = ContextVar("query_type", default=None)

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
    def message(self) -> Message:
        return self._message.get()  # type: ignore

    @message.setter
    def message(self, message: Message) -> None:
        self._message.set(message)  # type: ignore

    @property
    def query_type(self) -> QueryType:
        return self._query_type.get()  # type: ignore

    @query_type.setter
    def query_type(self, query_type: QueryType) -> None:
        self._query_type.set(query_type)  # type: ignore

    @property
    def is_user(self) -> bool:
        return self.entity_type.user

    @property
    def is_member(self) -> bool:
        return self.entity_type.member

    @property
    def is_message(self) -> bool:
        return self.query_type.message

    @property
    def is_callback(self) -> bool:
        return self.query_type.callback

    def set(self, query: Message | CallbackQuery):
        self.query = query
        self.query_type = QueryType(
            message=isinstance(query, Message),
            callback=isinstance(query, CallbackQuery),
        )
        if request.is_callback:
            self.message = query.message
        else:
            self.message = query

        self.chat_id = self.message.chat.id
        self.entity_type = EntityType(
            user=self.message.chat.type == "private",
            member=self.message.chat.type != "private",
        )


request = Request()
