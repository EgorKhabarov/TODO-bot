from PIL import Image, ImageDraw

ICON_SIZE: int = 778
ICON_NAME: str = "minimalistic_notepad_icon"

COLOR_BACKGROUND = (86, 176, 239)
COLOR_NOTEBOOK = (255, 255, 255)

COLOR_LOCK = (240, 168, 26)
COLOR_LOCK_CYLINDER = (192, 120, 4)
COLOR_LOCK_SHACKLE = (165, 165, 165)


def image_generator(icon_size: int) -> Image:
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


def draw_lock(image: Image):
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


if __name__ == "__main__":
    img = image_generator(ICON_SIZE)
    # draw_lock(img)
    img.save(f"{ICON_NAME}.png", "png")
