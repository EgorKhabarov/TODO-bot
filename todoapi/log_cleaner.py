from pathlib import Path
from datetime import datetime

from todoapi.config import LOG_FILE as input_file_path  # noqa


removal_lines_start = ("[", "|", "+")
removal_lines_in = (
    "HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded with url:",
    "HTTPSConnectionPool(host='api.telegram.org', port=443): Read timed out.",
)
removal_lines_end = (
    "ERROR Exception traceback:\n",
    "make sure that only one bot instance is running\n",
    "Error code: 502. Description: Bad Gateway\n",
)


def filter_function(test_line: str) -> bool:
    if any(test_line.endswith(rl) for rl in removal_lines_end):
        return False

    if any((rl in test_line) for rl in removal_lines_in):
        return False

    return any(test_line.startswith(rl) for rl in removal_lines_start)


def clear_logs():
    log_folder, utc_time = Path(input_file_path).parent, datetime.utcnow()
    output_file_path = rf"{log_folder}\old_logs\{utc_time:%Y.%m.%d-%H.%M.%S}.log"
    output_errors_file_path = rf"{output_file_path.removesuffix('.log')}_errors.log"
    Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)

    with (
        open(input_file_path, "r") as input_file,
        open(output_file_path, "w") as output_file,
        open(output_errors_file_path, "w") as output_error_file,
    ):
        for line in input_file:
            (output_file if filter_function(line) else output_error_file).write(line)

    with open(input_file_path, "w", encoding="UTF-8") as file:
        file.write("")
