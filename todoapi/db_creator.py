from todoapi.types import db


def create_tables() -> None:
    with db.connection(), db.cursor(), open("todoapi/db_create.sql") as file:
        db.execute(file.read(), commit=True, script=True)
