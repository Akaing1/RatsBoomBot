from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute("ALTER TABLE raid_boss_flag_bearers ADD COLUMN stream_id TEXT NOT NULL DEFAULT ''")
    # Preserve activated flags in their original stream. Unknown reservations
    # remain unscoped and expire rather than carrying into a later stream.
    await connection.execute(
        """
        UPDATE raid_boss_flag_bearers AS flags
        SET stream_id = COALESCE((
            SELECT attacks.stream_id FROM raid_boss_attacks AS attacks
            WHERE attacks.event_id = flags.event_id
              AND attacks.user_id = flags.user_id
              AND attacks.buff_used = 'flag_bearer'
            ORDER BY attacks.attacked_at DESC LIMIT 1
        ), '')
        """
    )
