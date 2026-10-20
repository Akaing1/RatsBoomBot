"""Keep the initial three pets Common and rename the rat without changing ownership."""


async def migrate(connection) -> None:
    await connection.execute(
        "UPDATE pet_definitions SET rarity = 'common' WHERE id IN ('dungeon_bat', 'explosive_rat', 'sleepy_fox')"
    )
    await connection.execute(
        "UPDATE pet_definitions SET display_name = 'Little Rat' WHERE id = 'explosive_rat'"
    )
