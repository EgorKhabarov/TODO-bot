import logging

logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
)
console = logging.StreamHandler()
# console.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s", datefmt="[%Y-%m-%d %H:%M:%S]"
)
console.setFormatter(formatter)
logging.getLogger("").addHandler(console)
