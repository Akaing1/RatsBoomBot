"""Align existing UAT pets with the selected fixed passives."""


async def migrate(connection) -> None:
    for pet_id, passive_type, starting_bps in (
        ("dungeon_bat", "gamble_odds", 500),
        ("explosive_rat", "loyalty_gain", 1000),
        ("sleepy_fox", "raid_damage", 1000),
    ):
        await connection.execute(
            "UPDATE user_pets SET passive_type = ?, passive_value_bps = ? WHERE pet_id = ?",
            (passive_type, starting_bps, pet_id),
        )
