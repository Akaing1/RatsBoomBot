async def migrate(connection):
    await connection.execute(
        """
        CREATE TABLE youtube_chat_connections (
            broadcaster_id TEXT PRIMARY KEY,
            youtube_channel_id TEXT NOT NULL,
            youtube_channel_title TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            connected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await connection.execute(
        """
        CREATE TABLE chat_widget_tokens (
            broadcaster_id TEXT PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
