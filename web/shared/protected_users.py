import logging
import re
import time
from heapq import nsmallest

from bot.profiles import get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


class ProtectedUserError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def get_protected_user_rows(runtime_bot, broadcaster_id: str, *, profile_loader=None) -> list[dict[str, object]]:
    profile_settings = runtime_bot.services.profile_settings
    default_ids = set(profile_settings.get_default_protected_user_ids(broadcaster_id))
    added_users = {user.user_id: user for user in profile_settings.get_added_protected_users(broadcaster_id)}
    resolved_users = {}
    user_ids = sorted(default_ids | set(added_users))
    if profile_loader:
        resolved_users = await profile_loader(runtime_bot, str(broadcaster_id), [{"id": user_id} for user_id in user_ids])
    else:
        for offset in range(0, len(user_ids), 100):
            try:
                users = await runtime_bot.fetch_users(ids=user_ids[offset:offset + 100])
                resolved_users.update((str(user.id), {
                    "login": str(getattr(user, "name", "") or ""),
                    "display_name": str(getattr(user, "display_name", "") or ""),
                    "profile_image_url": str(getattr(getattr(user, "profile_image", None), "url", "") or getattr(user, "profile_image_url", "") or ""),
                }) for user in users)
            except Exception:
                LOGGER.exception("[Profiles] Failed to resolve protected users for broadcaster %s.", broadcaster_id)

    rows = []

    for user_id in user_ids:
        added = added_users.get(user_id)
        resolved = resolved_users.get(user_id, {})
        login = added.login if added is not None else str(resolved.get("login") or "")
        display_name = added.display_name if added is not None else str(resolved.get("display_name") or login or "Unknown user")
        rows.append({
            "user_id": user_id,
            "login": login,
            "display_name": display_name,
            "profile_image_url": str(resolved.get("profile_image_url") or ""),
            "is_default": user_id in default_ids,
            "removable": user_id not in default_ids
        })

    return sorted(rows, key=lambda user: (str(user["display_name"]).casefold(), str(user["user_id"])))


async def user_profile_images(runtime_bot, broadcaster_id, ids, profile_loader):
    user_ids = list(dict.fromkeys(ids.split(','))) if ids else []
    if len(ids) > 2600 or len(user_ids) > 100 or any(not re.fullmatch(r'[0-9]{1,25}', user_id) for user_id in user_ids):
        raise ProtectedUserError('Supply up to 100 valid user IDs.')
    profiles = await profile_loader(runtime_bot, str(broadcaster_id), [{'id': user_id} for user_id in user_ids])
    return {'profiles': [{'id': user_id, 'profile_image_url': str(user.get('profile_image_url') or '')} for user_id, user in profiles.items()]}


async def lookup_protected_user(runtime_bot, broadcaster_id: str, query: str) -> dict[str, object]:
    normalized_login = query.strip().lstrip("@").casefold()

    if not re.fullmatch(r"[a-z0-9_]{3,25}", normalized_login):
        raise ProtectedUserError("Enter a valid Twitch username.")

    try:
        user = await runtime_bot.fetch_user(login=normalized_login)
    except Exception as error:
        LOGGER.exception("[Profiles] Twitch user lookup failed for %s.", normalized_login)
        raise ProtectedUserError("Twitch could not verify that user. Please try again.", 502) from error

    if user is None:
        raise ProtectedUserError(f"Twitch user @{normalized_login} was not found.", 404)

    return protected_user_result(
        runtime_bot, broadcaster_id, str(user.id), str(user.name),
        str(getattr(user, "display_name", None) or user.name),
        str(getattr(getattr(user, "profile_image", None), "url", "") or getattr(user, "profile_image_url", "") or ""),
    )


def protected_user_result(runtime_bot, broadcaster_id, user_id, login, display_name, profile_image_url):
    profile = get_active_profile(str(broadcaster_id))
    automatic = user_id in {str(broadcaster_id), str(runtime_bot.bot_id)}
    return {
        "id": user_id, "login": login, "display_name": display_name,
        "profile_image_url": profile_image_url,
        "already_protected": automatic or (profile is not None and profile.is_user_protected(user_id)),
        "automatic": automatic,
    }


def user_name_similarity(a, b):
    previous = list(range(len(b) + 1))
    for i, char in enumerate(a, 1):
        row = [i]
        for j, other in enumerate(b, 1):
            row.append(min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (char != other)))
        previous = row
    return 1 - previous[-1] / max(len(a), len(b), 1)


def protected_user_match(user, needle):
    names = (str(user["login"]).casefold(), str(user["display_name"]).casefold())
    match = min(0 if name == needle else 1 if name.startswith(needle) else 2 if needle in name else 3 for name in names)
    similarity = max(user_name_similarity(needle, name) for name in names)
    return match, -similarity, names[0], user["id"]


def protected_search_rank(user, needle):
    match = protected_user_match(user, needle)
    priority = 0 if match[0] == 0 else 1 if user.get("related") else 2
    return priority, *match


def cached_protected_user_candidates(runtime_bot, broadcaster_id, needle):
    """Read available relationship data only; never start or refresh a lookup."""
    broadcaster_id = str(broadcaster_id)
    now = time.monotonic()
    candidates = {}
    profiles = getattr(runtime_bot, "_raid_browser_profile_cache", {})

    def include(rows, following=False):
        for row in rows:
            user_id = str(row.get("broadcaster_id" if following else "user_id") or "")
            login = str(row.get("broadcaster_login" if following else "user_login") or "")
            display = str(row.get("broadcaster_name" if following else "user_name") or login)
            if not user_id or not login or user_id in candidates:
                continue
            user = {"id": user_id, "login": login, "display_name": display}
            if needle:
                rank = protected_user_match(user, needle)
                if rank[0] == 3 and rank[1] > -0.6:
                    continue
            cached = profiles.get((broadcaster_id, user_id))
            profile = cached[1] if cached and now - cached[0] < 86400 else None
            candidates[user_id] = protected_user_result(runtime_bot, broadcaster_id, user_id, login, display,
                str((profile or {}).get("profile_image_url") or ""))
            candidates[user_id]["related"] = True

    name_cache = getattr(runtime_bot, "_follower_names_cache", {}).get(broadcaster_id)
    if name_cache:
        include(name_cache["users"].values())
    following_cache = getattr(runtime_bot, "_following_names_cache", {}).get(broadcaster_id)
    if following_cache:
        include(following_cache["users"].values(), following=True)
    snapshot = getattr(runtime_bot, "_followers_directory_cache", {}).get(broadcaster_id)
    if snapshot:
        include(snapshot.get("followers", []))
    for (reader, path, parameters), (cached_at, payload) in getattr(runtime_bot, "_raid_browser_cache", {}).items():
        if reader != broadcaster_id or path not in {"channels/followed", "channels/followers"} or now - cached_at >= 86400:
            continue
        following = path == "channels/followed"
        params = dict(parameters)
        if params.get("user_id" if following else "broadcaster_id") != broadcaster_id:
            continue
        include(payload.get("data", []), following)
    return candidates


async def search_protected_users(runtime_bot, broadcaster_id: str, query: str, *, cached_only: bool = False) -> list[dict[str, object]]:
    needle = query.strip().lstrip("@").casefold()
    if cached_only and not needle:
        return list(cached_protected_user_candidates(runtime_bot, broadcaster_id, "").values())
    minimum = 1 if cached_only else 2
    if not re.fullmatch(rf"[a-z0-9_]{{{minimum},25}}", needle):
        raise ProtectedUserError("Enter at least two characters of a Twitch username.")
    known = cached_protected_user_candidates(runtime_bot, broadcaster_id, "")
    related_ids = set(known)
    candidates = {}
    for user_id, user in known.items():
        match = protected_user_match(user, needle)
        if match[0] < 3 or -match[1] >= 0.6:
            candidates[user_id] = user
    if cached_only:
        return nsmallest(5, candidates.values(), key=lambda user: protected_search_rank(user, needle))
    exact_error = None
    if len(needle) >= 3:
        try:
            exact = await lookup_protected_user(runtime_bot, broadcaster_id, needle)
            exact["related"] = exact["id"] in related_ids
            candidates[exact["id"]] = exact
        except ProtectedUserError as error:
            if error.status_code != 404:
                exact_error = error
    search = getattr(runtime_bot, "search_channels", None)
    if search:
        queries = [needle]
        if len(needle) >= 4:
            queries.append(needle[:max(2, min(5, len(needle) // 2))])
        for term in queries:
            if term != needle and sum(not user.get("related") for user in candidates.values()) >= 5:
                break
            try:
                async for channel in search(term, first=20, max_results=20):
                    user = channel.broadcaster
                    user_id = str(user.id)
                    if user_id not in candidates:
                        candidates[user_id] = protected_user_result(
                            runtime_bot, broadcaster_id, user_id, str(user.name),
                            str(user.display_name or user.name), str(channel.thumbnail.url),
                        )
                        candidates[user_id]["related"] = user_id in related_ids
            except Exception:
                LOGGER.exception("[Profiles] Protected user search failed for %s.", term)
                if not candidates:
                    raise ProtectedUserError("Twitch could not search users. Please try again.", 502)
                break
    if not candidates and exact_error:
        raise exact_error

    related = nsmallest(5, (user for user in candidates.values() if user.get('related')),
        key=lambda user: protected_search_rank(user, needle))
    remote = nsmallest(5, (user for user in candidates.values() if not user.get('related')),
        key=lambda user: protected_search_rank(user, needle))
    return [*related, *remote]


async def add_protected_user(runtime_bot, broadcaster_id: str, user_id: str) -> str:
    if not user_id.isdigit():
        raise ProtectedUserError("Twitch returned an invalid user ID.")

    try:
        users = await runtime_bot.fetch_users(ids=[user_id])
    except Exception as error:
        LOGGER.exception("[Profiles] Twitch user validation failed for %s.", user_id)
        raise ProtectedUserError("Twitch could not verify that user. Please try again.") from error

    user = users[0] if users else None

    if user is None:
        raise ProtectedUserError("That Twitch user no longer exists.")

    resolved_user_id = str(user.id)
    display_name = str(getattr(user, "display_name", None) or user.name)

    if resolved_user_id in {str(broadcaster_id), str(runtime_bot.bot_id)}:
        raise ProtectedUserError("The broadcaster and bot account are already protected automatically.")

    profile = get_active_profile(str(broadcaster_id))

    if profile is not None and profile.is_user_protected(resolved_user_id):
        return f"{display_name} is already protected."

    try:
        await runtime_bot.services.profile_settings.add_protected_user(
            str(broadcaster_id), resolved_user_id, str(user.name), display_name
        )
    except Exception as error:
        LOGGER.exception("[Profiles] Failed to add protected user %s for broadcaster %s.", resolved_user_id, broadcaster_id)
        raise ProtectedUserError("The protected user could not be saved. Please try again.") from error

    return f"{display_name} was added to protected users."


async def remove_protected_user(runtime_bot, broadcaster_id: str, user_id: str) -> str:
    try:
        removed = await runtime_bot.services.profile_settings.remove_protected_user(str(broadcaster_id), user_id)
    except ValueError as error:
        raise ProtectedUserError(str(error)) from error
    except Exception as error:
        LOGGER.exception("[Profiles] Failed to remove protected user %s for broadcaster %s.", user_id, broadcaster_id)
        raise ProtectedUserError("The protected user could not be removed. Please try again.") from error

    if not removed:
        raise ProtectedUserError("That user is not in the protected-user list.")

    return "The user was removed from protected users."
