# noinspection PyPackageRequirements
from contextvars import ContextVar

from todoapi.api import User


class Request:
    _user_info = ContextVar("user_info", default=None)
    _chat_id = ContextVar("chat_id", default=None)

    @property
    def user(self) -> User:
        # FIXME
        return self._user_info.get()  # type: ignore

    @user.setter
    def user(self, user_data):
        self._user_info.set(user_data)

    @property
    def chat_id(self):
        return self._chat_id.get()

    @chat_id.setter
    def chat_id(self, chat_id):
        self._chat_id.set(chat_id)


request = Request()
