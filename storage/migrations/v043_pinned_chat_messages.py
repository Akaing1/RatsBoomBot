async def migrate(connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pinned_chat_messages (
            broadcaster_id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            message_json TEXT NOT NULL,
            pinned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
