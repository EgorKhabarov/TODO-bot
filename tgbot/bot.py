import logging

from telebot import TeleBot
from telebot.types import BotCommandScopeChat
from telebot.apihelper import ApiTelegramException

import todoapi.config
from tgbot import config
from tgbot.request import request
from tgbot.lang import get_translate
from todoapi.utils import is_admin_id


bot = TeleBot(config.BOT_TOKEN)

bot.me = bot.get_me()
bot.id = bot.me.id
bot.username = bot.me.username

bot.parse_mode = "html"
bot.disable_web_page_preview = True
bot.protect_content = False


def bot_log_info():
    bot_dict = bot.me.to_dict()
    bot_dict.update(
        {
            "database": config.DATABASE_PATH,
            "log_file": todoapi.config.LOG_FILE,
            "notifications": config.NOTIFICATIONS,
            "__version__": config.__version__,
        }
    )

    key_list = {
        "can_join_groups": "True",
        "can_read_all_group_messages": "True",
        "supports_inline_queries": "False",
    }

    for k, v in key_list.items():
        if v != str(bot_dict.get(k)):
            raise AttributeError(
                f"{k}\n"
                f"Should be {key_list[k]}\n"
                f"Actually is {bot_dict[k]}\n\n"
                f"{config.bot_settings.strip()}"
            )

    max_len_left = max(len(k) for k in bot_dict.keys())
    max_len_right = max(len(str(v)) for v in bot_dict.values())
    max_len = max_len_left + max_len_right + 5

    return (
        "\n"
        + f"+{'-' * max_len}+\n"
        + "".join(
            f"| {k: >{max_len_left}} = {str(v): <{max_len_right}} |\n"
            for k, v in bot_dict.items()
        )
        + f"+{'-' * max_len}+"
    )


def set_bot_commands(
    chat_id: int | None = None, user_status: int | None = None, lang: str | None = None
) -> bool:
    """
    Ставит список команд для пользователя chat_id
    """
    if not chat_id:
        chat_id = request.chat_id

    if not user_status:
        user_status = request.user.settings.user_status

    if not lang:
        lang = request.user.settings.lang

    if is_admin_id(chat_id) and user_status != -1:
        user_status = 2

    target = f"buttons.commands.{user_status}"

    try:
        return bot.set_my_commands(
            get_translate(target, lang), BotCommandScopeChat(chat_id)
        )
    except (ApiTelegramException, KeyError) as e:
        logging.info(f'set_bot_commands (ApiTelegramException, KeyError) "{e}"')
        return False
