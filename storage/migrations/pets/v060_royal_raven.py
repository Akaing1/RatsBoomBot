"""Add the Common Royal Raven without changing existing pets."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES ('royal_raven', 'Royal Raven', 'common', '/assets/Royal%20Raven.png', 4, 50)
        """
    )
