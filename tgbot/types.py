from sqlite3 import Error
from functools import cached_property

from config import ADMIN_IDS
from todoapi.types import User, db, Group, Settings, allow_for
from todoapi.exceptions import ApiError, UserNotFound, GroupNotFound


class TelegramSettings(Settings):
    def __init__(
        self,
        lang: str = "ru",
        sub_urls: bool = True,
        city: str = "Москва",
        timezone: int = 3,
        direction: str = "DESC",
        notifications: bool = False,
        notifications_time: str = "08:00",
        theme: int = 0,
        add_event_date: str = "",
    ):
        super().__init__(lang, sub_urls, city, timezone, direction, notifications, notifications_time, theme)
        self.add_event_date = add_event_date


class TelegramUser(User):
    def __init__(
        self,
        user_id: int,
        chat_id: int,
        username: str,
        user_status: int,
        reg_date: str,
        max_event_id: int | None = None,
        *,
        group_id: str | None = None,
        group_chat_id: int | None = None,
    ):
        super().__init__(user_id, username, user_status, reg_date, max_event_id=max_event_id, group_id=group_id)
        self.chat_id = chat_id
        self.group_chat_id = group_chat_id

    @property
    def request_chat_id(self):
        return self.group_chat_id or self.chat_id

    @property
    @allow_for(user=True)
    def is_admin(self) -> bool:
        return self.user_status >= 2 or self.request_chat_id in ADMIN_IDS

    @cached_property
    def settings(self) -> TelegramSettings:
        return self.get_user_settings()

    def get_user_settings(self) -> TelegramSettings:
        try:
            settings = db.execute(
                """
SELECT lang,
       sub_urls,
       city,
       timezone,
       direction,
       notifications,
       notifications_time,
       theme,
       add_event_date
  FROM tg_settings
 WHERE user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "user_id": None if self.group_id else self.user_id,
                    "group_id": self.group_id,
                },
            )[0]
        except Error:
            raise ApiError
        except IndexError:
            raise UserNotFound

        return TelegramSettings(*settings)


class TelegramGroup(Group):
    def __init__(self, group_id: str, chat_id: int, name: str, owner_id: int, max_event_id: int):
        super().__init__(group_id, name, owner_id, max_event_id)
        self.chat_id = chat_id


def get_group_from_chat_id(telegram_group_chat_id) -> TelegramGroup:
    try:
        group = db.execute(
            """
SELECT group_id,
       name,
       owner_id,
       max_event_id
  FROM groups
 WHERE chat_id = :chat_id;
""",
            params={"chat_id": telegram_group_chat_id},
        )[0]
    except Error:
        raise ApiError
    except IndexError:
        raise GroupNotFound

    group_id, name, owner_id, max_event_id = group
    return TelegramGroup(group_id, telegram_group_chat_id, name, owner_id, max_event_id)


def get_user_from_chat_id(telegram_user_id: int, telegram_group_chat_id: int | None = None) -> TelegramUser:
    # TODO защита от перебора брутфорса и количества попыток

    if telegram_group_chat_id:
        group = get_group_from_chat_id(telegram_group_chat_id)
        group_id = group.group_id
        group_chat_id = group.chat_id
    else:
        group_id = None
        group_chat_id = None

    try:
        user = db.execute(
            """
SELECT user_id,
       chat_id,
       username,
       user_status,
       reg_date,
       max_event_id
 FROM users
WHERE chat_id = :chat_id;
""",
            params={"chat_id": telegram_user_id},
        )[0]
    except Error:
        raise ApiError
    except IndexError:
        raise UserNotFound

    return TelegramUser(*user, group_id=group_id, group_chat_id=group_chat_id)
