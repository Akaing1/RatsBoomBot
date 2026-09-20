async def migrate(connection):
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_protected_users (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            login TEXT NOT NULL,
            display_name TEXT NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, user_id)
        )
        """
    )
