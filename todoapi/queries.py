queries = {
    "delete settings": """
DELETE FROM settings
      WHERE user_id = ?;
""",
    "delete all_events": """
DELETE FROM events
      WHERE user_id = ?;
""",
    "delete event": """
DELETE FROM events
      WHERE user_id = ? AND 
            event_id = ?;
""",
    "update user_status": """
UPDATE settings
   SET user_status = ?
 WHERE user_id = ?;
""",
    "select all_events": """
SELECT event_id,
       date,
       status,
       text
  FROM events
 WHERE user_id = ? AND 
       removal_time IS NULL;
""",
    "delete deleted_events": """
DELETE FROM events
      WHERE user_id = ? AND 
            removal_time IS NOT NULL;
""",
    "update restore_events": """
UPDATE events
   SET removal_time IS NULL
 WHERE user_id = ? AND 
       event_id = ?;
""",
    "update event_to_trash": """
UPDATE events
   SET removal_time = DATE() 
 WHERE user_id = ? AND 
       event_id = ?;
""",
    "update event_status": """
UPDATE events
   SET status = ?
 WHERE user_id = ? AND 
       event_id = ?;
""",
    "update event_date": """
UPDATE events
   SET date = ?
 WHERE user_id = ? AND
       event_id = ?;
""",
    "update event_text": """
UPDATE events
   SET text = ?
 WHERE user_id = ? AND 
       event_id = ?;
""",
    "insert event": """
INSERT INTO events (
    event_id,
    user_id,
    date,
    text
)
VALUES (
    COALESCE(
        (
            SELECT user_max_event_id
              FROM settings
             WHERE user_id = :user_id
        ),
        1
    ),
    :user_id,
    :date,
    :text
);
""",
    "update user_max_event_id": """
UPDATE settings
   SET user_max_event_id = user_max_event_id + 1
 WHERE user_id = ?;
""",
    "insert settings": """
INSERT INTO settings (user_id)
VALUES (?);
""",
    "select settings": """
SELECT lang,
       sub_urls,
       city,
       timezone,
       direction,
       user_status,
       notifications,
       notifications_time,
       theme
  FROM settings
 WHERE user_id = ?;
""",
    "select limits": """
SELECT 
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               date = :date
    ) AS count_today,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               date = :date
    ) AS sum_length_today,
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 4, 7) = :date_3
    ) AS count_month,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 4, 7) = :date_3
    ) AS sum_length_month,
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 7, 4) = :date_6
    ) AS count_year,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id AND 
               SUBSTR(date, 7, 4) = :date_6
    ) AS sum_length_year,
    (
        SELECT IFNULL(COUNT( * ), 0) 
          FROM events
         WHERE user_id = :user_id
    ) AS total_count,
    (
        SELECT IFNULL(SUM(LENGTH(text)), 0) 
          FROM events
         WHERE user_id = :user_id
    ) AS total_length;
""",
}
