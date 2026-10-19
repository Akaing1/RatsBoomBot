import time


RECENT_RAID_SECONDS = 30 * 86400


async def record_incoming_raid(db, broadcaster_id: str, raider_id: str) -> None:
    async with db.acquire() as connection:
        await connection.execute("""
            INSERT INTO incoming_raid_recency (broadcaster_id, raider_id, received_at)
            VALUES (?, ?, ?)
            ON CONFLICT (broadcaster_id, raider_id)
            DO UPDATE SET received_at = MAX(received_at, excluded.received_at)
        """, (str(broadcaster_id), str(raider_id), time.time()))


async def recent_incoming_raids(db, broadcaster_id: str) -> dict[str, float]:
    if db is None:
        return {}
    now = time.time()
    async with db.acquire() as connection:
        rows = await connection.fetchall("""
            SELECT raider_id, received_at FROM incoming_raid_recency
            WHERE broadcaster_id = ? AND received_at > ? AND received_at <= ?
            ORDER BY received_at DESC LIMIT 100
        """, (str(broadcaster_id), now - RECENT_RAID_SECONDS, now))
    return {str(row["raider_id"]): max(0, 1 - (now - row["received_at"]) / RECENT_RAID_SECONDS) for row in rows}
