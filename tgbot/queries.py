from todoapi.utils import sqlite_format_date

queries = {
    # Для кнопок
    "select day_number_with_events": """
-- Дни в которые есть события
SELECT CAST (SUBSTR(date, 1, 2) AS INT) AS day_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id = ? AND 
       removal_time IS NULL AND 
       date LIKE ?
 GROUP BY day_number;
""",
    "select day_number_with_birthdays": """
-- Номера дней дней рождений в конкретном месяце
SELECT DISTINCT CAST (SUBSTR(date, 1, 2) AS INT) 
  FROM events
 WHERE user_id = ? AND 
       removal_time IS NULL AND 
       (
           status LIKE '%📅%' OR
           (
               (
                   status LIKE '%🎉%' OR 
                   status LIKE '%🎊%' OR 
                   status LIKE '%📆%'
               ) AND 
               SUBSTR(date, 4, 2) = ?
           )
       );
""",
    "select month_number_with_events": """
-- Месяцы в которых есть события
SELECT CAST (SUBSTR(date, 4, 2) AS INT) AS month_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id = ? AND
       removal_time IS NULL AND
       date LIKE ?
 GROUP BY month_number;
""",
    "select year_number_with_events": """
-- Года в которых есть события
SELECT CAST (SUBSTR(date, 7, 4) AS INT) AS year_number,
       COUNT(event_id) AS event_count
  FROM events
 WHERE user_id = ? AND
       removal_time IS NULL
 GROUP BY year_number;
""",
    "select month_number_with_birthdays": """
-- Номера месяцев дней рождений в конкретном месяце
SELECT DISTINCT CAST (SUBSTR(date, 4, 2) AS INT) 
  FROM events
 WHERE user_id = ? AND 
       removal_time IS NULL AND 
       (
           status LIKE '%🎉%' OR 
           status LIKE '%🎊%' OR 
           status LIKE '%📆%'
       );
""",
    "select year_number_with_birthdays": """
-- Номера месяцев дней рождений в конкретном месяце
SELECT 1
  FROM events
 WHERE user_id = ? AND 
       removal_time IS NULL AND 
       (
           status LIKE '%🎉%' OR 
           status LIKE '%🎊%' OR 
           status LIKE '%📆%'
       );
""",
    "select week_day_number_with_event_every_week": f"""
-- Номер дней недели в которых есть события повторяющиеся каждую неделю события
SELECT DISTINCT CAST (strftime('%w', {sqlite_format_date('date')}) - 1 AS INT) 
  FROM events
 WHERE user_id = ? AND 
       removal_time IS NULL AND 
       status LIKE '%🗞%';
""",
    "select having_event_every_month": """
-- Есть ли событие, которое повторяется каждый месяц
SELECT date
  FROM events
 WHERE user_id = ? AND 
       removal_time IS NULL AND 
       status LIKE '%📅%'
 LIMIT 1;
""",
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
    "select chat_ids_for_sending_notifications": """
-- id людей через запятую, которым нужно сейчас прислать уведомление
SELECT GROUP_CONCAT(IFNULL(user_id, group_id), ',') AS id_list
  FROM tg_settings
 WHERE notifications = 1 AND 
       user_status != -1 AND 
       ((CAST(SUBSTR(notifications_time, 1, 2) AS INT) - timezone + 24) % 24) = ? AND 
       CAST(SUBSTR(notifications_time, 4, 2) AS INT) = ?;
""",
    "delete events_older_30_days": """
-- Удаляем события старше 30 дней
DELETE FROM events
      WHERE removal_time IS NOT NULL AND 
            (julianday('now') - julianday(removal_time) > 30);
""",
}
