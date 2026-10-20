async def migrate(connection) -> None:
    await connection.execute(
        """
        UPDATE pet_definitions
        SET sprite_path = '/assets/bat.png'
        WHERE id = 'dungeon_bat'
        """
    )
