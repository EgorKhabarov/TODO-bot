import logging

logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    level=logging.INFO,
)
console = logging.StreamHandler()
# console.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
)
console.setFormatter(formatter)
logging.getLogger("").addHandler(console)
