import logging
from config import LOG_FILE_PATH

# Создание объекта логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Создание обработчика для записи логов в файл
file_handler = logging.FileHandler(LOG_FILE_PATH)
file_handler.setLevel(logging.DEBUG)

# Создание обработчика для вывода логов в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Определение форматирования для логов
formatter = logging.Formatter(
    "%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Добавление обработчиков к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)
