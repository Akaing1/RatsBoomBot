"""Identify messages relayed from another Twitch channel."""


def is_shared_message(payload) -> bool:
    source = getattr(payload, 'source_broadcaster', None)
    return source is not None and str(source.id) != str(payload.broadcaster.id)
