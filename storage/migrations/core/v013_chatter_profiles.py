from typing import Any


async def migrate(connection: Any) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chatter_channel_stats (
            broadcaster_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            messages_sent INTEGER NOT NULL DEFAULT 0,
            lifetime_points_earned INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (broadcaster_id, user_id)
        )
        """
    )
    await connection.execute(
        """
        INSERT INTO chatter_channel_stats (broadcaster_id, user_id, messages_sent, lifetime_points_earned)
        SELECT observations.broadcaster_id,
               observations.user_id,
               COALESCE(viewers.messages, 0),
               MAX(COALESCE(viewers.points, 0), 0)
        FROM chatter_channel_observations AS observations
        LEFT JOIN viewers
          ON viewers.broadcaster_id = observations.broadcaster_id
         AND viewers.user_id = observations.user_id
        ON CONFLICT(broadcaster_id, user_id) DO NOTHING
        """
    )
    await connection.execute(
        """
        INSERT INTO chatter_channel_stats (broadcaster_id, user_id, messages_sent, lifetime_points_earned)
        SELECT viewers.broadcaster_id, viewers.user_id, viewers.messages, MAX(viewers.points, 0)
        FROM viewers
        WHERE EXISTS (SELECT 1 FROM chatter_identities WHERE chatter_identities.user_id = viewers.user_id)
        ON CONFLICT(broadcaster_id, user_id) DO NOTHING
        """
    )
    await connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chatter_channel_stats_user
        ON chatter_channel_stats (user_id)
        """
    )
