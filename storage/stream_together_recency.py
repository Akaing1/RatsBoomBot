import time


RECENT_STREAM_TOGETHER_SECONDS = 3 * 86400
STREAM_TOGETHER_INITIAL_BOOST = 2500
STREAM_TOGETHER_DAY_ONE_BOOST = 1200


async def record_stream_together_participants(db, broadcaster_id: str, participant_ids) -> None:
    now = time.time()
    async with db.acquire() as connection:
        await connection.executemany("""
            INSERT INTO chatter_channel_stats (broadcaster_id, user_id, last_streamed_together_at)
            VALUES (?, ?, ?)
            ON CONFLICT (broadcaster_id, user_id)
            DO UPDATE SET last_streamed_together_at =
                MAX(COALESCE(last_streamed_together_at, 0), excluded.last_streamed_together_at)
        """, [(str(broadcaster_id), str(participant_id), now) for participant_id in participant_ids])


async def recent_stream_together_participants(db, broadcaster_id: str) -> dict[str, float]:
    if db is None:
        return {}
    now = time.time()
    async with db.acquire() as connection:
        rows = await connection.fetchall("""
            SELECT user_id, last_streamed_together_at FROM chatter_channel_stats
            WHERE broadcaster_id = ? AND last_streamed_together_at > ? AND last_streamed_together_at <= ?
            ORDER BY last_streamed_together_at DESC LIMIT 100
        """, (str(broadcaster_id), now - RECENT_STREAM_TOGETHER_SECONDS, now))
    weights = {}
    for row in rows:
        elapsed = now - row["last_streamed_together_at"]
        if elapsed <= 86400:
            boost = STREAM_TOGETHER_INITIAL_BOOST - (
                STREAM_TOGETHER_INITIAL_BOOST - STREAM_TOGETHER_DAY_ONE_BOOST) * elapsed / 86400
        else:
            boost = STREAM_TOGETHER_DAY_ONE_BOOST * (
                RECENT_STREAM_TOGETHER_SECONDS - elapsed) / (RECENT_STREAM_TOGETHER_SECONDS - 86400)
        weights[str(row["user_id"])] = max(0, boost / STREAM_TOGETHER_INITIAL_BOOST)
    return weights
