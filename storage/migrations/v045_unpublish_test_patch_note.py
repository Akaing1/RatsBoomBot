from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        UPDATE patch_notes
        SET published_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE slug = 'test-patch-notes'
        """
    )
