async def migrate(connection) -> None:
    await connection.execute(
        """
        CREATE TABLE pet_definitions (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            sprite_path TEXT NOT NULL,
            frame_count INTEGER NOT NULL CHECK(frame_count > 0),
            max_level INTEGER NOT NULL CHECK(max_level > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await connection.execute(
        """
        CREATE TABLE user_pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            pet_id TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1 CHECK(level > 0),
            xp INTEGER NOT NULL DEFAULT 0 CHECK(xp >= 0),
            passive_type TEXT NOT NULL,
            passive_value_bps INTEGER NOT NULL CHECK(passive_value_bps >= 0),
            acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, pet_id),
            FOREIGN KEY(pet_id) REFERENCES pet_definitions(id)
        )
        """
    )
    await connection.execute(
        """
        CREATE TABLE user_pet_loadouts (
            user_id TEXT PRIMARY KEY,
            user_pet_id INTEGER NOT NULL UNIQUE,
            equipped_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_pet_id) REFERENCES user_pets(id) ON DELETE CASCADE
        )
        """
    )
    await connection.execute(
        """
        INSERT INTO pet_definitions (
            id, display_name, rarity, sprite_path, frame_count, max_level
        )
        VALUES ('dungeon_bat', 'Dungeon Bat', 'common', '/assets/bat.png', 4, 50)
        """
    )
