from PIL import Image, ImageDraw

ICON_SIZE: int = 778
ICON_NAME: str = "minimalistic_notepad_icon"


def image_generator(icon_size: int) -> Image:
    color_background = (86, 176, 239)
    color_notebook = (255, 255, 255)

    _image = Image.new("RGB", (icon_size, icon_size), color_background)
    draw = ImageDraw.Draw(_image)

    y = 20
    draw.rounded_rectangle((195, 195 + y, 583, 583 + y), 57, fill=color_notebook)
    draw.ellipse(((310, 137 + y), (467, 294 + y)), fill=color_notebook)
    draw.ellipse(((353, 180 + y), (424, 251 + y)), fill=color_background)
    draw.rounded_rectangle((281, 303 + y, 496, 345 + y), 22, fill=color_background)
    draw.rounded_rectangle((281, 389 + y, 496, 431 + y), 22, fill=color_background)
    draw.rounded_rectangle((281, 475 + y, 496, 518 + y), 22, fill=color_background)

    return _image


if __name__ == "__main__":
    image = image_generator(ICON_SIZE)
    image.save(f"{ICON_NAME}.png", "png")
