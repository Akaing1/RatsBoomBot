from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS remaining_ahirman_test_cleanup_events (
            event_id INTEGER PRIMARY KEY
        )
        """
    )
    await connection.execute("DELETE FROM remaining_ahirman_test_cleanup_events")
    await connection.execute(
        """
        INSERT INTO remaining_ahirman_test_cleanup_events (event_id)
        SELECT events.id
        FROM raid_boss_events AS events
        WHERE events.status = 'failed'
          AND events.boss_name = 'Ahirman'
          AND DATE(events.spawned_at) = '2026-08-28'
          AND (
              SELECT COALESCE(SUM(attacks.damage), 0)
              FROM raid_boss_attacks AS attacks
              WHERE attacks.event_id = events.id
          ) = 634
        """
    )

    for table in ("raid_boss_reward_items", "raid_boss_reward_summaries", "raid_boss_attacks", "raid_boss_streams"):
        await connection.execute(f"DELETE FROM {table} WHERE event_id IN (SELECT event_id FROM remaining_ahirman_test_cleanup_events)")

    await connection.execute("DELETE FROM raid_boss_events WHERE id IN (SELECT event_id FROM remaining_ahirman_test_cleanup_events)")
    await connection.execute("DROP TABLE remaining_ahirman_test_cleanup_events")
