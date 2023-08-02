import logging

from telebot import TeleBot
from telebot.apihelper import ApiTelegramException
from telebot.types import BotCommandScopeChat

import config
from lang import get_translate


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
                "database": config.DATABASE_PATH,
                "log_file": config.LOG_FILE,
                "notifications": config.NOTIFICATIONS,
                "__version__": config.__version__,
            }
        )

        keylist = {
            "can_join_groups": "True",
            "can_read_all_group_messages": "True",
            "supports_inline_queries": "False",
        }

        for k, v in keylist.items():
            if v != str(bot_dict.get(k)):
                raise AttributeError(
                    f"{k}\n"
                    f"Should be {keylist[k]}\n"
                    f"Actually is {bot_dict[k]}\n\n"
                    f"{config.bot_settings}"
                )

        max_len_left = max(len(k) for k in bot_dict.keys())
        max_len_right = max(len(str(v)) for v in bot_dict.values())
        max_len = max_len_left + max_len_right + 5

        logging.info(
            "\n"
            + f"+{'-' * max_len}+\n"
            + "".join(
                f"| {k: >{max_len_left}} = {str(v): <{max_len_right}} |\n"
                for k, v in bot_dict.items()
            )
            + f"+{'-' * max_len}+"
        )

    def set_commands(self, chat_id: int, user_status: int, lang: str) -> bool:
        """
        Ставит список команд для пользователя chat_id
        """
        # if is_admin_id(chat_id) and user_status != -1:
        #     user_status = 2

        target = f"{user_status}_command_list"

        try:
            return self.set_my_commands(
                commands=get_translate(target, lang),
                scope=BotCommandScopeChat(chat_id),
            )
        except (ApiTelegramException, KeyError) as e:
            logging.info(
                f'[bot.py -> set_commands -> "|"] (ApiTelegramException, KeyError) "{e}"'
            )
            return False


bot = Bot(config.BOT_TOKEN)
