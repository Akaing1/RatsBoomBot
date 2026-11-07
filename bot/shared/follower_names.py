"""Channel-scoped follower names for instant dashboard user suggestions."""
import asyncio
import logging
import time

from twitchio.http import Route

LOGGER = logging.getLogger("RatBoomBot")


def follower_names_state(bot, channel_id):
    channel_id = str(channel_id)
    cache = getattr(bot, "_follower_names_cache", None)
    if cache is None:
        cache = bot._follower_names_cache = {}
    return cache.setdefault(channel_id, {"users": {}, "loaded": False, "task": None, "retry_at": 0})


def remember_follower(bot, channel_id, user, followed_at=None):
    state = follower_names_state(bot, channel_id)
    user_id = str(user.id)
    entry = {"user_id": user_id, "user_login": str(user.name or ""),
        "user_name": str(getattr(user, "display_name", None) or user.name),
        "followed_at": followed_at.isoformat() if hasattr(followed_at, "isoformat") else followed_at}
    state["users"][user_id] = entry
    snapshot = getattr(bot, "_followers_directory_cache", {}).get(str(channel_id))
    if snapshot is not None:
        members = {str(row["user_id"]): row for row in snapshot["followers"]}
        added = user_id not in members
        members[user_id] = entry
        snapshot.update(followers=list(members.values()), follower_ids=set(members),
            loaded=len(members), total=max(snapshot["total"] + int(added), len(members)))


def ensure_follower_names(bot, channel_id):
    """Start one background load per channel; dashboard rendering never waits."""
    channel_id = str(channel_id)
    state = follower_names_state(bot, channel_id)
    if state["loaded"] or (state["task"] and not state["task"].done()) or time.monotonic() < state["retry_at"]:
        return
    snapshot = getattr(bot, "_followers_directory_cache", {}).get(channel_id)
    if snapshot and snapshot.get("refreshed") and not snapshot.get("loading") and not snapshot.get("error"):
        state["users"] = {**{str(row["user_id"]): row for row in snapshot["followers"]}, **state["users"]}
        state["loaded"] = True
        state.setdefault("refreshed", snapshot["refreshed"])
        return

    directory_task = snapshot.get("task") if snapshot and snapshot.get("loading") else None

    async def load():
        try:
            if directory_task:
                await asyncio.shield(directory_task)
                if not snapshot.get("error"):
                    state["users"] = {**{str(row["user_id"]): row for row in snapshot["followers"]}, **state["users"]}
                    state["loaded"] = True
                    state["refreshed"] = time.monotonic()
                    return
            cursor = None
            cursors = set()
            while True:
                params = {"broadcaster_id": channel_id, "first": 100}
                if cursor:
                    params["after"] = cursor
                payload = await asyncio.wait_for(bot._http.request_json(Route("GET", "channels/followers", token_for=channel_id, params=params)), 20)
                if payload.get("total") and not payload.get("data") and not cursor:
                    raise ValueError("Twitch did not return follower names; reconnect with follower access.")
                for row in payload.get("data", []):
                    # A newer follow event takes priority over the initial snapshot.
                    state["users"].setdefault(str(row["user_id"]), row)
                directory = getattr(bot, "_followers_directory_cache", {}).get(channel_id)
                if directory is not None and directory.get("loading") and not directory.get("refreshed"):
                    directory.update(followers=list(state["users"].values()), follower_ids=set(state["users"]),
                        loaded=len(state["users"]), total=max(int(payload.get("total", 0)), len(state["users"])))
                cursor = payload.get("pagination", {}).get("cursor")
                if not cursor:
                    state["loaded"] = True
                    state["refreshed"] = time.monotonic()
                    break
                if cursor in cursors:
                    raise ValueError("Twitch returned a repeated follower page.")
                cursors.add(cursor)
        except asyncio.CancelledError:
            raise
        except Exception:
            state["retry_at"] = time.monotonic() + 60
            LOGGER.warning("[Followers] Could not preload follower names for %s.", channel_id, exc_info=True)
    state["task"] = asyncio.create_task(load(), name=f"follower-names-{channel_id}")


def ensure_following_names(bot, channel_id, request):
    """Preload followed-channel names once, using the caller's shared request cache."""
    channel_id = str(channel_id)
    cache = getattr(bot, '_following_names_cache', None)
    if cache is None:
        cache = bot._following_names_cache = {}
    state = cache.setdefault(channel_id, {'users': {}, 'loaded': False, 'task': None, 'retry_at': 0})
    if state['loaded'] or (state['task'] and not state['task'].done()) or time.monotonic() < state['retry_at']:
        return

    async def load():
        try:
            cursor = None
            cursors = set()
            while True:
                params = {'user_id': channel_id, 'first': 100}
                if cursor:
                    params['after'] = cursor
                payload = await asyncio.wait_for(request(params), 20)
                if payload.get('total') and not payload.get('data') and not cursor:
                    raise ValueError('Twitch did not return followed channels; reconnect with following access.')
                for row in payload.get('data', []):
                    state['users'][str(row['broadcaster_id'])] = row
                cursor = payload.get('pagination', {}).get('cursor')
                if not cursor:
                    state['loaded'] = True
                    break
                if cursor in cursors:
                    raise ValueError('Twitch returned a repeated following page.')
                cursors.add(cursor)
        except asyncio.CancelledError:
            raise
        except Exception:
            state['retry_at'] = time.monotonic() + 60
            LOGGER.warning('[Followers] Could not preload followed-channel names for %s.', channel_id, exc_info=True)
    state['task'] = asyncio.create_task(load(), name=f'following-names-{channel_id}')
