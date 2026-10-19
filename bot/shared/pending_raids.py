"""Shared outgoing raid state for dashboard, commands, and Twitch events."""

import asyncio
from datetime import UTC, datetime


def raid_state(bot):
    if not hasattr(bot, "_dashboard_pending_raids"):
        bot._dashboard_pending_raids = {}
    if not hasattr(bot, "_dashboard_raid_locks"):
        bot._dashboard_raid_locks = {}
    return bot._dashboard_pending_raids


def raid_lock(bot, broadcaster_id):
    raid_state(bot)
    return bot._dashboard_raid_locks.setdefault(str(broadcaster_id), asyncio.Lock())


def raid_viewer_count(bot, broadcaster_id):
    channels = getattr(getattr(bot, "services", None), "broadcasters", None)
    broadcaster = channels.get_broadcasters().get(str(broadcaster_id)) if channels else None
    count = getattr(broadcaster, "viewer_count", None)
    return count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None


def remember_raid(bot, broadcaster_id, target, created_at=None):
    state = raid_state(bot)
    broadcaster_id, target_id = str(broadcaster_id), str(target.id)
    created = created_at if isinstance(created_at, datetime) else datetime.now(UTC)
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    profile_image = str(getattr(getattr(target, "profile_image", None), "url", "")
                        or getattr(target, "profile_image_url", "") or "")
    existing = state.get(broadcaster_id)
    # The API response and moderation event describe the same start. Do not
    # restart its countdown when the second notification arrives.
    if existing and existing["target_id"] == target_id and abs(
        datetime.fromisoformat(existing["created_at"]).timestamp() - created.timestamp()
    ) < 10:
        if profile_image and not existing.get("profile_image_url"):
            existing["profile_image_url"] = profile_image
        return existing
    login = str(getattr(target, "name", None) or getattr(target, "login", ""))
    raid = {"target_id": target_id, "login": login,
            "display_name": str(getattr(target, "display_name", None) or login),
            "profile_image_url": profile_image,
            "created_at": created.isoformat(), "expires_at": created.timestamp() + 90,
            "viewer_count": raid_viewer_count(bot, broadcaster_id)}
    state[broadcaster_id] = raid
    return raid
