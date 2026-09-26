async def migrate(connection) -> None:
    """Repair holes left by earlier quote removals and reset channel counters."""
    await connection.execute(
        """
        CREATE TABLE channel_quotes_compacted (
            broadcaster_id TEXT NOT NULL,
            number INTEGER NOT NULL,
            message TEXT NOT NULL,
            added_by TEXT NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, number)
        )
        """
    )
    await connection.execute(
        """
        INSERT INTO channel_quotes_compacted (broadcaster_id, number, message, added_by, added_at)
        SELECT broadcaster_id,
               ROW_NUMBER() OVER (PARTITION BY broadcaster_id ORDER BY number),
               message, added_by, added_at
        FROM channel_quotes
        """
    )
    await connection.execute("DROP TABLE channel_quotes")
    await connection.execute("ALTER TABLE channel_quotes_compacted RENAME TO channel_quotes")
    await connection.execute(
        """
        UPDATE channel_quote_sequences
        SET last_number = COALESCE(
            (SELECT MAX(number) FROM channel_quotes WHERE broadcaster_id = channel_quote_sequences.broadcaster_id),
            0
        )
        """
    )
