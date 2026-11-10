"""Chronological clip pages over Twitch's popularity-ordered API."""
from datetime import datetime, timedelta, timezone


async def latest_clips(fetch, channel, days, after):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    floor = now.replace(minute=0, second=0) - timedelta(days=days) if days else datetime(2016, 1, 1, tzinfo=timezone.utc)
    end = datetime.fromisoformat(after) if after else now
    if end.tzinfo is None or end > now or end < floor:
        raise ValueError("Invalid cursor")
    # Complete a recent interval before returning any rows; otherwise popularity
    # pagination could hide a newer clip on a later upstream page.
    start = max(floor, end - timedelta(days=7))
    for _ in range(24):
        payload = await fetch({"broadcaster_id": channel, "first": 100,
                               "started_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "ended_at": end.strftime("%Y-%m-%dT%H:%M:%SZ")})
        if not payload.get("pagination", {}).get("cursor"):
            if not payload.get("data") and start > floor:
                end = start
                start = max(floor, end - timedelta(days=30))
                continue
            rows = sorted(payload.get("data", []), key=lambda row: row["created_at"], reverse=True)
            return {"data": rows, "pagination": {"cursor": start.isoformat() if start > floor else ""}}
        seconds = int((end - start).total_seconds())
        if seconds <= 1:
            raise RuntimeError("Clip interval is too dense to order safely")
        start = end - timedelta(seconds=max(1, seconds // 2))
    return {"data": [], "pagination": {"cursor": end.isoformat()}}
