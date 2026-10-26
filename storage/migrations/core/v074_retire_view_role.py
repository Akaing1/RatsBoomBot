"""Retire read-only grants without silently expanding anyone's permissions."""
async def migrate(connection):
    await connection.execute("ALTER TABLE channel_access RENAME TO channel_access_legacy")
    await connection.execute("DROP INDEX channel_access_user")
    await connection.execute("""CREATE TABLE channel_access (
        broadcaster_id TEXT NOT NULL, user_id TEXT NOT NULL,
        channel_name TEXT NOT NULL, user_name TEXT NOT NULL,
        feature TEXT NOT NULL CHECK(feature = 'dashboard'),
        permission TEXT NOT NULL CHECK(permission IN ('edit', 'super')),
        PRIMARY KEY (broadcaster_id, user_id, feature))""")
    await connection.execute("INSERT INTO channel_access SELECT * FROM channel_access_legacy WHERE permission IN ('edit', 'super')")
    await connection.execute("DROP TABLE channel_access_legacy")
    await connection.execute("CREATE INDEX channel_access_user ON channel_access(user_id)")
