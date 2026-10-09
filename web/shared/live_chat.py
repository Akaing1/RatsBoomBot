import asyncio
import json
from datetime import UTC, datetime, timedelta

from bot.services.channels.live_chat import message_matches_view, normalize_chat_view


def clear_stale_chat_on_refresh(service, broadcaster, *, now=None):
    """Only a page load, after a confirmed hour offline, clears combined history."""
    offline_since = getattr(broadcaster, "offline_since", None)
    if getattr(broadcaster, "is_live", False) or offline_since is None:
        return False
    if (now or datetime.now(UTC)) - offline_since < timedelta(hours=1):
        return False
    service.clear_chat(str(broadcaster.id), platform="both")
    return True


async def stream_chat_events(request, service, broadcaster_id: str, view: str):
    broadcaster_id = str(broadcaster_id)
    view = normalize_chat_view(view)
    queue = service.subscribe(broadcaster_id)

    try:
        yield "retry: 2000\n\n"

        for message in service.history(broadcaster_id, view):
            yield f"data: {json.dumps(message, separators=(',', ':'))}\n\n"

        yield "event: history-complete\ndata: {}\n\n"

        while not await request.is_disconnected():
            try:
                message = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue

            if isinstance(message, dict) and message.get("event") == "chat-clear":
                yield f"event: chat-clear\ndata: {json.dumps(message, separators=(',', ':'))}\n\n"
            elif message_matches_view(message, view):
                yield f"data: {json.dumps(message.as_dict(), separators=(',', ':'))}\n\n"
    finally:
        service.unsubscribe(broadcaster_id, queue)
