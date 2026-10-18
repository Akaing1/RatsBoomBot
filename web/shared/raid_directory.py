"""Source-ordered public directory pages for sorts Helix cannot provide."""

import json
import re
import time

import httpx
from web.shared.raid_suggestions import PUBLIC_CLIENT_ID

DIRECTORY_SORTS = {"viewers_asc": "VIEWER_COUNT_ASC", "viewers_desc": "VIEWER_COUNT", "uptime_asc": "RECENT"}
FIELDS = "edges { cursor node { broadcaster { id } } } pageInfo { hasNextPage }"


async def get_sorted_directory(runtime_bot, *, sort, after="", category_id="", language="", tags=(), tag_match="any"):
    options = {"sort": DIRECTORY_SORTS[sort]}
    if language and language != "other":
        options["languages"] = [language if category_id else language.upper()]
    # Twitch applies ALL semantics to multiple tags. ANY callers can merge
    # separate single-tag first pages instead of accidentally requiring all.
    if tags and (tag_match == "all" or len(tags) == 1):
        options["freeformTags"] = list(tags)
    if category_id:
        query = ("query RaidBrowserDirectory($first:Int!, $after:Cursor, $options:GameStreamOptions, $category:ID!) "
                 "{ game(id:$category) { streams(first:$first,after:$after,options:$options) { " + FIELDS + " } } }")
    else:
        query = ("query RaidBrowserDirectory($first:Int!, $after:Cursor, $options:StreamOptions) "
                 "{ streams(first:$first,after:$after,options:$options) { " + FIELDS + " } }")
    variables = {"first": 30, "after": after or None, "options": options}
    if category_id:
        variables["category"] = category_id
    key = json.dumps(variables, sort_keys=True)
    cache = getattr(runtime_bot, "_raid_directory_cache", None)
    if cache is None:
        cache = runtime_bot._raid_directory_cache = {}
    now = time.monotonic()
    if key in cache and cache[key][0] > now:
        return cache[key][1]
    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
        response = await client.post("https://gql.twitch.tv/gql",
            headers={"Client-ID": PUBLIC_CLIENT_ID}, json={"query": query, "variables": variables})
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("errors"):
        raise ValueError("Twitch directory sorting is temporarily unavailable.")
    data = payload.get("data") or {}
    connection = (data.get("game") or {}).get("streams") if category_id else data.get("streams")
    if not isinstance(connection, dict) or not isinstance(connection.get("edges"), list):
        raise ValueError("Twitch directory sorting is temporarily unavailable.")
    ids = []
    for edge in connection["edges"]:
        node = edge.get("node") or {}
        id_ = str((node.get("broadcaster") or {}).get("id") or "")
        if re.fullmatch(r"\d{1,25}", id_) and id_ not in ids:
            ids.append(id_)
    edges = connection["edges"]
    cursor = str(edges[-1].get("cursor") or "") if edges and (connection.get("pageInfo") or {}).get("hasNextPage") else ""
    if len(cursor) > 500:
        raise ValueError("Invalid Twitch directory cursor.")
    result = {"ids": ids, "cursor": cursor}
    cache[key] = (now + 60, result)
    if len(cache) > 256:
        for previous in list(cache)[:64]:
            if previous != key:
                del cache[previous]
    return result
