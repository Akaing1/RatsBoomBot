async def migrate(connection):
    await connection.execute('''CREATE TABLE moderation_external_bans (
        id INTEGER PRIMARY KEY, event_key TEXT NOT NULL UNIQUE,
        broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT NOT NULL,
        moderator_id TEXT NOT NULL, moderator_name TEXT NOT NULL, source TEXT NOT NULL,
        reason TEXT, banned_at REAL NOT NULL, received_at REAL NOT NULL,
        timestamp_source TEXT NOT NULL
    )''')
    await connection.execute('''CREATE INDEX moderation_ban_account_time
        ON moderation_external_bans(broadcaster_id, user_id, banned_at)''')
    await connection.execute('''CREATE TABLE moderation_shadow_messages (
        id INTEGER PRIMARY KEY, message_key TEXT NOT NULL UNIQUE,
        broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT NOT NULL,
        message TEXT NOT NULL, fingerprint TEXT NOT NULL, sent_at REAL NOT NULL,
        received_at REAL NOT NULL, timestamp_source TEXT NOT NULL,
        flagged INTEGER NOT NULL, protected INTEGER NOT NULL
    )''')
    await connection.execute('''CREATE INDEX moderation_shadow_account_time
        ON moderation_shadow_messages(broadcaster_id, user_id, sent_at)''')
    await connection.execute('''CREATE TABLE moderation_ban_messages (
        ban_id INTEGER NOT NULL REFERENCES moderation_external_bans(id),
        message_id INTEGER NOT NULL REFERENCES moderation_shadow_messages(id),
        PRIMARY KEY (ban_id, message_id)
    )''')
