"""Validated channel-wide chat filters shared by the dashboard and OBS."""

PLATFORM_USERS = {
    "twitch": ("vips", "mods", "subs", "non_subs", "bots"),
    "youtube": ("youtube_mods", "youtube_members", "youtube_non_members", "youtube_bots"),
}
MESSAGE_TYPES = ("commands", "redeems", "messages")


def normalize_chat_preferences(value):
    if not isinstance(value, dict) or set(value) - {"version", "connectedPlatforms", "users", "types", "origin"}:
        raise ValueError("Invalid chat preferences.")
    origin = value.get("origin", "all")
    if origin not in ("all", "local", "shared"):
        raise ValueError("Invalid chat origin.")
    result = {"version": 5, "origin": origin}
    for axis, allowed in (("connectedPlatforms", tuple(PLATFORM_USERS)),
                          ("users", sum(PLATFORM_USERS.values(), ())), ("types", MESSAGE_TYPES)):
        keys = value.get(axis)
        if not isinstance(keys, list) or len(keys) > len(allowed) or any(not isinstance(key, str) or key not in allowed for key in keys):
            raise ValueError(f"Invalid chat {axis}.")
        result[axis] = list(dict.fromkeys(keys))
    return result
