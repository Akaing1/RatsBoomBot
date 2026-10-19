"""Read the public Twitch streamer shelf without account tokens or cookies.

This is an unsupported website query, isolated so failures never prevent the
official Helix-based raid browser from working.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import time

import httpx
from config.settings import settings

LOGGER = logging.getLogger("RatBoomBot")
CACHE_SECONDS = 86400
FAILURE_RETRY_SECONDS = 600
PUBLIC_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
SHELF_QUERY_HASH = "3d9e1494fe4b426aa3ea81ff63dc87e784529a150bdc362c01cdb2c30373440f"


def parse_streamer_shelf(payload, broadcaster_id):
    if isinstance(payload, list):
        if len(payload) != 1:
            raise ValueError("Unexpected shelf response")
        payload = payload[0]
    if not isinstance(payload, dict) or payload.get("errors"):
        raise ValueError("Twitch shelf query failed")
    user = payload.get("data", {}).get("user")
    if not isinstance(user, dict) or str(user.get("id")) != broadcaster_id:
        raise ValueError("Missing or mismatched shelf owner")
    shelf = user.get("channel", {}).get("home", {}).get("shelves", {}).get("streamerShelf")
    if not isinstance(shelf, dict) or not isinstance(shelf.get("edges"), list):
        raise ValueError("Missing streamer shelf")
    result, seen = [], set()
    for edge in shelf["edges"][:1000]:
        node = edge.get("node") if isinstance(edge, dict) else None
        if node is None:
            continue  # A deleted channel may have a null node.
        id_ = str(node.get("id", ""))
        login = str(node.get("login", ""))
        if not re.fullmatch(r"\d{1,25}", id_) or not re.fullmatch(r"[A-Za-z0-9_]{1,25}", login):
            raise ValueError("Invalid suggested channel")
        if id_ not in seen and id_ != broadcaster_id:
            seen.add(id_)
            result.append({"id": id_, "login": login.lower()})
    return result


async def fetch_public_shelf(login):
    # Deliberately use only the public website client ID, never our user's
    # OAuth token, session cookies, integrity tokens, or captured headers.
    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
        response = await client.post("https://gql.twitch.tv/gql",
            headers={"Client-ID": PUBLIC_CLIENT_ID},
            json={"operationName": "HomeShelfUsers", "variables": {"channelLogin": login},
                  "extensions": {"persistedQuery": {"version": 1, "sha256Hash": SHELF_QUERY_HASH}}})
        response.raise_for_status()
        return response.json()


def read_cache(path, broadcaster_id, login):
    try:
        if path.stat().st_size > 256000:
            return None
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("broadcaster_id") != broadcaster_id or entry.get("login") != login:
            return None
        # Validate disk data as strictly as network data.
        channels = parse_streamer_shelf({"data": {"user": {"id": broadcaster_id,
            "channel": {"home": {"shelves": {"streamerShelf": {
                "edges": [{"node": node} for node in entry["channels"]]}}}}}}}, broadcaster_id)
        fetched_at = float(entry["fetched_at"])
        if not 0 < fetched_at <= time.time() + 60:
            return None
        return {"channels": channels, "fetched_at": fetched_at, "retry_at": 0}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def write_cache(path, broadcaster_id, login, entry):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump({"broadcaster_id": broadcaster_id, "login": login,
                       "fetched_at": entry["fetched_at"], "channels": entry["channels"]}, stream)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


async def get_suggested_streamers(runtime_bot, broadcaster_id, login):
    broadcaster_id, login = str(broadcaster_id), str(login or "").lower()
    if not re.fullmatch(r"\d{1,25}", broadcaster_id) or not re.fullmatch(r"[a-z0-9_]{1,25}", login):
        return [], "unavailable"
    state = getattr(runtime_bot, "_raid_suggestions", None)
    if state is None:
        state = runtime_bot._raid_suggestions = {"cache": {}, "locks": {}}
    key = (broadcaster_id, login)
    lock = state["locks"].setdefault(key, asyncio.Lock())
    path = Path(settings.DATABASE_PATH).parent / "raid-suggestions" / f"{broadcaster_id}.json"
    async with lock:
        if key not in state["cache"]:
            state["cache"][key] = await asyncio.to_thread(read_cache, path, broadcaster_id, login) or {
                "channels": [], "fetched_at": 0, "retry_at": 0}
        entry = state["cache"][key]
        now = time.time()
        if entry["fetched_at"] > now - CACHE_SECONDS:
            return entry["channels"], "cached"
        if entry["retry_at"] <= now:
            try:
                channels = parse_streamer_shelf(await fetch_public_shelf(login), broadcaster_id)
                entry = {"channels": channels, "fetched_at": time.time(), "retry_at": 0}
                state["cache"][key] = entry
                try:
                    await asyncio.to_thread(write_cache, path, broadcaster_id, login, entry)
                except OSError:
                    LOGGER.warning("[Raid browser] Suggested streamer cache could not be saved.")
                return channels, "fresh"
            except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
                entry["retry_at"] = now + FAILURE_RETRY_SECONDS
                LOGGER.warning("[Raid browser] Public suggested streamer query unavailable for %s; retaining cached list.", broadcaster_id)
        return entry["channels"], "stale" if entry["fetched_at"] else "unavailable"
