async def migrate(connection) -> None:
    await connection.execute(
        """
        CREATE TABLE channel_quote_sequences (
            broadcaster_id TEXT PRIMARY KEY,
            last_number INTEGER NOT NULL
        )
        """
    )
    await connection.execute(
        """
        CREATE TABLE channel_quotes (
            broadcaster_id TEXT NOT NULL,
            number INTEGER NOT NULL,
            message TEXT NOT NULL,
            added_by TEXT NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, number)
        )
        """
    )
