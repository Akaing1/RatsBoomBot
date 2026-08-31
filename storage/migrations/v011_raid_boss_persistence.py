from typing import Any


async def migrate(connection: Any) -> None:
    queries = (
        """
        CREATE TABLE IF NOT EXISTS raid_boss_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcaster_id TEXT NOT NULL,
            boss_name TEXT NOT NULL,
            boss_type TEXT NOT NULL,
            boss_tier TEXT NOT NULL DEFAULT 'main',
            max_hp INTEGER NOT NULL,
            current_hp INTEGER NOT NULL,
            reward_pool INTEGER NOT NULL,
            final_hit_reward INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            spawned_at TEXT NOT NULL,
            stream_limit INTEGER NOT NULL,
            final_hitter_id TEXT,
            final_hitter_name TEXT,
            rewards_paid INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_streams (
            event_id INTEGER NOT NULL,
            stream_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            PRIMARY KEY (event_id, stream_id)
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS raid_boss_one_active_event
        ON raid_boss_events (broadcaster_id)
        WHERE status = 'active'
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_attacks (
            event_id INTEGER NOT NULL,
            broadcaster_id TEXT NOT NULL,
            stream_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            damage INTEGER NOT NULL,
            weapon TEXT,
            potion_used INTEGER NOT NULL DEFAULT 0,
            critical_hit INTEGER NOT NULL DEFAULT 0,
            attacked_at TEXT NOT NULL,
            PRIMARY KEY (event_id, stream_id, user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_players (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            equipped_weapon TEXT,
            potion_attacks_remaining INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (broadcaster_id, user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_inventory (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            durability INTEGER NOT NULL DEFAULT 15,
            PRIMARY KEY (broadcaster_id, user_id, item_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_channel_state (
            broadcaster_id TEXT PRIMARY KEY,
            tutorial_completed INTEGER NOT NULL DEFAULT 0,
            consecutive_mini_bosses INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_reward_summaries (
            event_id INTEGER NOT NULL,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            contribution_points INTEGER NOT NULL DEFAULT 0,
            final_hit_points INTEGER NOT NULL DEFAULT 0,
            bonus_points INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (event_id, user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_reward_items (
            event_id INTEGER NOT NULL,
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            PRIMARY KEY (event_id, user_id, item_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS raid_boss_schedules (
            broadcaster_id TEXT PRIMARY KEY,
            stream_id TEXT NOT NULL,
            boss_tier TEXT,
            boss_type TEXT,
            warning_at TEXT,
            warning_sent INTEGER NOT NULL DEFAULT 0,
            spawn_at TEXT,
            next_reminder_at TEXT,
            reminder_message_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    for query in queries:
        await connection.execute(query)

    await add_column_if_missing(connection, "raid_boss_events", "boss_tier", "TEXT NOT NULL DEFAULT 'main'")
    await add_column_if_missing(connection, "raid_boss_attacks", "weapon", "TEXT")
    await add_column_if_missing(connection, "raid_boss_attacks", "potion_used", "INTEGER NOT NULL DEFAULT 0")
    await add_column_if_missing(connection, "raid_boss_attacks", "critical_hit", "INTEGER NOT NULL DEFAULT 0")
    await add_column_if_missing(connection, "raid_boss_inventory", "durability", "INTEGER NOT NULL DEFAULT 15")
    await add_column_if_missing(connection, "raid_boss_channel_state", "consecutive_mini_bosses", "INTEGER NOT NULL DEFAULT 0")


async def add_column_if_missing(connection: Any, table_name: str, column_name: str, definition: str) -> None:
    columns = await connection.fetchall(f"PRAGMA table_info({table_name})")

    if column_name not in {str(column["name"]) for column in columns}:
        await connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
