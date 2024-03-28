from io import BytesIO
from urllib.parse import urlencode

# noinspection PyPackageRequirements
from telebot.formatting import hide_link
from PIL.ImageDraw import Draw
from PIL import Image, ImageFont

from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.time_utils import now_time
from todoapi.types import event_limits
from config import LIMIT_IMAGE_GENERATOR_URL


noimage = "https://upload.wikimedia.org/wikipedia/commons/1/14/No_Image_Available.jpg"

colors = {
    "g": "#00cc00",
    "y": "#fcf11d",
    "o": "#ff9900",
    "r": "#ff4400",
    "bg g": "#95ff95",
    "bg y": "#fef998",
    "bg o": "#ffcc80",
    "bg r": "#ffb093",
    "0": "#F0F0F0",
    "1": "#202020",
}

def get_limit_link(date: str = "now") -> str:
    if not date or date == "now":
        date = f"{now_time():%d.%m.%Y}"

    limits = zip(
        request.entity.limit.get_event_limits(date),
        tuple(event_limits[request.entity.user.user_status].values())
    )
    params = {
        # "date": date,
        "theme": request.entity.settings.theme,
        "lang": request.entity.settings.lang,
        "data": "n".join(f"{x}s{y}" for x, y in limits),
    }
    if LIMIT_IMAGE_GENERATOR_URL:
        return (
            date
            + hide_link(f"{LIMIT_IMAGE_GENERATOR_URL}?{urlencode(params, doseq=True)}")
            + hide_link(noimage)
        )
    else:
        f, b = "▓", "░"
        lst = []
        for text, x, y in zip(
            get_translate("arrays.account"),
            request.entity.limit.get_event_limits(date),
            tuple(event_limits[request.entity.user.user_status].values()),
        ):
            percent = int((x / y) * 100)
            lst.append(f"<b>{text}</b>\n<u>{x}/{y}</u> [{f*(percent//10)}{b*(10-(percent//10))}] ({percent}%)")
        return f"{date}\n\n" + "\n\n".join(lst)

def _semicircle(title: str, x: int, y: int, theme: str):
    text = f"{x}/{y}"
    percent = int((x / y) * 100)
    percent_str = f"{percent}%"
    background_color = colors[theme]
    invert_background_color = colors["0" if theme == "1" else "1"]

    if percent < 25:
        bg_color, color = colors["bg g"], colors["g"]
    elif 24 < percent < 51:
        bg_color, color = colors["bg y"], colors["y"]
    elif 50 < percent < 76:
        bg_color, color = colors["bg o"], colors["o"]
    else:
        bg_color, color = colors["bg r"], colors["r"]

    font = ImageFont.truetype("fonts/arial.ttf", 30)
    image = Image.new("RGB", (291, 202), background_color)
    draw = Draw(image)

    # Название дуги
    text_width, text_height = [
        wh // 2 for wh in draw.textbbox((0, 0), text=title, font=font)[2:]
    ]
    draw.text((145 - text_width, 15 - text_height), title, fill=invert_background_color, font=font)

    # Рисуем дугу
    draw.pieslice(((45, 42), (245, 242)), 180, 360, fill=bg_color)  # "#778795"
    draw.pieslice(
        ((45, 42), (245, 242)),
        180,
        ((180 + (percent / 100) * 180) if percent < 101 else 360),
        fill=color,
    )  # "#303b44"
    draw.pieslice(((95, 50 + 42), (195, 192)), 180, 360, fill=background_color)

    text_width, text_height = [
        wh // 2 for wh in draw.textbbox((0, 0), text=text, font=font)[2:]
    ]
    draw.text((145 - text_width, 172 - text_height), text, fill=invert_background_color, font=font)

    text_width, text_height = [
        wh // 2 for wh in draw.textbbox((0, 0), text=percent_str, font=font)[2:]
    ]
    draw.text(
        (145 - text_width, 119 - text_height), percent_str, fill=invert_background_color, font=font
    )

    return image

def create_image_from_link(lang: str, lst: list[list[int]], theme: str) -> Image:
    background_color = colors[theme]
    image = Image.new("RGB", (1500, 1000), background_color)
    for t, (x, y), xy in zip(
        get_translate("arrays.account", lang),
        lst,
        ((100, 140), (390, 140), (100, 345), (390, 345), (100, 562), (390, 562), (100, 766), (390, 766))
    ):
        image.paste(_semicircle(t, x, y, theme), xy)

    image = image.crop((94, 114, 694, 981))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
