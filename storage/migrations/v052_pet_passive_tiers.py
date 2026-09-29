async def migrate(connection) -> None:
    await connection.execute(
        """
        CREATE TABLE pet_passive_definitions (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            rarity TEXT NOT NULL CHECK(rarity IN ('common', 'rare', 'ultra_rare')),
            min_bps INTEGER NOT NULL CHECK(min_bps >= 0),
            max_bps INTEGER NOT NULL CHECK(max_bps >= min_bps)
        )
        """
    )
    await connection.executemany(
        "INSERT INTO pet_passive_definitions (id, display_name, rarity, min_bps, max_bps) VALUES (?, ?, ?, ?, ?)",
        (
            ("loyalty_gain", "Loyalty Gain", "common", 1000, 1000),
            ("raid_damage", "Boss Hunt Damage", "common", 1000, 2000),
            ("gamble_odds", "Gamble Luck", "common", 500, 1000),
            ("raid_profit", "Boss Hunt Profit", "common", 1000, 2000),
            ("rare_drop_chance", "Rare Drop Luck", "rare", 100, 500),
            ("kamikaze_odds", "Kamikaze Luck", "rare", 500, 1000),
            ("gamble_loss_refund", "Second Chance", "ultra_rare", 1000, 1000),
        ),
    )
    await connection.execute(
        """
        INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level)
        VALUES ('explosive_rat', 'Explosive Rat', 'common', '/assets/explosive_rat.png', 4, 50)
        """
    )
