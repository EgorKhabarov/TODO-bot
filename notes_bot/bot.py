# noinspection PyPackageRequirements
from telebot import TeleBot
from table2string import Table

import config
from telegram_utils.command_parser import command_regex


if config.TELEGRAM_WEBHOOK:
    threaded, num_threads = False, 6
else:
    threaded, num_threads = True, 2

bot = TeleBot(config.BOT_TOKEN, threaded=threaded, num_threads=num_threads)

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
    del bot_dict["last_name"]
    del bot_dict["is_premium"]
    del bot_dict["language_code"]
    del bot_dict["added_to_attachment_menu"]
    del bot_dict["can_connect_to_business"]
    bot_dict.update(
        {
            "database": config.SQLALCHEMY_DATABASE_URI,
            "log_file": config.LOG_FILE_PATH,
            "notifications": config.BOT_NOTIFICATIONS,
            **({"webhook": True} if bot_webhook_info.url else {}),
            "__version__": f"{config.__version__}{config.string_branch}",
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

    return "\n{}".format(
        Table([(k, v) for k, v in bot_dict.items()]).stringify(
            h_align=(">", "<"),
            sep=False,
        )
    )
