# noinspection PyPackageRequirements
from telebot import TeleBot

import config
from telegram_utils.command_parser import command_regex


bot = TeleBot(config.BOT_TOKEN)

bot.parse_mode = "html"
bot.disable_web_page_preview = True
bot.protect_content = False
bot_webhook_info = bot.get_webhook_info()
bot_settings = """
Bot Settings => Group Privacy => disabled
Bot Settings => Inline Mode   => disabled
"""
command_regex.set_username(bot.user.username)


def bot_log_info():
    bot_dict = bot.user.to_dict()
    bot_dict.update(
        {
            "database": config.DATABASE_PATH,
            "log_file": config.LOG_FILE_PATH,
            "notifications": config.BOT_NOTIFICATIONS,
            **({"webhook": True} if bot_webhook_info.url else {}),
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
                f"{bot_settings.strip()}"
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
