from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        INSERT INTO counters (name, value)
        VALUES ('reklop', 700)
        ON CONFLICT(name) DO UPDATE SET
            value = excluded.value
        """
    )
