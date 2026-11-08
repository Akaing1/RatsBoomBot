async def migrate(connection) -> None:
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS eight_ball_history (
            id INTEGER PRIMARY KEY,
            broadcaster_id TEXT NOT NULL,
            question TEXT NOT NULL,
            category TEXT NOT NULL,
            outcome TEXT NOT NULL,
            response_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await connection.execute("CREATE INDEX IF NOT EXISTS idx_eight_ball_history_channel ON eight_ball_history (broadcaster_id, id)")
