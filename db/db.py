from sqlite3 import connect

import config


def SQL(
    query: str, params: tuple = (), commit: bool = False, column_names: bool = False
) -> list[tuple[int | str | bytes, ...], ...]:
    """
    Выполняет SQL запрос
    Пробовал через with, но оно не закрывало файл

    :param query: Запрос
    :param params: Параметры запроса (необязательно)
    :param commit: Нужно ли сохранить изменения? (необязательно, по умолчанию False)
    :param column_names: Названия столбцов вставить в результат
    :return: Результат запроса
    """
    connection = connect(config.DATABASE_PATH)
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        if commit:
            connection.commit()
        result = cursor.fetchall()
        if column_names:
            description = [column[0] for column in cursor.description]
            result = [description] + result
    finally:
        # cursor.close()
        connection.close()
    return result


class SqlQueries:
    @staticmethod
    def get_limits(user_id: int, date: str, removal_time_equals_0: int = False) -> str:
        """
        if isdel_equals_0: "AND removal_time=0"
        else: ""
        """
        removal_time = "AND removal_time=0" if removal_time_equals_0 else ""

        return f"""
SELECT 
    (
        SELECT IFNULL(COUNT(*), 0) FROM events
        WHERE user_id={user_id} {removal_time} AND date='{date}'
    ) AS count_today,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) FROM events
        WHERE user_id={user_id} {removal_time} AND date='{date}'
    ) AS sum_length_today,
    (
        SELECT IFNULL(COUNT(*), 0) FROM events
        WHERE user_id={user_id} {removal_time} AND SUBSTR(date, 4, 7)='{date[3:]}'
    ) AS count_month,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) FROM events
        WHERE user_id={user_id} {removal_time} AND SUBSTR(date, 4, 7)='{date[3:]}'
    ) AS sum_length_month,
    (
        SELECT IFNULL(COUNT(*), 0) FROM events
        WHERE user_id={user_id} {removal_time} AND SUBSTR(date, 7, 4)='{date[6:]}'
    ) AS count_year,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) FROM events
        WHERE user_id={user_id} {removal_time} AND SUBSTR(date, 7, 4)='{date[6:]}'
    ) AS sum_length_year,
    (
        SELECT IFNULL(COUNT(*), 0) FROM events
        WHERE user_id={user_id} {removal_time}
    ) AS total_count,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) FROM events
        WHERE user_id={user_id} {removal_time}
    ) AS total_length;
"""
