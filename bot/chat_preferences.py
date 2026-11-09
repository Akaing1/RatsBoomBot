"""Validated channel-wide chat filters shared by the dashboard and OBS."""

PLATFORM_USERS = {
    "twitch": ("vips", "mods", "subs", "non_subs", "bots"),
    "youtube": ("youtube_mods", "youtube_members", "youtube_non_members", "youtube_bots"),
}
MESSAGE_TYPES = ("commands", "redeems", "messages", "gifs")


def normalize_chat_preferences(value):
    if not isinstance(value, dict) or set(value) - {"version", "connectedPlatforms", "users", "types", "origin", "channels"}:
        raise ValueError("Invalid chat preferences.")
    origin = value.get("origin", "all")
    if origin not in ("all", "local", "shared"):
        raise ValueError("Invalid chat origin.")
    channels = value.get("channels", {})
    if (not isinstance(channels, dict) or len(channels) > 100
            or any(not isinstance(key, str) or (key != "local" and (not key.isascii() or not key.isdigit() or len(key) > 25))
                   or not isinstance(enabled, bool) for key, enabled in channels.items())):
        raise ValueError("Invalid chat channels.")
    result = {"version": 7, "origin": origin, "channels": dict(channels)}
    for axis, allowed in (("connectedPlatforms", tuple(PLATFORM_USERS)),
                          ("users", sum(PLATFORM_USERS.values(), ())), ("types", MESSAGE_TYPES)):
        keys = value.get(axis)
        if not isinstance(keys, list) or len(keys) > len(allowed) or any(not isinstance(key, str) or key not in allowed for key in keys):
            raise ValueError(f"Invalid chat {axis}.")
        result[axis] = list(dict.fromkeys(keys))
    version = value.get('version', 0)
    if not isinstance(version, int):
        version = 0
    additions = []
    if version < 7 and 'messages' in result['types']:
        additions.append('gifs')
    result['types'] = list(dict.fromkeys([*result['types'], *additions]))
    return result
