from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS raid_boss_flag_bearers (
            event_id INTEGER PRIMARY KEY,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            charges_remaining INTEGER NOT NULL DEFAULT 0,
            activated INTEGER NOT NULL DEFAULT 0,
            purchased_at TEXT NOT NULL,
            activated_at TEXT
        )
        """
    )
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS raid_boss_bonus_contributions (
            event_id INTEGER NOT NULL,
            stream_id TEXT NOT NULL,
            attacker_user_id TEXT NOT NULL,
            attack_number INTEGER NOT NULL,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            damage INTEGER NOT NULL,
            PRIMARY KEY (event_id, stream_id, attacker_user_id, attack_number)
        )
        """
    )
    await connection.execute("DROP VIEW IF EXISTS raid_boss_contributions")
    await connection.execute(
        """
        CREATE VIEW raid_boss_contributions AS
        SELECT event_id, broadcaster_id, stream_id, user_id, username, damage FROM raid_boss_attacks
        UNION ALL
        SELECT event_id, broadcaster_id, stream_id, user_id, username, damage FROM raid_boss_bonus_contributions
        """
    )
