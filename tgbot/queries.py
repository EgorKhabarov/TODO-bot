from todoapi.utils import sqlite_format_date

queries = {
    # bot_messages.py
    "select recurring_events": f"""
-- Если находит, то добавлять кнопку повторяющихся событий
SELECT DISTINCT date
  FROM events
 WHERE (user_id IS :user_id AND group_id IS :group_id) AND
       removal_time IS NULL AND
       date != :date AND
(
    ( -- Каждый год
        (
            status LIKE '%🎉%'
            OR
            status LIKE '%🎊%'
            OR
            status LIKE '%📆%'
        )
        AND date LIKE :y_date
    )
    OR
    ( -- Каждый месяц
        status LIKE '%📅%'
        AND date LIKE :m_date
    )
    OR
    ( -- Каждую неделю
        status LIKE '%🗞%'
        AND
        strftime('%w', {sqlite_format_date('date')}) =
        CAST(strftime('%w', {sqlite_format_date(':date')}) as TEXT)
    )
    OR
    ( -- Каждый день
        status LIKE '%📬%'
    )
)
LIMIT 1;
""",
    "delete events_older_30_days": """
-- Удаляем события старше 30 дней
DELETE FROM events
      WHERE removal_time IS NOT NULL AND 
            (julianday('now') - julianday(removal_time) > 30);
""",
}
