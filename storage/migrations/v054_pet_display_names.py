"""Update pet names and sprite paths without changing ownership IDs."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        UPDATE pet_definitions
        SET display_name = 'Silly Bat', sprite_path = '/assets/Silly%20Bat.png'
        WHERE id = 'dungeon_bat'
        """
    )
    await connection.execute(
        """
        UPDATE pet_definitions
        SET display_name = 'Explosive Rat', sprite_path = '/assets/Explosive%20Rat.png'
        WHERE id = 'explosive_rat'
        """
    )
