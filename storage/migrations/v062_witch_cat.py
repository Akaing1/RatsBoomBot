"""Add the Common Witch's Cat without changing existing pets."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("witch_cat", "Witch's Cat", "common", "/assets/Witch%27s%20Cat.png", 4, 50),
    )
