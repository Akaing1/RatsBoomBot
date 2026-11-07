async def migrate(connection) -> None:
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_activity_history (
            broadcaster_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            entries_json TEXT NOT NULL,
            PRIMARY KEY (broadcaster_id, kind)
        )
    """)
