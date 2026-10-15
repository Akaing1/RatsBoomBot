"""Add the Common Dog of the Sun without changing existing pets."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("dog_of_the_sun", "Dog of the Sun", "common", "/assets/Dog%20of%20the%20Sun.png", 4, 50),
    )
