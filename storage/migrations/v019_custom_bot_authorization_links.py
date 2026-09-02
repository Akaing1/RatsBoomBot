from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_bot_authorization_requests (
            state_hash TEXT PRIMARY KEY,
            broadcaster_id TEXT NOT NULL,
            expected_bot_user_id TEXT NOT NULL,
            expected_bot_login TEXT NOT NULL,
            expected_bot_display_name TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_custom_bot_authorization_requests_broadcaster
        ON custom_bot_authorization_requests (broadcaster_id, created_at)
        """
    )
