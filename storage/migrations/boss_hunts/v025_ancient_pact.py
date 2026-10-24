from typing import Any


async def migrate(connection: Any) -> None:
    columns = {str(row["name"]) for row in await connection.fetchall("PRAGMA table_info(raid_boss_stream_effects)")}

    if "ancient_pact_user_id" in columns:
        return

    await connection.execute("ALTER TABLE raid_boss_stream_effects RENAME TO raid_boss_stream_effects_legacy")
    await connection.execute(
        """
        CREATE TABLE raid_boss_stream_effects (
            broadcaster_id TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            blessing_user_id TEXT,
            blessing_username TEXT,
            purchased_at TEXT,
            ancient_pact_user_id TEXT,
            ancient_pact_username TEXT,
            ancient_pact_purchased_at TEXT,
            PRIMARY KEY (broadcaster_id, stream_id)
        )
        """
    )
    await connection.execute(
        """
        INSERT INTO raid_boss_stream_effects (
            broadcaster_id, stream_id, blessing_user_id, blessing_username, purchased_at
        )
        SELECT broadcaster_id, stream_id, blessing_user_id, blessing_username, purchased_at
        FROM raid_boss_stream_effects_legacy
        """
    )
    await connection.execute("DROP TABLE raid_boss_stream_effects_legacy")
