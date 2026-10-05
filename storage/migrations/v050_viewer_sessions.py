async def migrate(connection) -> None:
    await connection.execute("""
        CREATE TABLE viewer_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            last_action_at INTEGER
        )
    """)
    await connection.execute("CREATE INDEX viewer_sessions_expires_at ON viewer_sessions(expires_at)")
