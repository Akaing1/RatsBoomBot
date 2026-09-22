import logging
import re

from bot.profiles import get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


class ProtectedUserError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def get_protected_user_rows(runtime_bot, broadcaster_id: str) -> list[dict[str, object]]:
    profile_settings = runtime_bot.services.profile_settings
    default_ids = set(profile_settings.get_default_protected_user_ids(broadcaster_id))
    added_users = {user.user_id: user for user in profile_settings.get_added_protected_users(broadcaster_id)}
    resolved_defaults = {}

    if default_ids:
        try:
            resolved_defaults = {str(user.id): user for user in await runtime_bot.fetch_users(ids=sorted(default_ids))}
        except Exception:
            LOGGER.exception("[Profiles] Failed to resolve default protected users for broadcaster %s.", broadcaster_id)

    rows = []

    for user_id in sorted(default_ids | set(added_users)):
        added = added_users.get(user_id)
        resolved = resolved_defaults.get(user_id)
        login = added.login if added is not None else str(getattr(resolved, "name", "") or "")
        display_name = added.display_name if added is not None else str(getattr(resolved, "display_name", "") or login or "Unknown user")
        rows.append({
            "user_id": user_id,
            "login": login,
            "display_name": display_name,
            "is_default": user_id in default_ids,
            "removable": user_id not in default_ids
        })

    return sorted(rows, key=lambda user: (str(user["display_name"]).casefold(), str(user["user_id"])))


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

    user_id = str(user.id)
    profile = get_active_profile(str(broadcaster_id))
    automatically_protected = user_id in {str(broadcaster_id), str(runtime_bot.bot_id)}
    already_protected = automatically_protected or (profile is not None and profile.is_user_protected(user_id))
    return {
        "id": user_id,
        "login": str(user.name),
        "display_name": str(getattr(user, "display_name", None) or user.name),
        "already_protected": already_protected,
        "automatic": automatically_protected
    }


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
