import asqlite
import pytest

from storage.migrations.v011_raid_boss_persistence import migrate as migrate_raid_boss_persistence
from storage.migrations.v014_remove_test_raid_records import migrate as migrate_remove_test_raid_records
from storage.migrations.v018_remove_ahriman_test_run import migrate as migrate_remove_ahriman_test_run


async def seed_event(connection, event_id: int, boss_name: str, spawned_at: str, damage: int) -> None:
    await connection.execute(
        """
        INSERT INTO raid_boss_events (
            id, broadcaster_id, boss_name, boss_type, max_hp, current_hp, reward_pool,
            final_hit_reward, status, spawned_at, stream_limit
        )
        VALUES (?, 'test-channel', ?, 'melee', 10000, 1000, 5000, 500, 'failed', ?, 3)
        """,
        (event_id, boss_name, spawned_at)
    )
    await connection.execute("INSERT INTO raid_boss_streams (event_id, stream_id, started_at) VALUES (?, ?, ?)", (event_id, f"stream-{event_id}", spawned_at))
    await connection.execute(
        "INSERT INTO raid_boss_attacks (event_id, broadcaster_id, stream_id, user_id, username, damage, attacked_at) VALUES (?, 'test-channel', ?, 'user-1', 'tester', ?, ?)",
        (event_id, f"stream-{event_id}", damage, spawned_at)
    )
    await connection.execute("INSERT INTO raid_boss_reward_summaries (event_id, broadcaster_id, user_id, username) VALUES (?, 'test-channel', 'user-1', 'tester')", (event_id,))
    await connection.execute("INSERT INTO raid_boss_reward_items (event_id, broadcaster_id, user_id, item_id) VALUES (?, 'test-channel', 'user-1', 'sword')", (event_id,))


@pytest.mark.asyncio
async def test_remove_test_raid_records_migration_only_removes_exact_encounters(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "raid-cleanup.db")) as database:
        async with database.acquire() as connection:
            await migrate_raid_boss_persistence(connection)
            await seed_event(connection, 1, "Ahirman", "2026-08-28T12:00:00+00:00", 402)
            await seed_event(connection, 2, "Training Golem", "2026-08-27T12:00:00+00:00", 1938)
            await seed_event(connection, 3, "Training Golem", "2026-08-27T13:00:00+00:00", 2497)
            await seed_event(connection, 4, "Training Golem", "2026-08-27T14:00:00+00:00", 2000)
            await seed_event(connection, 5, "Ahirman", "2026-08-29T12:00:00+00:00", 402)

            await migrate_remove_test_raid_records(connection)
            await migrate_remove_test_raid_records(connection)

            events = await connection.fetchall("SELECT id FROM raid_boss_events ORDER BY id")

            assert [int(event["id"]) for event in events] == [4, 5]

            for table in ("raid_boss_reward_items", "raid_boss_reward_summaries", "raid_boss_attacks", "raid_boss_streams"):
                rows = await connection.fetchall(f"SELECT event_id FROM {table} ORDER BY event_id")
                assert [int(row["event_id"]) for row in rows] == [4, 5]



@pytest.mark.asyncio
async def test_remove_ahriman_test_run_removes_correctly_spelled_event_and_dependencies(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "ahriman-cleanup.db")) as database:
        async with database.acquire() as connection:
            await migrate_raid_boss_persistence(connection)
            await seed_event(connection, 1, "Ahriman", "2026-08-28T12:00:00+00:00", 634)
            await seed_event(connection, 2, "Ahriman", "2026-08-29T12:00:00+00:00", 634)
            await seed_event(connection, 3, "Ahirman", "2026-08-28T12:00:00+00:00", 634)

            await migrate_remove_ahriman_test_run(connection)
            await migrate_remove_ahriman_test_run(connection)

            events = await connection.fetchall("SELECT id FROM raid_boss_events ORDER BY id")

            assert [int(event["id"]) for event in events] == [2, 3]

            for table in ("raid_boss_reward_items", "raid_boss_reward_summaries", "raid_boss_attacks", "raid_boss_streams"):
                rows = await connection.fetchall(f"SELECT event_id FROM {table} ORDER BY event_id")
                assert [int(row["event_id"]) for row in rows] == [2, 3]
