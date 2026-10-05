"""Repair rat definitions seeded before the pet was renamed."""


async def migrate(connection) -> None:
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES ('explosive_rat', 'Explosive Rat', 'common', '/assets/explosive_rat.png', 4, 50)
        ON CONFLICT(id) DO UPDATE SET
            display_name = excluded.display_name,
            sprite_path = excluded.sprite_path
        """
    )
    # A previous deployment seeded dungeon_rat under migration 52. Keep any
    # existing ownership and equipped loadout while moving to the new ID.
    await connection.execute(
        """
        UPDATE user_pet_loadouts
        SET user_pet_id = (
            SELECT newer.id FROM user_pets AS old
            JOIN user_pets AS newer ON newer.user_id = old.user_id
                                   AND newer.pet_id = 'explosive_rat'
            WHERE old.id = user_pet_loadouts.user_pet_id
        )
        WHERE user_pet_id IN (
            SELECT old.id FROM user_pets AS old
            JOIN user_pets AS newer ON newer.user_id = old.user_id
                                   AND newer.pet_id = 'explosive_rat'
            WHERE old.pet_id = 'dungeon_rat'
        )
        """
    )
    await connection.execute(
        """
        DELETE FROM user_pets
        WHERE pet_id = 'dungeon_rat'
          AND EXISTS (
              SELECT 1 FROM user_pets AS newer
              WHERE newer.user_id = user_pets.user_id
                AND newer.pet_id = 'explosive_rat'
          )
        """
    )
    await connection.execute(
        "UPDATE user_pets SET pet_id = 'explosive_rat' WHERE pet_id = 'dungeon_rat'"
    )
    await connection.execute("DELETE FROM pet_definitions WHERE id = 'dungeon_rat'")
