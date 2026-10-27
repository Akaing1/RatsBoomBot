"""Keep follower presence lookups indexed as payout history grows."""


async def migrate(connection):
    await connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_passive_point_payouts_follower_presence
        ON passive_point_payouts (broadcaster_id, user_id, interval_started_at DESC)
    """)
