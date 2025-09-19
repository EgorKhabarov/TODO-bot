
CREATE TABLE IF NOT EXISTS chats (
    date       TEXT NOT NULL DEFAULT (DATETIME()),
    id         INT  PRIMARY KEY NOT NULL,
    type       TEXT NOT NULL,
    title      TEXT DEFAULT NULL,
    username   TEXT UNIQUE NOT NULL,
    first_name TEXT DEFAULT NULL,
    last_name  TEXT DEFAULT NULL,
    bio        TEXT DEFAULT NULL,
    is_forum   INT  NOT NULL,
    json       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id           INT  PRIMARY KEY NOT NULL,
    token             TEXT UNIQUE NOT NULL,
    username          TEXT UNIQUE NOT NULL,
    password          TEXT NOT NULL,
    email             TEXT UNIQUE NOT NULL,
    user_status       INT  DEFAULT (0),
    max_event_id      INT  DEFAULT (1),
    icon              TEXT DEFAULT NULL,
    reg_date          TEXT NOT NULL DEFAULT (DATETIME()),
    token_create_time TEXT NOT NULL DEFAULT (DATETIME()),
    chat_id           INT  UNIQUE DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    group_id          TEXT PRIMARY KEY NOT NULL,
    name              TEXT NOT NULL,  -- Group name
    token             TEXT UNIQUE NOT NULL,
    token_create_time TEXT NOT NULL DEFAULT (DATETIME()),
    owner_id          INT  NOT NULL,  -- Group owner
    max_event_id      INT  DEFAULT (1),
    icon              TEXT DEFAULT NULL,
    chat_id           INT  UNIQUE DEFAULT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS members (
    group_id      TEXT NOT NULL,
    user_id       INT  NOT NULL,  -- member_id
    entry_date    TEXT NOT NULL DEFAULT (DATETIME()),
    member_status INT  NOT NULL DEFAULT (0),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (group_id) REFERENCES groups(group_id)
);

------------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users_settings (
    user_id            INT  UNIQUE NOT NULL,
    lang               TEXT DEFAULT 'en',
    sub_urls           INT  CHECK (sub_urls IN (0, 1)) DEFAULT (1),
    city               TEXT DEFAULT 'London',
    timezone           INT  CHECK (-13 < timezone < 13) DEFAULT (0),
    notifications      INT  CHECK (notifications IN (0, 1, 2)) DEFAULT (0),
    notifications_time TEXT DEFAULT '08:00',
    theme              INT  DEFAULT (0),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS tg_settings (
    user_id            INT  UNIQUE,
    group_id           TEXT UNIQUE,
    lang               TEXT DEFAULT 'en',
    sub_urls           INT  CHECK (sub_urls IN (0, 1)) DEFAULT (1),
    city               TEXT DEFAULT 'London',
    timezone           INT  CHECK (-13 < timezone < 13) DEFAULT (0),
    notifications      INT  CHECK (notifications IN (0, 1, 2)) DEFAULT (0),
    notifications_time TEXT DEFAULT '08:00',
    theme              INT  DEFAULT (0),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (group_id) REFERENCES groups(group_id)
);

------------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS events (
    user_id             INT,
    group_id            TEXT,
    event_id            INT  NOT NULL,
    date                TEXT NOT NULL,
    text                TEXT NOT NULL,
    statuses            TEXT DEFAULT '["⬜"]',
    adding_time         TEXT DEFAULT (DATETIME()),
    recent_changes_time TEXT DEFAULT NULL,
    removal_time        TEXT DEFAULT NULL,
    history             TEXT DEFAULT '[]',
    CHECK (
        (user_id IS NOT NULL AND group_id IS NULL) OR
        (user_id IS NULL AND group_id IS NOT NULL)
    ),
    UNIQUE (user_id, event_id),
    UNIQUE (group_id, event_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (group_id) REFERENCES groups(group_id)
);

CREATE TABLE IF NOT EXISTS media (
    media_id        TEXT PRIMARY KEY NOT NULL,
    event_id        INT  NOT NULL,
    user_id         INT,
    group_id        TEXT,
    filename        TEXT NOT NULL,
    media_type      TEXT NOT NULL,
    media           TEXT NOT NULL,
    url             TEXT DEFAULT '',
    url_create_time TEXT DEFAULT '',
    CHECK (
        (user_id IS NOT NULL AND group_id IS NULL) OR
        (user_id IS NULL AND group_id IS NOT NULL)
    ),
    UNIQUE (user_id, event_id),
    UNIQUE (group_id, event_id),
    FOREIGN KEY (user_id, event_id) REFERENCES events(user_id, event_id),
    FOREIGN KEY (group_id, event_id) REFERENCES events(group_id, event_id)
);

------------------------------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS errors (
    user_id   INT  NOT NULL,
    user_text TEXT,
    reason    TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS frequently_used_dates (
    user_id      INT,
    group_id     TEXT,
    date         TEXT      NOT NULL,
    count        INT       NOT NULL DEFAULT 1,
    pinned       INT       NOT NULL DEFAULT 0,
    last_visited TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (user_id IS NOT NULL AND group_id IS NULL) OR
        (user_id IS NULL AND group_id IS NOT NULL)
    ),
    UNIQUE (user_id, date),
    UNIQUE (group_id, date),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (group_id) REFERENCES groups(group_id)
);

CREATE TABLE IF NOT EXISTS chat_states (
    chat_id    INT,
    state_type TEXT,
    state      TEXT,
    PRIMARY KEY (chat_id, state_type)
);

------------------------------------------------------------------------------------------------------------------------

-- When deleting a user, we delete all rows associated with it.
CREATE TRIGGER IF NOT EXISTS trigger_delete_user
AFTER DELETE ON users FOR EACH ROW
BEGIN
    DELETE FROM events         WHERE user_id = OLD.user_id;
    DELETE FROM users_settings WHERE user_id = OLD.user_id;
    DELETE FROM tg_settings    WHERE user_id = OLD.user_id;
    DELETE FROM groups         WHERE owner_id = OLD.user_id;
    DELETE FROM members        WHERE user_id = OLD.user_id;
END;

-- Trigger for updating the time of the last token change
CREATE TRIGGER IF NOT EXISTS trigger_recent_changes_time_user_token
AFTER UPDATE OF token ON users FOR EACH ROW
BEGIN
    UPDATE users
       SET token_create_time = DATETIME()
     WHERE user_id = NEW.user_id;
END;

-- Trigger for updating the time of the last token change in groups
CREATE TRIGGER IF NOT EXISTS trigger_recent_changes_time_group_token
AFTER UPDATE OF token ON groups FOR EACH ROW
BEGIN
    UPDATE groups
       SET token_create_time = DATETIME()
     WHERE group_id = NEW.group_id;
END;

-- Trigger for updating the last change time of an event
CREATE TRIGGER IF NOT EXISTS trigger_recent_changes_time_event
AFTER UPDATE OF date, text, statuses, removal_time ON events FOR EACH ROW
BEGIN
    UPDATE events
       SET recent_changes_time = DATETIME(),
           history = CASE
               WHEN OLD.date != NEW.date
               THEN JSON_INSERT(history, '$[#]', JSON_ARRAY('date', JSON_ARRAY(OLD.date, NEW.date), DATETIME()))

               WHEN OLD.text != NEW.text
               THEN JSON_INSERT(history, '$[#]', JSON_ARRAY('text', JSON_ARRAY(OLD.text, NEW.text), DATETIME()))

               WHEN OLD.statuses != NEW.statuses
               THEN JSON_INSERT(history, '$[#]', JSON_ARRAY('statuses', JSON_ARRAY(JSON(OLD.statuses), NEW.statuses), DATETIME()))

               WHEN OLD.removal_time IS NOT NEW.removal_time AND NEW.removal_time IS NOT NULL
               THEN JSON_INSERT(history, '$[#]', JSON_ARRAY('delete', JSON_ARRAY(OLD.removal_time, NEW.removal_time), DATETIME()))

               WHEN OLD.removal_time IS NOT NEW.removal_time AND NEW.removal_time IS NULL
               THEN JSON_INSERT(history, '$[#]', JSON_ARRAY('recover', JSON_ARRAY(OLD.removal_time, NEW.removal_time), DATETIME()))

               ELSE history
           END
     WHERE event_id = NEW.event_id
           AND user_id IS OLD.user_id
           AND group_id IS OLD.group_id;

    UPDATE events
       SET history = JSON_ARRAY(
               JSON_EXTRACT(history, '$[#-10]'),
               JSON_EXTRACT(history, '$[#-9]'),
               JSON_EXTRACT(history, '$[#-8]'),
               JSON_EXTRACT(history, '$[#-7]'),
               JSON_EXTRACT(history, '$[#-6]'),
               JSON_EXTRACT(history, '$[#-5]'),
               JSON_EXTRACT(history, '$[#-4]'),
               JSON_EXTRACT(history, '$[#-3]'),
               JSON_EXTRACT(history, '$[#-2]'),
               JSON_EXTRACT(history, '$[#-1]')
           )
     WHERE event_id = NEW.event_id
           AND user_id IS OLD.user_id
           AND group_id IS OLD.group_id
           AND JSON_ARRAY_LENGTH(history) > 10;
END;

-- When deleting an event, we delete the media belonging to this event.
CREATE TRIGGER IF NOT EXISTS trigger_delete_event_media
AFTER DELETE ON events FOR EACH ROW
BEGIN
    DELETE FROM media
          WHERE event_id = OLD.event_id
                AND user_id IS OLD.user_id
                AND group_id IS OLD.group_id;
END;


-- When adding a group, add an entry to members with the user_id of the group owner
CREATE TRIGGER IF NOT EXISTS trigger_add_group_member
AFTER INSERT ON groups FOR EACH ROW
BEGIN
    INSERT INTO members (group_id, user_id, entry_date, member_status)
    VALUES (NEW.group_id, NEW.owner_id, DATETIME(), 2);
END;

-- When deleting a group, we delete all rows from members associated with this group.
CREATE TRIGGER IF NOT EXISTS trigger_delete_group
AFTER DELETE ON groups FOR EACH ROW
BEGIN
    DELETE FROM members     WHERE group_id IS OLD.group_id;
    DELETE FROM events      WHERE group_id IS OLD.group_id;
    DELETE FROM tg_settings WHERE group_id IS OLD.group_id;
END;

-- When adding a user, add an entry to the settings.
CREATE TRIGGER IF NOT EXISTS trigger_create_user
BEFORE INSERT ON users FOR EACH ROW
BEGIN
    INSERT INTO users_settings (user_id)
    VALUES (NEW.user_id);
END;

-- When adding chat_id to users, it adds and deletes the entry in tg_settings (login)
CREATE TRIGGER IF NOT EXISTS trigger_add_user_chat_id
BEFORE UPDATE OF chat_id ON users FOR EACH ROW
WHEN OLD.chat_id IS NULL
BEGIN
    INSERT OR IGNORE INTO tg_settings (user_id)
                               VALUES (NEW.user_id);
END;

-- When adding chat_id to groups, it adds and deletes the entry in tg_settings
CREATE TRIGGER IF NOT EXISTS trigger_add_group_chat_id
AFTER UPDATE OF chat_id ON groups FOR EACH ROW
WHEN OLD.chat_id IS NULL
BEGIN
    INSERT OR IGNORE INTO tg_settings (group_id)
                               VALUES (NEW.group_id);
END;

-- index
CREATE INDEX IF NOT EXISTS index_event_search ON events (user_id, group_id, event_id, date);
