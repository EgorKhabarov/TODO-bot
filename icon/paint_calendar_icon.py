from PIL import Image, ImageDraw, ImageFont

ICON_SIZE: int = 778
ICON_NAME: str = "calendar_icon"
FONT_PATH = "../fonts/roboto-black.ttf"
# http://allfont.net/cache/fonts/roboto-black_9d5456046bfe9a00b0b9325cda8c55f3.ttf
ICON_VERSION: str = ""


def image_generator(
    icon_size: int, font_path: str, icon_version: str | None = None
) -> Image:
    _image = Image.new("RGB", (icon_size, icon_size), "white")
    draw = ImageDraw.Draw(_image)

    color_gray = (61, 61, 63)
    color_white = (255, 255, 255)
    color_red = (252, 31, 38)

    # Basic gray calendar outline
    draw.rounded_rectangle(
        (170, 179, 604, 604), 80, fill=color_white, outline=color_gray, width=28
    )

    # Top of the calendar (red)
    draw.rounded_rectangle((199, 207, 576, 295), 80, fill=color_red)
    draw.rectangle((198, 252, 576, 295), fill=color_red, outline=color_red)

    # Vertical gray stripes (staples)
    draw.rounded_rectangle((295, 133, 320, 258), 80, fill=color_gray)
    draw.rounded_rectangle((446, 133, 471, 258), 80, fill=color_gray)

    # Gray, horizontal line partition
    draw.rectangle((198, 296, 576, 322), fill=color_gray, outline=color_gray)

    # Black squares of days
    for y in (351, 406, 458, 512):
        for x in (239, 306, 373, 440, 506):
            # First square at the top left
            if x == 239 and y == 351:
                continue
            # Two squares bottom right
            if x in (440, 506) and y == 512:
                continue
            # Don't draw a box for the checkbox
            if x == 440 and y == 458:
                continue

            draw.rectangle((x, y, x + 30, y + 30), fill=color_gray)

    # Red tick
    draw.line((433, 466, 458, 491), fill=color_red, width=19)
    draw.line((447, 490, 484, 453), fill=color_red, width=20)

    if icon_version:
        font = ImageFont.truetype(font_path, 350)
        draw.text((510, 300), ICON_VERSION, fill=color_gray, font=font)
        draw.text((490, 280), ICON_VERSION, fill=color_red, font=font)

    return _image


if __name__ == "__main__":
    image = image_generator(ICON_SIZE, FONT_PATH, ICON_VERSION)
    image.save(f"{ICON_NAME}.png", "png")
