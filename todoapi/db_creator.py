from todoapi.types import db


def create_tables() -> None:
    with db.connect(), open("todoapi/db_create.sql") as file:
        db.execute(file.read(), commit=True, script=True)
