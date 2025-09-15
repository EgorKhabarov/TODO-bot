from PIL import Image, ImageDraw, ImageFont

ICON_SIZE: int = 778
ICON_NAME: str = "notepad_icon"
FONT_PATH = "../fonts/roboto-black.ttf"
# http://allfont.net/cache/fonts/roboto-black_9d5456046bfe9a00b0b9325cda8c55f3.ttf
ICON_VERSION: str = ""


def image_generator(
    icon_size: int, font_path: str, icon_version: str | None = None
) -> Image:
    main_color_type = "b"
    match main_color_type:
        case "g":
            color_background = "#8CC63F"
            color_dark_background = "#82B736"
        case "b":
            color_background = (86, 176, 239)
            color_dark_background = "#5096CE"
        case _:
            color_background = "#EFC849"
            color_dark_background = "#D7B343"

    color_notebook = (255, 255, 255)
    color_paper_clips = "#627A8B"
    color_notes = "#D5D6DB"

    _image = Image.new("RGB", (icon_size, icon_size), color_background)
    draw = ImageDraw.Draw(_image)

    notebook_offset_x = 209  # 250
    notebook_offset_y = 159

    def draw_notebook(offset_x: int, offset_y: int):
        # Notepad shadows
        for n in range(9):
            n *= 36
            draw.polygon(
                (
                    (offset_x + 40 + n, offset_y),
                    (offset_x + 63 + n, offset_y + 23),
                    (offset_x + 63 + n, offset_y + 43),
                    (offset_x + 40 + n, offset_y + 51),
                ),
                fill=color_dark_background,
            )

        # Big shadow
        draw.polygon(
            (
                (offset_x + 330, offset_y + 1),
                (778, offset_y + 240),
                (778, 778),
                (offset_x + 171, 778),
                (offset_x + 1, offset_y + 439),
            ),
            fill=color_dark_background,
        )

        # Sheet
        draw.rounded_rectangle(
            (offset_x, offset_y + 41, offset_x + 358, offset_y + 444),
            10,
            fill=color_notebook,
        )

        # Paper clips
        for n in range(9):
            n *= 36
            draw.rounded_rectangle(
                (offset_x + 28 + n, offset_y, offset_x + 43 + n, offset_y + 70),
                4,
                fill=color_paper_clips,
            )

        # Posts
        for n in range(5):
            n *= 55
            draw.rounded_rectangle(
                (offset_x + 27, offset_y + 116 + n, offset_x + 330, offset_y + 146 + n),
                4,
                fill=color_notes,
            )

    draw_notebook(notebook_offset_x, notebook_offset_y)

    if icon_version:
        font = ImageFont.truetype(font_path, 220)
        color_gray = (61, 61, 63)
        color_red = (252, 31, 38)
        center_x = 388
        x = center_x - font.getbbox(icon_version)[2] // 2
        draw.text((x + 7, 273 + 7), icon_version, fill=color_gray, font=font)
        draw.text((x, 273), icon_version, fill=color_red, font=font)

    return _image


if __name__ == "__main__":
    image = image_generator(ICON_SIZE, FONT_PATH, ICON_VERSION)
    image.save(f"{ICON_NAME}.png", "png")
