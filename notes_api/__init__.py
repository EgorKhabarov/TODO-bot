from pathlib import Path

from notes_api.db_creator import create_tables


Path("data").mkdir(exist_ok=True)
create_tables()
