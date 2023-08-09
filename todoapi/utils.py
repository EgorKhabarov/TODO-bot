import re
import todoapi.config as config


def html_to_markdown(html_text: str) -> str:
    for (k1, k2), v in {
        ("<i>", "</i>"): "__",
        ("<b>", "</b>"): "**",
        ("<s>", "</s>"): "~~",
        ("<pre>", "</pre>"): "```",
        ("<code>", "</code>"): "`",
        ('<span class="tg-spoiler">', "</span>"): "||",
    }.items():
        html_text = html_text.replace(k1, v).replace(k2, v)

    def prepare_url(url):
        url = url.removeprefix("http://").removeprefix("https://")
        url = url.strip().strip("/").strip("\\")
        return f"https://{url}"

    html_text = re.sub(
        r"<a href=\"(.+?)\">(\S+?)(\n??)</a>",
        lambda x: " {url} ({text}) {n}".format(  #
            url=prepare_url(x.group(1)),
            text=x.group(2).strip(),
            n=x.group(3),
        ),
        html_text,
    )
    return html_text


def to_html_escaping(text: str) -> str:
    return (
        text.replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&#39;")
        .replace('"', "&quot;")
    )


def remove_html_escaping(text: str) -> str:
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )


def sqlite_format_date(_column):
    """
    Столбец sql базы данных превращает из формата
    dd.mm.yyyy в yyyy.mm.dd в виде sql выражения

    :param _column: Столбец для превращения.
    :return: sql выражение
    """
    return f"""
SUBSTR({_column}, 7, 4) || '-' ||
SUBSTR({_column}, 4, 2) || '-' ||
SUBSTR({_column}, 1, 2)"""


def is_admin_id(chat_id: int) -> bool:
    """
    Проверка на админа
    Админом могут быть только люди, чьи id записаны в config.admin_id
    """
    return chat_id in config.admin_id


def is_premium_user(user) -> bool:
    """
    Является ли премиум пользователем
    """
    return user.settings.user_status >= 1 or is_admin_id(user.user_id)
