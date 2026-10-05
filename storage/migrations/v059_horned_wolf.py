"""Add the Common Horned Wolf without changing existing ownership."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES ('horned_wolf', 'Horned Wolf', 'common', '/assets/Horned%20Wolf.png', 4, 50)
        """
    )
