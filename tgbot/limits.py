from io import BytesIO

from PIL.ImageDraw import Draw
from PIL import Image, ImageFont

from tgbot.request import request
from tgbot.lang import get_translate
from tgbot.time_utils import now_time
from todoapi.types import Limit, event_limits


def _semicircle(title: str, val: int, y: int) -> Image:
    colors = {
        "g": "#00cc00",
        "bg g": "#95ff95",
        "y": "#fcf11d",
        "bg y": "#fef998",
        "o": "#ff9900",
        "bg o": "#ffcc80",
        "r": "#ff4400",
        "bg r": "#ffb093",
    }

    if not y:
        y = float("inf")
    percent = int((val / y) * 100)
    if str(y) == "inf":
        y = "ꝏ"
    text = f"{val}/{y}"
    percent_str = f"{percent}%"

    if percent < 25:
        bg_color, color = colors["bg g"], colors["g"]
    elif 24 < percent < 51:
        bg_color, color = colors["bg y"], colors["y"]
    elif 50 < percent < 76:
        bg_color, color = colors["bg o"], colors["o"]
    else:
        bg_color, color = colors["bg r"], colors["r"]

    font = ImageFont.truetype("fonts/arial.ttf", 30)
    image = Image.new("RGB", (291, 202), "#F0F0F0")
    draw = Draw(image)

    # Название дуги
    text_width, text_height = [
        wh // 2 for wh in draw.textbbox((0, 0), text=title, font=font)[2:]
    ]
    draw.text((145 - text_width, 15 - text_height), title, fill="black", font=font)

    # Рисуем дугу
    draw.pieslice(((45, 42), (245, 242)), 180, 360, fill=bg_color)  # "#778795"
    draw.pieslice(
        ((45, 42), (245, 242)),
        180,
        ((180 + (percent / 100) * 180) if percent < 101 else 360),
        fill=color,
    )  # "#303b44"
    draw.pieslice(((95, 50 + 42), (195, 192)), 180, 360, fill="#F0F0F0")

    text_width, text_height = [
        wh // 2 for wh in draw.textbbox((0, 0), text=text, font=font)[2:]
    ]
    draw.text((145 - text_width, 172 - text_height), text, fill="black", font=font)

    text_width, text_height = [
        wh // 2 for wh in draw.textbbox((0, 0), text=percent_str, font=font)[2:]
    ]
    draw.text(
        (145 - text_width, 119 - text_height), percent_str, fill="black", font=font
    )

    return image


def create_image(year=None, month=None, day=None, text="Account") -> BytesIO:
    user_info = event_limits[request.user.user_status]
    now_date = now_time()
    if not year:
        year = now_date.year
    if not month:
        month = now_date.month
    if not day:
        day = now_date.day

    image = Image.new("RGB", (1500, 1000), "#F0F0F0")
    draw = Draw(image)

    font = ImageFont.truetype("fonts/arial.ttf", 100)
    text_width, text_height = font.getbbox(text)[2:]
    draw.text(
        (375 * 2 - text_width // 2, 60 - text_height // 2),
        text,
        fill="black",
        font=font,
    )

    date = f"{day:0>2}.{month:0>2}.{year}"
    limit = Limit(request.user.user_id, request.user.user_status, date)
    (
        limit_event_day,
        limit_symbol_day,
        limit_event_month,
        limit_symbol_month,
        limit_event_year,
        limit_symbol_year,
        limit_event_all,
        limit_symbol_all,
    ) = (
        limit.limit_event_day,
        limit.limit_symbol_day,
        limit.limit_event_month,
        limit.limit_symbol_month,
        limit.limit_event_year,
        limit.limit_symbol_year,
        limit.limit_event_all,
        limit.limit_symbol_all,
    )
    (
        event_day,
        symbol_day,
        event_month,
        symbol_month,
        event_year,
        symbol_year,
        event_all,
        symbol_all,
    ) = get_translate("arrays.account")

    if day:
        image.paste(
            _semicircle(event_day, limit_event_day, user_info["max_event_day"]),
            (100, 140),
        )
        image.paste(
            _semicircle(symbol_day, limit_symbol_day, user_info["max_symbol_day"]),
            (390, 140),
        )
    if month:
        image.paste(
            _semicircle(event_month, limit_event_month, user_info["max_event_month"]),
            (100, 345),
        )
        image.paste(
            _semicircle(
                symbol_month, limit_symbol_month, user_info["max_symbol_month"]
            ),
            (390, 345),
        )
    if year:
        image.paste(
            _semicircle(event_year, limit_event_year, user_info["max_event_year"]),
            (100, 562),
        )
        image.paste(
            _semicircle(symbol_year, limit_symbol_year, user_info["max_symbol_year"]),
            (390, 562),
        )
    # all
    image.paste(
        _semicircle(event_all, limit_event_all, user_info["max_event_all"]), (100, 766)
    )
    image.paste(
        _semicircle(symbol_all, limit_symbol_all, user_info["max_symbol_all"]),
        (390, 766),
    )

    draw.rectangle(((800, 139), (1350, 956)), outline="#000000", width=5)

    # text = "..."
    # font = ImageFont.truetype("fonts/arial.ttf", 30)
    # text_width, text_height = [
    #     wh // 2 for wh in draw.textbbox((0, 0), text=text, font=font)[2:]
    # ]
    # draw.text((1073 - text_width, 551 - text_height), text, fill="black", font=font)

    # Временно обрезаем всё лишнее.
    image = image.crop((94, 114, 694, 981))
    # year_calendar = [monthcalendar(year, m) for m in range(1, 13)]

    buffer = BytesIO()
    image.save(buffer, format="png")
    buffer.seek(0)
    return buffer
