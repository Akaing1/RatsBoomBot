async def migrate(connection) -> None:
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS channel_chat_preferences (
            broadcaster_id TEXT PRIMARY KEY,
            preferences_json TEXT NOT NULL
        )
    """)
