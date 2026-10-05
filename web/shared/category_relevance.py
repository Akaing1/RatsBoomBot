"""Cached, ID-based IGDB checks for category-picker suggestions."""

import logging
import asyncio
import time
import math

import aiohttp
from config.settings import settings

LOGGER = logging.getLogger("RatBoomBot")
# Conservative starting cutoff for IGDB's popularity values, not player counts.
LOW_POPULARITY_THRESHOLD = 0.00001
INTEREST_TYPES = {2, 3, 4}  # IGDB Want to Play, Playing, Played.


def is_low_relevance(game, interest):
    if game is None:
        return False
    status = str((game.get("game_status") or {}).get("status") or "").casefold()
    # IGDB omits optional counts when a successfully fetched game has no ratings.
    no_ratings = game.get("rating_count", 0) == 0 and game.get("aggregated_rating_count", 0) == 0
    no_artwork = not game.get("cover") and not game.get("artworks")
    no_releases = not game.get("first_release_date") and not game.get("release_dates")
    low_popularity = set(interest) == INTEREST_TYPES and all(
        0 <= score <= LOW_POPULARITY_THRESHOLD for score in interest.values())
    return status == "delisted" or no_artwork or no_ratings or no_releases or low_popularity


async def query_igdb(runtime_bot, session, endpoint, query, headers):
    lock = getattr(runtime_bot, "_dashboard_igdb_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        runtime_bot._dashboard_igdb_lock = lock
    async with lock:
        # IGDB permits four requests per second; serialize and space requests.
        last_request = getattr(runtime_bot, "_dashboard_igdb_last_request", 0)
        await asyncio.sleep(max(0, 0.26 - (time.monotonic() - last_request)))
        runtime_bot._dashboard_igdb_last_request = time.monotonic()
        async with session.post(f"https://api.igdb.com/v4/{endpoint}", headers=headers, data=query) as response:
            response.raise_for_status()
            return await response.json()


async def low_relevance_category_ids(runtime_bot, categories, broadcaster_id):
    http = getattr(runtime_bot, "_http", None)
    client_id = getattr(http, "_client_id", None)
    token = getattr(http, "_app_token", None)
    if not client_id or not token:
        return set()
    now = time.monotonic()
    developing = settings.ENVIRONMENT == "local"
    cache_seconds = 3600 if developing else 86400
    failure_cache_seconds = 60 if developing else 86400
    cache = getattr(runtime_bot, "_dashboard_category_relevance_cache", None)
    if cache is None:
        cache = {}
        runtime_bot._dashboard_category_relevance_cache = cache
    ids = [item["id"] for item in categories]
    missing = [id_ for id_ in ids if id_ not in cache or cache[id_][0] <= now]
    if missing:
        try:
            # Search Categories doesn't provide IGDB IDs; resolve in one batch.
            games = await runtime_bot.fetch_games(ids=missing, token_for=str(broadcaster_id))
            mappings = {str(game.id): str(getattr(game, "igdb_id", "")) for game in games}
            igdb_ids = sorted({id_ for id_ in mappings.values() if id_.isdigit() and int(id_) > 0})
            records = {}
            interests = {}
            if igdb_ids:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                    headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
                    payload = await query_igdb(runtime_bot, session, "games",
                        "fields id,game_status.status,cover,artworks,rating_count,aggregated_rating_count,first_release_date,release_dates.date; "
                        f"where id = ({','.join(igdb_ids)}); limit 100;", headers)
                    records = {str(game["id"]): game for game in payload}
                    try:
                        popularity = await query_igdb(runtime_bot, session, "popularity_primitives",
                            "fields game_id,popularity_type,value,calculated_at; "
                            f"where game_id = ({','.join(igdb_ids)}) & popularity_type = (2,3,4); "
                            "sort calculated_at desc; limit 500;", headers)
                        # A complete successful response with no entries means no
                        # recorded interest, not a failed/unknown lookup. Don't
                        # infer absence if the response may have been truncated.
                        if len(popularity) < 500:
                            interests = {id_: {type_: 0 for type_ in INTEREST_TYPES} for id_ in records}
                        seen = set()
                        for entry in popularity:
                            key = (str(entry["game_id"]), entry["popularity_type"])
                            if key in seen:
                                continue
                            seen.add(key)
                            # Old snapshots don't establish low current interest.
                            if entry.get("calculated_at", 0) < time.time() - 7 * 86400:
                                interests.setdefault(key[0], {})[key[1]] = float("nan")
                                continue
                            score = float(entry["value"])
                            interests.setdefault(key[0], {})[key[1]] = score if math.isfinite(score) else float("nan")
                    except Exception:
                        interests = {}
                        LOGGER.warning("[Dashboard] Category popularity unavailable; keeping uncertain results visible.")
            for id_ in missing:
                igdb_id = mappings.get(id_, "")
                cache[id_] = (now + cache_seconds, is_low_relevance(records.get(igdb_id), interests.get(igdb_id, {})))
        except Exception:
            LOGGER.warning("[Dashboard] Category status lookup unavailable; keeping results visible.")
            for id_ in missing:
                cache[id_] = (now + failure_cache_seconds, False)
    # Bound the cache even when many different searches are made.
    if len(cache) > 5000:
        for id_ in list(cache):
            if id_ not in ids:
                del cache[id_]
            if len(cache) <= 4000:
                break
    return {id_ for id_ in ids if cache.get(id_, (0, False))[1]}
