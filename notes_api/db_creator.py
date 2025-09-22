from notes_api.types import db


def create_tables() -> None:
    with db.connect(), open("notes_api/db_create.sql") as file:
        db.execute(file.read(), commit=True, script=True)
