async def migrate(connection) -> None:
    await connection.execute(
        """
        CREATE TABLE viewer_gamble_outcomes (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0 CHECK(wins >= 0),
            losses INTEGER NOT NULL DEFAULT 0 CHECK(losses >= 0),
            PRIMARY KEY (broadcaster_id, user_id)
        )
        """
    )
    await connection.execute(
        "CREATE INDEX idx_viewer_gamble_outcomes_user ON viewer_gamble_outcomes (user_id)"
    )
