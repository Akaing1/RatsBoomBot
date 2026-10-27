"""Read channel-local metrics for verified Twitch followers, in bounded batches."""


async def follower_metrics(db, broadcaster_id, user_ids):
    if not user_ids:
        return {}
    channel_id = str(broadcaster_id)
    result = {}
    async with db.acquire() as connection:
        for start in range(0, len(user_ids), 400):
            batch = user_ids[start:start + 400]
            placeholders = ','.join('(?)' for _ in batch)
            rows = await connection.fetchall(f"""
                WITH target(user_id) AS (VALUES {placeholders}),
                claims AS (
                    SELECT r.user_id, r.redeem_type, COUNT(*) AS total
                    FROM redeem_claims r JOIN target ON target.user_id=r.user_id
                    WHERE r.broadcaster_id=? AND r.redeem_type IN ('first','daily')
                    GROUP BY r.user_id,r.redeem_type
                    UNION ALL
                    SELECT i.user_id,i.redeem_type,i.claim_count
                    -- Keep the small target batch outermost to use both indexed keys.
                    FROM target CROSS JOIN imported_redeem_totals i ON target.user_id=i.user_id
                    WHERE i.broadcaster_id=? AND i.redeem_type IN ('first','daily')
                ), redeem_totals AS (
                    SELECT user_id, SUM(CASE WHEN redeem_type='first' THEN total ELSE 0 END) AS first_redeems,
                        SUM(CASE WHEN redeem_type='daily' THEN total ELSE 0 END) AS check_ins
                    FROM claims GROUP BY user_id
                ), achievements AS (
                    SELECT a.user_id, COUNT(DISTINCT a.achievement_id) AS achievement_count
                    FROM achievement_unlocks a JOIN target ON target.user_id=a.user_id
                    WHERE a.broadcaster_id=? GROUP BY a.user_id
                )
                SELECT target.user_id, COALESCE(v.points,0) AS points,
                    COALESCE(s.messages_sent,0) AS messages,
                    COALESCE(s.lifetime_points_earned,0) AS lifetime_points,
                    COALESCE(w.progress,0) AS watch_minutes,
                    COALESCE(r.first_redeems,0) AS first_redeems,
                    COALESCE(r.check_ins,0) AS check_ins,
                    COALESCE(a.achievement_count,0) AS achievement_count,
                    NULL AS points_spent,
                    o.first_seen_at AS first_seen, o.last_seen_at AS last_seen,
                    (SELECT datetime(MAX(p.interval_started_at),'unixepoch') FROM passive_point_payouts p
                        WHERE p.broadcaster_id=? AND p.user_id=target.user_id) AS last_watched
                FROM target
                LEFT JOIN redeem_totals r ON r.user_id=target.user_id
                LEFT JOIN achievements a ON a.user_id=target.user_id
                LEFT JOIN viewers v ON v.user_id=target.user_id AND v.broadcaster_id=?
                LEFT JOIN chatter_channel_stats s ON s.user_id=target.user_id AND s.broadcaster_id=?
                LEFT JOIN chatter_channel_observations o ON o.user_id=target.user_id AND o.broadcaster_id=?
                LEFT JOIN community_achievement_progress w ON w.user_id=target.user_id
                    AND w.broadcaster_id=? AND w.achievement_id='watch_time'
            """, (*batch, *(channel_id,) * 8))
            result.update((str(row['user_id']), dict(row)) for row in rows)
    return result
