
CREATE TABLE IF NOT EXISTS users (
    user_id           INT  PRIMARY KEY NOT NULL,
    token             TEXT UNIQUE NOT NULL,
    username          TEXT UNIQUE NOT NULL,
    password          TEXT NOT NULL,
    email             TEXT UNIQUE NOT NULL,
    user_status       INT  DEFAULT (0),
    max_event_id      INT  DEFAULT (1),
    icon              BLOB DEFAULT NULL,
    reg_date          TEXT NOT NULL DEFAULT (DATETIME()),
    token_create_time TEXT NOT NULL DEFAULT (DATETIME()),
    chat_id           INT  UNIQUE DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    group_id          TEXT PRIMARY KEY NOT NULL,
    name              TEXT NOT NULL,  -- Название группы
    token             TEXT UNIQUE NOT NULL,
    token_create_time TEXT NOT NULL DEFAULT (DATETIME()),
    owner_id          INT  NOT NULL,  -- владелец группы
    max_event_id      INT  DEFAULT (1),
    icon              BLOB DEFAULT NULL,
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
    lang               TEXT DEFAULT 'ru',
    sub_urls           INT  CHECK (sub_urls IN (0, 1)) DEFAULT (1),
    city               TEXT DEFAULT 'Moscow',
    timezone           INT  CHECK (-13 < timezone < 13) DEFAULT (3),
    direction          TEXT CHECK (direction IN ('DESC', 'ASC')) DEFAULT 'DESC',
    notifications      INT  CHECK (notifications IN (0, 1, 2)) DEFAULT (0),
    notifications_time TEXT DEFAULT '08:00',
    theme              INT  DEFAULT (0),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS tg_settings (
    user_id            INT  UNIQUE,
    group_id           TEXT UNIQUE,
    lang               TEXT DEFAULT 'ru',
    sub_urls           INT  CHECK (sub_urls IN (0, 1)) DEFAULT (1),
    city               TEXT DEFAULT 'Moscow',
    timezone           INT  CHECK (-13 < timezone < 13) DEFAULT (3),
    direction          TEXT CHECK (direction IN ('DESC', 'ASC')) DEFAULT 'DESC',
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
    status              TEXT DEFAULT '⬜️',
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
    media           BLOB NOT NULL,
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

------------------------------------------------------------------------------------------------------------------------

-- При удалении пользователя, удаляем все строки связанные с ним.
CREATE TRIGGER IF NOT EXISTS trigger_delete_user
AFTER DELETE ON users FOR EACH ROW
BEGIN
    DELETE FROM events         WHERE user_id = OLD.user_id;
    DELETE FROM users_settings WHERE user_id = OLD.user_id;
    DELETE FROM tg_settings    WHERE user_id = OLD.user_id;
    DELETE FROM groups         WHERE owner_id = OLD.user_id;
    DELETE FROM members        WHERE user_id = OLD.user_id;
END;

-- Триггер обновления времени последнего изменения токена
CREATE TRIGGER IF NOT EXISTS trigger_recent_changes_time_user_token
AFTER UPDATE OF token ON users FOR EACH ROW
BEGIN
    UPDATE users
       SET token_create_time = DATETIME()
     WHERE user_id = NEW.user_id;
END;

-- Триггер обновления времени последнего изменения токена в группах
CREATE TRIGGER IF NOT EXISTS trigger_recent_changes_time_group_token
AFTER UPDATE OF token ON groups FOR EACH ROW
BEGIN
    UPDATE groups
       SET token_create_time = DATETIME()
     WHERE group_id = NEW.group_id;
END;

-- Триггер обновления времени последнего изменения события
CREATE TRIGGER IF NOT EXISTS trigger_recent_changes_time_event
AFTER UPDATE OF date, text, status ON events FOR EACH ROW
BEGIN
    UPDATE events
       SET recent_changes_time = DATETIME()
     WHERE event_id = NEW.event_id;
END;

-- При удалении события, удаляем медиа принадлежащие этому событию.
CREATE TRIGGER IF NOT EXISTS trigger_delete_event_media
AFTER DELETE ON events FOR EACH ROW
BEGIN
    DELETE FROM media WHERE event_id = OLD.event_id;
END;


-- При добавлении группы, добавляем запись в members с user_id владельца группы
CREATE TRIGGER IF NOT EXISTS trigger_add_group_member
AFTER INSERT ON groups FOR EACH ROW
BEGIN
    INSERT INTO members (group_id, user_id, entry_date, member_status)
    VALUES (NEW.group_id, NEW.owner_id, DATETIME(), 2);
END;

-- При удалении группы, удаляем все строки из members связанные с этой группой.
CREATE TRIGGER IF NOT EXISTS trigger_delete_group
AFTER DELETE ON groups FOR EACH ROW
BEGIN
    DELETE FROM members     WHERE group_id IS OLD.group_id;
    DELETE FROM events      WHERE group_id IS OLD.group_id;
    DELETE FROM tg_settings WHERE group_id IS OLD.group_id;
END;

-- При добавлении пользователя добавлять запись в настройки.
CREATE TRIGGER IF NOT EXISTS trigger_create_user
BEFORE INSERT ON users FOR EACH ROW
BEGIN
    INSERT INTO users_settings (user_id)
    VALUES (NEW.user_id);
END;

-- При добавлении chat_id в users то добавляет удаляет запись в tg_settings (login)
CREATE TRIGGER IF NOT EXISTS trigger_add_user_chat_id
BEFORE UPDATE OF chat_id ON users FOR EACH ROW
WHEN OLD.chat_id IS NULL
BEGIN
    INSERT OR IGNORE INTO tg_settings (user_id)
         VALUES (NEW.user_id);
END;

-- При добавлении chat_id в groups то добавляет удаляет запись в tg_settings
CREATE TRIGGER IF NOT EXISTS trigger_add_group_chat_id
AFTER UPDATE OF chat_id ON groups FOR EACH ROW
WHEN OLD.chat_id IS NULL
BEGIN
    INSERT OR IGNORE INTO tg_settings (group_id)
         VALUES (NEW.group_id);
END;

-- индекс
CREATE INDEX IF NOT EXISTS index_event_search ON events (user_id, group_id, event_id, date);
