async def migrate(connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS viewer_queue_blacklist (
            broadcaster_id TEXT NOT NULL,
            username TEXT NOT NULL COLLATE NOCASE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, username)
        )
        """
    )
    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_viewer_queue_blacklist_channel
        ON viewer_queue_blacklist (broadcaster_id, username)
        """
    )
