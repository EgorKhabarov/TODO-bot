import json
from typing import Literal
from ast import literal_eval
from cachetools import LFUCache, cached
from functools import cached_property

# noinspection PyPackageRequirements
from telebot.types import Message

from config import ADMIN_IDS
from tgbot.bot import bot
from todoapi.utils import verify_password
from todoapi.types import User, db, Group, Settings, Account
from todoapi.logger import logger
from todoapi.exceptions import (
    ApiError,
    DataBaseError,
    UserNotFound,
    GroupNotFound,
    NotEnoughPermissions,
    Forbidden,
)


class TelegramSettings(Settings):
    pass


class TelegramGroup(Group):
    def __init__(
        self,
        group_id: str,
        chat_id: int,
        name: str,
        owner_id: int,
        max_event_id: int,
        entry_date: str | None = None,
        member_status: int | None = None,
    ):
        super().__init__(
            group_id, name, owner_id, max_event_id, entry_date, member_status
        )
        self.chat_id = chat_id

    @classmethod
    def get_from_group_id(cls, group_id: str, user_chat_id: int) -> "TelegramGroup":
        try:
            group = db.execute(
                """
SELECT group_id,
       chat_id,
       name,
       owner_id,
       max_event_id
  FROM groups
 WHERE group_id = :group_id;
""",
                params={"group_id": group_id},
            )[0]
        except DataBaseError as e:
            raise ApiError(e)
        except IndexError:
            raise GroupNotFound

        member_status = ("member", "administrator", "creator").index(
            bot.get_chat_member(group[1], user_chat_id).status
        )
        return TelegramGroup(*group, "", member_status)

    @classmethod
    def get_from_chat_id(cls, group_chat_id: int, user_chat_id: int) -> "TelegramGroup":
        try:
            group = db.execute(
                """
SELECT g.group_id,
       g.chat_id,
       g.name,
       g.owner_id,
       g.max_event_id,
       u.user_status
  FROM groups AS g
  JOIN users  AS u
    /*
    If the user is banned, the group is banned for everyone `ON g.owner_id = u.user_id`
    If a user is banned, the group is banned for that user  `ON u.chat_id = :user_chat_id`
    */
    ON u.chat_id = :user_chat_id
 WHERE g.chat_id = :group_chat_id;
""",
                params={
                    "group_chat_id": group_chat_id,
                    "user_chat_id": user_chat_id,
                },
            )[0]
        except DataBaseError as e:
            raise ApiError(e)
        except IndexError:
            raise GroupNotFound

        group_id, chat_id, name, owner_id, max_event_id, user_status = group

        if user_status == -1:
            member_status = -1
        else:
            telegram_group_member = bot.get_chat_member(group_chat_id, user_chat_id)
            match telegram_group_member.status:
                case "administrator":
                    member_status = 1
                case "creator":
                    member_status = 2
                case _:  # "member"
                    member_status = 0

        return TelegramGroup(
            group_id,
            chat_id,
            name,
            owner_id,
            max_event_id,
            "",
            member_status,
        )


class TelegramUser(User):
    def __init__(
        self,
        user_id: int,
        chat_id: int,
        user_status: int,
        username: str,
        password: str,
        max_event_id: int | None = None,
        reg_date: str | None = None,
    ):
        self.chat_id = chat_id
        super().__init__(
            user_id,
            user_status,
            username,
            password=password,
            max_event_id=max_event_id,
            reg_date=reg_date,
        )

    @classmethod
    def get_from_user_id(cls, user_id: int) -> "TelegramUser":
        # TODO защита от перебора брутфорса и количества попыток
        try:
            user = db.execute(
                """
SELECT user_id,
       chat_id,
       user_status,
       username,
       password,
       max_event_id,
       reg_date
  FROM users
 WHERE user_id = :user_id;
""",
                params={"user_id": user_id},
            )[0]
        except DataBaseError as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return TelegramUser(*user)

    @classmethod
    def get_from_chat_id(cls, chat_id: int) -> "TelegramUser":
        # TODO защита от перебора брутфорса и количества попыток
        try:
            user = db.execute(
                """
SELECT user_id,
       chat_id,
       user_status,
       username,
       password,
       max_event_id,
       reg_date
  FROM users
 WHERE chat_id = :chat_id;
""",
                params={"chat_id": chat_id},
            )[0]
        except DataBaseError as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return TelegramUser(*user)

    @classmethod
    def get_from_password(cls, username: str, password: str) -> "TelegramUser":
        # TODO защита от перебора брутфорса и количества попыток
        try:
            user = db.execute(
                """
SELECT user_id,
       chat_id,
       user_status,
       username,
       password,
       max_event_id,
       reg_date
  FROM users
 WHERE username = :username;
""",
                params={"username": username},
            )[0]

            if not verify_password(user[4], password):
                raise IndexError
        except DataBaseError as e:
            raise ApiError(e)
        except IndexError:
            raise UserNotFound

        return TelegramUser(*user)


class TelegramAccount(Account):
    def __init__(self, chat_id: int, group_chat_id: int | None = None):
        self.chat_id, self.group_chat_id = chat_id, group_chat_id
        super().__init__(
            self.user.user_id if not group_chat_id else 0,
            self.group.group_id if group_chat_id else None,
        )

    @cached_property
    def user(self) -> TelegramUser:
        return TelegramUser.get_from_chat_id(self.chat_id)

    @cached_property
    def group(self) -> TelegramGroup | None:
        if self.group_chat_id:
            return TelegramGroup.get_from_chat_id(self.group_chat_id, self.chat_id)
        else:
            return None

    @property
    def request_chat_id(self) -> int:
        return self.group_chat_id or self.chat_id

    @property
    def request_id(self) -> int | str:
        return self.group_id or self.user_id

    @property
    def is_admin(self) -> bool:
        return self.user.user_status >= 2 or self.request_chat_id in ADMIN_IDS

    def get_settings(self) -> TelegramSettings:
        return self.get_telegram_user_settings()

    def get_telegram_user_settings(self) -> TelegramSettings:
        try:
            settings = db.execute(
                """
SELECT lang,
       sub_urls,
       city,
       timezone,
       notifications,
       notifications_time,
       theme
  FROM tg_settings
 WHERE user_id IS :user_id
       AND group_id IS :group_id;
""",
                params={
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
            )[0]
        except DataBaseError as e:
            raise ApiError(e)
        except IndexError:
            raise (GroupNotFound if self.group_id else UserNotFound)

        return TelegramSettings(*settings)

    def set_telegram_user_settings(
        self,
        lang: Literal["ru", "en"] | None = None,
        sub_urls: Literal[0, 1] | None = None,
        city: str | None = None,
        timezone: int | None = None,
        notifications: Literal[0, 1, 2] | bool | None = None,
        notifications_time: str | None = None,
        theme: int | None = None,
    ) -> None:
        """
        user_id            INT  UNIQUE NOT NULL,
        lang               TEXT DEFAULT 'ru',
        sub_urls           INT  CHECK (sub_urls IN (0, 1)) DEFAULT (1),
        city               TEXT DEFAULT 'London',
        timezone           INT  CHECK (-13 < timezone < 13) DEFAULT (3),
        notifications      INT  CHECK (notifications IN (0, 1, 2)) DEFAULT (0),
        notifications_time TEXT DEFAULT "08:00",
        theme              INT  DEFAULT (0),
        """
        update_list = []

        if lang is not None:
            if lang not in ("ru", "en"):
                raise ValueError('lang must be in ["ru", "en"]')

            update_list.append("lang")
            self.settings.lang = lang

        if sub_urls is not None:
            if sub_urls not in (0, 1, "0", "1"):
                raise ValueError("sub_urls must be in [0, 1]")

            update_list.append("sub_urls")
            self.settings.sub_urls = int(sub_urls)

        if city is not None:
            if len(city) > 50:
                raise ValueError("length city must be less than 50 characters")

            update_list.append("city")
            self.settings.city = city

        if timezone is not None:
            if timezone not in [j for i in range(-11, 12) for j in (i, str(i))]:
                raise ValueError("timezone must be -12 and less 12")

            update_list.append("timezone")
            self.settings.timezone = int(timezone)

        if notifications is not None:
            if notifications not in (0, 1, 2, "0", "1", "2", True, False):
                raise ValueError("notifications must be in [0, 1, 2]")

            update_list.append("notifications")
            self.settings.notifications = int(notifications)

        if notifications_time is not None:
            hour, minute = [int(v) for v in notifications_time.split(":")]
            if not -1 < hour < 24:
                raise ValueError("hour must be more -1 and less 24")

            if minute not in (0, 10, 20, 30, 40, 50):
                raise ValueError("minute must be in [0, 10, 20, 30, 40, 50]")

            update_list.append("notifications_time")
            self.settings.notifications_time = notifications_time

        if theme is not None:
            if theme not in (0, 1, "0", "1"):
                raise ValueError("theme must be in [0, 1]")

            update_list.append("theme")
            self.settings.theme = int(theme)

        try:
            db.execute(
                """
UPDATE tg_settings
   SET {}
 WHERE user_id IS :user_id
       AND group_id IS :group_id;
""".format(
                    ", ".join(f"{update} = :{update}" for update in update_list)
                ),
                params={
                    "lang": lang,
                    "sub_urls": sub_urls,
                    "city": city,
                    "timezone": timezone,
                    "notifications": notifications,
                    "notifications_time": notifications_time,
                    "theme": theme,
                    "user_id": self.safe_user_id,
                    "group_id": self.group_id,
                },
                commit=True,
            )
        except DataBaseError as e:
            raise ApiError(e)

    def set_group_telegram_chat_id(
        self, group_id: str | None = None, chat_id: int | None = None
    ) -> None:
        group_id = group_id or self.group_id

        if group_id is None:
            raise Forbidden

        if not self.is_owner(group_id):
            raise NotEnoughPermissions

        try:
            db.execute(
                """
UPDATE groups
   SET chat_id = :chat_id
 WHERE group_id = :group_id;
""",
                params={
                    "chat_id": chat_id,
                    "group_id": group_id,
                },
                commit=True,
            )
        except DataBaseError as e:
            raise ApiError(e)

    def get_group(self, group_id: str) -> TelegramGroup:
        if self.group_id:
            raise Forbidden

        return self.get_groups([group_id])[0]

    def get_groups(self, group_ids: list[str]) -> list[TelegramGroup]:
        if self.group_id:
            raise Forbidden

        if len(group_ids) > 400:
            raise ValueError

        try:
            groups = db.execute(
                f"""
SELECT group_id,
       chat_id,
       name,
       owner_id,
       max_event_id
  FROM groups
 WHERE group_id IN ({','.join('?' for _ in group_ids)})
 ORDER BY name ASC;
""",
                params=(*group_ids,),
            )
            members = db.execute(
                f"""
SELECT entry_date,
       member_status
  FROM members
 WHERE group_id IN ({','.join('?' for _ in group_ids)})
       AND user_id = ?;
""",
                params=(
                    *group_ids,
                    self.user_id,
                ),
            )
        except DataBaseError as e:
            raise ApiError(e)

        if not groups:
            raise GroupNotFound

        tg_groups = []
        for group, member in zip(groups, members):
            if self.check_member_exists(group_id=group[0]):
                tg_groups.append(TelegramGroup(*group, *member))

        if not tg_groups:
            raise GroupNotFound

        return tg_groups

    def get_my_groups(self, page: int = 1) -> list[TelegramGroup]:
        if self.group_id:
            raise Forbidden

        page -= 1
        try:
            groups = db.execute(
                """
SELECT groups.group_id,
       groups.chat_id,
       groups.name,
       groups.owner_id,
       groups.max_event_id,
       members.entry_date,
       members.member_status
  FROM groups
  JOIN members ON groups.group_id = members.group_id
 WHERE members.user_id = :user_id
 ORDER BY name ASC
 LIMIT :limit
OFFSET :offset;
""",
                params={
                    "user_id": self.user_id,
                    "limit": 12,
                    "offset": 12 * page,
                },
            )
        except DataBaseError as e:
            raise ApiError(e)

        return [TelegramGroup(*group) for group in groups]

    def get_groups_where_i_member(self, page: int = 1) -> list[TelegramGroup]:
        page -= 1
        try:
            groups = db.execute(
                """
SELECT groups.group_id,
       groups.chat_id,
       groups.name,
       groups.owner_id,
       groups.max_event_id,
       members.entry_date,
       members.member_status
  FROM groups
  JOIN members ON groups.group_id = members.group_id
 WHERE members.user_id = :user_id
       AND members.member_status < 1
 ORDER BY name ASC
 LIMIT :limit
OFFSET :offset;
""",
                params={
                    "user_id": self.user_id,
                    "limit": 12,
                    "offset": 12 * page,
                },
            )
        except DataBaseError as e:
            raise ApiError(e)

        return [TelegramGroup(*group) for group in groups]

    def get_groups_where_i_moderator(self, page: int = 1) -> list[TelegramGroup]:
        if self.group_id:
            raise Forbidden

        page -= 1
        try:
            groups = db.execute(
                """
SELECT groups.group_id,
       groups.chat_id,
       groups.name,
       groups.owner_id,
       groups.max_event_id,
       members.entry_date,
       members.member_status
  FROM groups
  JOIN members ON groups.group_id = members.group_id
 WHERE members.user_id = :user_id
       AND members.member_status >= 1
 ORDER BY name ASC
 LIMIT :limit
OFFSET :offset;
""",
                params={
                    "user_id": self.user_id,
                    "limit": 12,
                    "offset": 12 * page,
                },
            )
        except DataBaseError as e:
            raise ApiError(e)

        return [TelegramGroup(*group) for group in groups]

    def get_groups_where_i_admin(self, page: int = 1) -> list[TelegramGroup]:
        if self.group_id:
            raise Forbidden

        page -= 1
        try:
            groups = db.execute(
                """
SELECT groups.group_id,
       groups.chat_id,
       groups.name,
       groups.owner_id,
       groups.max_event_id,
       members.entry_date,
       members.member_status
  FROM groups
  JOIN members ON groups.group_id = members.group_id
 WHERE members.user_id = :user_id
       AND members.member_status >= 1
 ORDER BY name ASC
 LIMIT :limit
OFFSET :offset;
""",
                params={
                    "user_id": self.user_id,
                    "limit": 12,
                    "offset": 12 * page,
                },
            )
        except DataBaseError as e:
            raise ApiError(e)

        return [TelegramGroup(*group) for group in groups]


def get_telegram_account_from_password(
    username: str, password: str, group_chat_id: str | None = None
) -> TelegramAccount:
    try:
        user = db.execute(
            """
SELECT chat_id,
       password
  FROM users
 WHERE username = :username;
""",
            params={"username": username},
        )[0]

        if not verify_password(user[1], password):
            raise IndexError
    except DataBaseError as e:
        raise ApiError(e)
    except IndexError:
        raise UserNotFound

    return TelegramAccount(user[0], group_chat_id)


def set_user_telegram_chat_id(
    account: Account | TelegramAccount, chat_id: int | None = None
) -> None:
    try:
        db.execute(
            """
UPDATE users
   SET chat_id = :chat_id
 WHERE user_id = :user_id;
""",
            params={
                "chat_id": chat_id,
                "user_id": account.user_id,
            },
            commit=True,
        )
    except DataBaseError as e:
        raise ApiError(e)


@cached(LFUCache(maxsize=1000), key=lambda m: m.chat.id)
def add_chat_cached(message: Message) -> None:
    try:
        db.execute(
            """
INSERT OR IGNORE INTO chats (
    id,
    type,
    title,
    username,
    first_name,
    last_name,
    bio,
    is_forum,
    json
)
VALUES (
    :id,
    :type,
    :title,
    :username,
    :first_name,
    :last_name,
    :bio,
    :is_forum,
    :json
);
""",
            {
                "id": message.chat.id,
                "type": message.chat.type,
                "title": message.chat.title,
                "username": message.chat.username,
                "first_name": message.chat.first_name,
                "last_name": message.chat.last_name,
                "bio": message.chat.bio,
                "is_forum": bool(message.chat.is_forum),
                "json": json.dumps(
                    {k: v for k, v in literal_eval(str(message.chat)).items() if v},
                    ensure_ascii=False,
                ),
            },
            commit=True,
        )
    except DataBaseError as e:
        logger.exception(e)
