from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute("DROP INDEX IF EXISTS idx_redeem_claims_second")
    await connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_redeem_claims_second
        ON redeem_claims (
            broadcaster_id,
            redeem_type,
            stream_id
        )
        WHERE redeem_type = 'second'
        """
    )
