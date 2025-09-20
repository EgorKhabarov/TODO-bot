from pathlib import Path

import requests
from PIL import Image


ICON_SIZE: int = 778
link = "https://web.telegram.org/a/img-apple-64/{emoji_name}.png"
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 Edg/113.0.1774.42"
    )
}
emoji_dir = Path("emojis")
emoji_dir.mkdir(exist_ok=True)


def draw_emoji(image: Image.Image, emoji: str):
    emoji_image = Image.open(get_emoji(emoji)).convert("RGBA").resize((270, 270))
    mask = emoji_image.split()[3]
    image.paste(emoji_image, (ICON_SIZE // 2, ICON_SIZE // 2), mask)


def get_emoji(emoji: str) -> Path:
    emoji_name = get_emoji_name(emoji)
    emoji_path = emoji_dir.joinpath(f"{emoji_name}.png")

    if emoji_path.exists():
        return emoji_path

    download_emoji(emoji_name, emoji_path)
    return emoji_path


def get_emoji_name(emoji: str) -> str:
    return "-".join(str(hex(ord(c)))[2:] for c in emoji)


def download_emoji(emoji_name: str, emoji_path: Path) -> None:
    print(f"Download emoji {emoji_name} {emoji_path}")
    with open(emoji_path, "wb") as file:
        content = requests.get(
            link.format(emoji_name=emoji_name),
            headers=headers,
        ).content
        file.write(content)
