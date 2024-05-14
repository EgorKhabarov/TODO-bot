import logging
from pathlib import Path
from config import LOG_FILE_PATH

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "{asctime:s} {filename:s}:{lineno:d} {levelname:s} {message:s}",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    style="{",
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

Path("logs").mkdir(exist_ok=True)
file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="UTF-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
