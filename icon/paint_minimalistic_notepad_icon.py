from PIL import Image, ImageDraw


ICON_SIZE: int = 778
ICON_NAME: str = "minimalistic_notepad_icon"

COLOR_BACKGROUND = (86, 176, 239)
COLOR_NOTEBOOK = (255, 255, 255)

COLOR_LOCK = (240, 168, 26)
COLOR_LOCK_CYLINDER = (192, 120, 4)
COLOR_LOCK_SHACKLE = (165, 165, 165)

COLOR_CLOCK = (238, 125, 44)
COLOR_CLOCK_BACKGROUND = (255, 190, 113)
COLOR_CLOCK_HANDS = (151, 83, 0)
COLOR_CLOCK_HANDS_LDARK = (134, 73, 0)
COLOR_CLOCK_HANDS_DARK = (98, 54, 0)


def image_generator(icon_size: int) -> Image.Image:
    _image = Image.new("RGB", (icon_size, icon_size), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(_image)
    x, y = 195, 147

    draw.rounded_rectangle((x, 58 + y, 388 + x, 446 + y), 57, fill=COLOR_NOTEBOOK)
    draw.ellipse((115 + x, y, 272 + x, 157 + y), fill=COLOR_NOTEBOOK)
    draw.ellipse((158 + x, 43 + y, 229 + x, 114 + y), fill=COLOR_BACKGROUND)
    draw.rounded_rectangle(
        (86 + x, 166 + y, 301 + x, 208 + y), 22, fill=COLOR_BACKGROUND
    )
    draw.rounded_rectangle(
        (86 + x, 252 + y, 301 + x, 294 + y), 22, fill=COLOR_BACKGROUND
    )
    draw.rounded_rectangle(
        (86 + x, 338 + y, 301 + x, 381 + y), 22, fill=COLOR_BACKGROUND
    )

    return _image


def draw_lock(image: Image.Image):
    draw = ImageDraw.Draw(image)
    x, y = 450, 346

    draw.rounded_rectangle((x, 94 + y, 203 + x, 287 + y), 35, fill=COLOR_LOCK)

    draw.rounded_rectangle(
        (47 + x, y, 159 + x, 93 + y),
        50,
        fill=COLOR_LOCK_SHACKLE,
        corners=(True, True, False, False),
    )
    draw.rounded_rectangle(
        (79 + x, 34 + y, 127 + x, 93 + y),
        20,
        fill=COLOR_NOTEBOOK,
        corners=(True, True, False, False),
    )

    draw.ellipse((77 + x, 164 + y, 127 + x, 209 + y), fill=COLOR_LOCK_CYLINDER)
    draw.rounded_rectangle(
        (90 + x, 199 + y, 115 + x, 232 + y), 7, fill=COLOR_LOCK_CYLINDER
    )


def draw_clock(image: Image.Image):
    draw = ImageDraw.Draw(image)
    x, y = 450, 440

    draw.ellipse((x, y, 203 + x, 203 + y), fill=COLOR_CLOCK)
    draw.ellipse((20 + x, 20 + y, 183 + x, 183 + y), fill=COLOR_CLOCK_BACKGROUND)

    draw.rounded_rectangle(
        (96 + x, 43 + y, 106 + x, 107 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(
        (96 + x, 96 + y, 145 + x, 108 + y), 7, fill=COLOR_CLOCK_HANDS
    )

    draw.rounded_rectangle(  # 12
        (96 + x, 23 + y, 106 + x, 33 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 1
        (134 + x, 38 + y, 140 + x, 44 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 2
        (158 + x, 63 + y, 164 + x, 69 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 3
        (169 + x, 97 + y, 179 + x, 107 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 4
        (158 + x, 135 + y, 164 + x, 141 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 5
        (134 + x, 159 + y, 140 + x, 165 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 6
        (96 + x, 170 + y, 106 + x, 180 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 7
        (62 + x, 159 + y, 68 + x, 165 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 8
        (36 + x, 63 + y, 42 + x, 69 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 9
        (21 + x, 97 + y, 31 + x, 107 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 10
        (36 + x, 135 + y, 42 + x, 141 + y), 7, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(  # 11
        (62 + x, 38 + y, 68 + x, 44 + y), 7, fill=COLOR_CLOCK_HANDS
    )

    draw.rounded_rectangle(
        (93 - 1 + x, 94 - 1 + y, 109 + 1 + x, 110 + 1 + y),
        90,
        fill=COLOR_CLOCK_HANDS_LDARK,
    )
    draw.rounded_rectangle(
        (93 + x, 94 + y, 109 + x, 110 + y), 90, fill=COLOR_CLOCK_HANDS
    )
    draw.rounded_rectangle(
        (93 + 5 + x, 94 + 5 + y, 109 - 5 + x, 110 - 5 + y),
        90,
        fill=COLOR_CLOCK_HANDS_DARK,
    )


if __name__ == "__main__":
    img = image_generator(ICON_SIZE)
    # draw_lock(img)
    # draw_clock(img)
    # from icon.utils import get_emoji
    # draw_emoji(img, "📝")
    img.save(f"{ICON_NAME}.png", "PNG")
