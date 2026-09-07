from typing import Any


async def migrate(connection: Any) -> None:
    columns = {str(row["name"]) for row in await connection.fetchall("PRAGMA table_info(raid_boss_players)")}

    for name in ("lucky_dice_charges", "fools_card_charges"):
        if name not in columns:
            await connection.execute(f"ALTER TABLE raid_boss_players ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")
