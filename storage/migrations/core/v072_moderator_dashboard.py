"""Promote Notes grants into dashboard roles without granting settings access."""
async def migrate(connection):
    await connection.execute("ALTER TABLE channel_access RENAME TO channel_access_old")
    await connection.execute("DROP INDEX channel_access_user")
    await connection.execute("""CREATE TABLE channel_access (
        broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL,
        channel_name TEXT NOT NULL, user_name TEXT NOT NULL,
        feature TEXT NOT NULL CHECK(feature = 'dashboard'),
        permission TEXT NOT NULL CHECK(permission IN ('view', 'edit', 'super')),
        PRIMARY KEY (broadcaster_id, user_id, feature))""")
    await connection.execute("INSERT INTO channel_access SELECT broadcaster_id, user_id, channel_name, user_name, 'dashboard', permission FROM channel_access_old")
    await connection.execute("DROP TABLE channel_access_old")
    await connection.execute("CREATE INDEX channel_access_user ON channel_access(user_id)")
    await connection.execute("""CREATE TABLE moderator_twitch_tokens (
        user_id TEXT PRIMARY KEY, access_token TEXT NOT NULL,
        refresh_token TEXT NOT NULL, scopes TEXT NOT NULL)""")
