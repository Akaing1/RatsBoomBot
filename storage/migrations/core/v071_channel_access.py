"""Explicit channel delegation, keyed by Twitch identity rather than login."""
async def migrate(connection):
    await connection.execute("""CREATE TABLE channel_access (
        broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL,
        channel_name TEXT NOT NULL, user_name TEXT NOT NULL,
        feature TEXT NOT NULL CHECK(feature IN ('notes')),
        permission TEXT NOT NULL CHECK(permission IN ('view', 'edit')),
        PRIMARY KEY (broadcaster_id, user_id, feature))""")
    await connection.execute("CREATE INDEX channel_access_user ON channel_access(user_id)")
    await connection.execute("""CREATE TABLE channel_access_audit (
        id INTEGER PRIMARY KEY, broadcaster_id TEXT NOT NULL,
        actor_id TEXT NOT NULL, action TEXT NOT NULL, subject_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
