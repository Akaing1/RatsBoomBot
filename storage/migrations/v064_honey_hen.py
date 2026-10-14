"""Add the Common Honey Hen without changing existing pets."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("honey_hen", "Honey Hen", "common", "/assets/Honey%20Hen.png", 4, 50),
    )
