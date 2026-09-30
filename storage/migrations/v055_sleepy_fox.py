"""Add Sleepy Fox without changing existing pets."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES ('sleepy_fox', 'Sleepy Fox', 'common', '/assets/Sleepy%20Fox.png', 4, 50)
        """
    )
