from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_chat_identities (
            broadcaster_id TEXT PRIMARY KEY,
            premium_enabled INTEGER NOT NULL DEFAULT 0 CHECK (premium_enabled IN (0, 1)),
            bot_user_id TEXT,
            bot_login TEXT,
            bot_display_name TEXT,
            connected_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_channel_chat_identities_bot_user
        ON channel_chat_identities (bot_user_id)
        """
    )
