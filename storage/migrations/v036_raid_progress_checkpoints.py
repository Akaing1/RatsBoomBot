"""Persist raid health checkpoints so milestone announcements never repeat."""


async def migrate(connection):
    await connection.execute(
        """
        CREATE TABLE raid_boss_health_checkpoints (
            event_id INTEGER NOT NULL,
            checkpoint INTEGER NOT NULL CHECK(checkpoint IN (25, 50, 75)),
            reached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_id, checkpoint)
        )
        """
    )
