from telebot import TeleBot
from telebot.apihelper import ApiTelegramException
from telebot.types import BotCommandScopeChat

import config
import logging

from lang import get_translate
from user_settings import UserSettings
from utils import is_admin_id


class Bot(TeleBot):
    def __init__(self, token: str):
        super().__init__(token)
        self._me = self.get_me()
        self.id = self._me.id
        self.username = self._me.username

        self.parse_mode = "html"
        self.disable_web_page_preview = True
        self.protect_content = False

    def log_info(self):
        bot_dict = self._me.to_dict()
        bot_dict.update(
            {
                "database": config.database_path,
                "log_file": config.log_file,
                "notifications": config.notifications,
                "__version__": config.__version__,
            }
        )

        def check(key, val) -> str:
            """Подсветит не правильные настройки красным цветом"""
            keylist = {
                "can_join_groups": "True",
                "can_read_all_group_messages": "True",
                "supports_inline_queries": "False",
            }
            indent = " " * 22
            return (
                (
                    f"\033[32m{val!s:<5}\033[0m{indent}"
                    if keylist[key] == str(val)
                    else f"\033[31m{val!s:<5}\033[0m{indent}"
                )
                if key in keylist
                else f"{val}"
            )

        logging.info(
            "\n"
            + f"+{'-' * 59}+\n"
            + "".join(
                f"| {k: >27} = {check(k, v): <27} |\n" for k, v in bot_dict.items()
            )
            + f"+{'-' * 59}+"
        )

    def set_commands(self, settings: UserSettings) -> bool:
        """
        Ставит список команд для пользователя chat_id
        """
        if is_admin_id(settings.user_id):
            settings.user_status = 2

        target = f"{settings.user_status}_command_list"

        try:
            return self.set_my_commands(
                commands=get_translate(target, settings.lang),
                scope=BotCommandScopeChat(settings.user_id),
            )
        except (ApiTelegramException, KeyError) as e:
            logging.info(
                f'[bot.py -> set_commands -> "|"] (ApiTelegramException, KeyError) "{e}"'
            )
            return False


bot = Bot(config.bot_token)
