import re
from urllib.parse import urlparse

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

    def prepare_url(url) -> str:
        url = url.removeprefix("http://").removeprefix("https://")
        url = url.strip().strip("/").strip("\\")
        return f"https://{url}"

    def replace_url(m: re.Match) -> str:
        url = prepare_url(m.group(1))
        pre_text = m.group(2).strip()

        condition = pre_text != urlparse(m.group(1)).netloc
        text = f" ({pre_text})" if condition else ""

        return f"{url}{text}{m.group(3)}"

    html_text = re.sub(r"<a href=\"(.+?)\">(.+?)(\n*?)</a>", replace_url, html_text)
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


def to_valid_id(x_id: int | str) -> int:
    """
    Вернёт валидный id.
    Если ошибка, то возвращает 0.
    """
    if isinstance(x_id, str) and x_id.isdigit():
        x_id = int(x_id)

    return x_id if 0 < x_id else 0


def is_valid_year(year: int) -> bool:
    """
    Является ли год валидным (находится в диапазоне от 1900 до 3000)
    """
    return 1900 <= year <= 3000
