from typing import Any


async def migrate(connection: Any) -> None:
    """
    Remove the complete failed Ahriman test encounter from 2026-08-28.

    Earlier cleanup migrations used the misspelling "Ahirman" and therefore
    could not match the stored boss name.
    """
    await connection.execute(
        """
        CREATE TEMP TABLE IF NOT EXISTS ahriman_test_cleanup_events (
            event_id INTEGER PRIMARY KEY
        )
        """
    )
    await connection.execute("DELETE FROM ahriman_test_cleanup_events")
    await connection.execute(
        """
        INSERT INTO ahriman_test_cleanup_events (event_id)
        SELECT id
        FROM raid_boss_events
        WHERE status = 'failed'
          AND boss_name = 'Ahriman'
          AND DATE(spawned_at) = '2026-08-28'
        """
    )

    for table in ("raid_boss_reward_items", "raid_boss_reward_summaries", "raid_boss_attacks", "raid_boss_streams"):
        await connection.execute(f"DELETE FROM {table} WHERE event_id IN (SELECT event_id FROM ahriman_test_cleanup_events)")

    await connection.execute("DELETE FROM raid_boss_events WHERE id IN (SELECT event_id FROM ahriman_test_cleanup_events)")
    await connection.execute("DROP TABLE ahriman_test_cleanup_events")
