from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS raid_boss_test_cleanup_events (
            event_id INTEGER PRIMARY KEY
        )
        """
    )
    await connection.execute("DELETE FROM raid_boss_test_cleanup_events")
    await connection.execute(
        """
        INSERT INTO raid_boss_test_cleanup_events (event_id)
        SELECT events.id
        FROM raid_boss_events AS events
        WHERE events.status = 'failed'
          AND (
              (
                  events.boss_name = 'Ahirman'
                  AND DATE(events.spawned_at) = '2026-08-28'
                  AND EXISTS (
                      SELECT 1
                      FROM raid_boss_attacks AS attacks
                      WHERE attacks.event_id = events.id
                      GROUP BY attacks.user_id
                      HAVING SUM(attacks.damage) = 402
                  )
              )
              OR
              (
                  events.boss_name = 'Training Golem'
                  AND DATE(events.spawned_at) = '2026-08-27'
                  AND EXISTS (
                      SELECT 1
                      FROM raid_boss_attacks AS attacks
                      WHERE attacks.event_id = events.id
                      GROUP BY attacks.user_id
                      HAVING SUM(attacks.damage) IN (1938, 2497)
                  )
              )
          )
        """
    )

    for table in ("raid_boss_reward_items", "raid_boss_reward_summaries", "raid_boss_attacks", "raid_boss_streams"):
        await connection.execute(f"DELETE FROM {table} WHERE event_id IN (SELECT event_id FROM raid_boss_test_cleanup_events)")

    await connection.execute("DELETE FROM raid_boss_events WHERE id IN (SELECT event_id FROM raid_boss_test_cleanup_events)")
    await connection.execute("DROP TABLE raid_boss_test_cleanup_events")
