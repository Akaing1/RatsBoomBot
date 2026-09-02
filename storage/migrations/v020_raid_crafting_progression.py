from typing import Any


async def migrate(connection: Any) -> None:
    columns = {str(row["name"]) for row in await connection.fetchall("PRAGMA table_info(raid_boss_attacks)")}

    if "attack_number" not in columns:
        await connection.execute("ALTER TABLE raid_boss_attacks RENAME TO raid_boss_attacks_legacy")
        await connection.execute(
            """
            CREATE TABLE raid_boss_attacks (
                event_id INTEGER NOT NULL, broadcaster_id TEXT NOT NULL, stream_id TEXT NOT NULL,
                user_id TEXT NOT NULL, username TEXT NOT NULL, attack_number INTEGER NOT NULL DEFAULT 1,
                damage INTEGER NOT NULL, weapon TEXT, potion_used INTEGER NOT NULL DEFAULT 0,
                critical_hit INTEGER NOT NULL DEFAULT 0, buff_used TEXT, blessing_active INTEGER NOT NULL DEFAULT 0,
                weapon_shattered INTEGER NOT NULL DEFAULT 0, attacked_at TEXT NOT NULL,
                PRIMARY KEY (event_id, stream_id, user_id, attack_number)
            )
            """
        )
        await connection.execute(
            """
            INSERT INTO raid_boss_attacks (event_id, broadcaster_id, stream_id, user_id, username, damage, weapon, potion_used, critical_hit, attacked_at)
            SELECT event_id, broadcaster_id, stream_id, user_id, username, damage, weapon, potion_used, critical_hit, attacked_at
            FROM raid_boss_attacks_legacy
            """
        )
        await connection.execute("DROP TABLE raid_boss_attacks_legacy")

    player_columns = {str(row["name"]) for row in await connection.fetchall("PRAGMA table_info(raid_boss_players)")}

    for name in ("second_wind_charges", "berserk_charges"):
        if name not in player_columns:
            await connection.execute(f"ALTER TABLE raid_boss_players ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")

    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS raid_boss_stream_effects (
            broadcaster_id TEXT NOT NULL, stream_id TEXT NOT NULL,
            blessing_user_id TEXT NOT NULL, blessing_username TEXT NOT NULL, purchased_at TEXT NOT NULL,
            PRIMARY KEY (broadcaster_id, stream_id)
        )
        """
    )
    mappings = (("sword", "basic_sword"), ("bow", "basic_bow"), ("spellbook", "apprentice_tome"))

    for old, new in mappings:
        await connection.execute(
            """
            INSERT INTO raid_boss_inventory (broadcaster_id, user_id, item_id, quantity, durability)
            SELECT broadcaster_id, user_id, ?, quantity, durability FROM raid_boss_inventory WHERE item_id = ?
            ON CONFLICT(broadcaster_id, user_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (new, old)
        )
        await connection.execute("DELETE FROM raid_boss_inventory WHERE item_id = ?", (old,))
        await connection.execute("UPDATE raid_boss_players SET equipped_weapon = ? WHERE equipped_weapon = ?", (new, old))
