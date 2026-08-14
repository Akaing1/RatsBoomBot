from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS imported_redeem_totals (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            redeem_type TEXT NOT NULL,
            claim_count INTEGER NOT NULL CHECK (claim_count >= 0),
            source_last_write TEXT,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, user_id, redeem_type)
        )
        """
    )