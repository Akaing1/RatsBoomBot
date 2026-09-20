import asyncio
import json

from bot.services.channels.live_chat import message_matches_view, normalize_chat_view


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

            if message_matches_view(message, view):
                yield f"data: {json.dumps(message.as_dict(), separators=(',', ':'))}\n\n"
    finally:
        service.unsubscribe(broadcaster_id, queue)
