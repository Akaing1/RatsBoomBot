from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute("ALTER TABLE raid_boss_attacks ADD COLUMN overdrive_attempted INTEGER NOT NULL DEFAULT 0")
    await connection.execute("ALTER TABLE raid_boss_attacks ADD COLUMN overdrive_consumable TEXT")
