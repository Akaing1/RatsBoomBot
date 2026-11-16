import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.channels.live_chat import LiveChatService, YouTubeConnection
from web.shared.live_chat import stream_chat_events


def linked_service():
    service = LiveChatService(None)
    service.connections["owner"] = YouTubeConnection(
        "owner", "youtube-id", "Channel", "access", "refresh", "2099-01-01T00:00:00Z")
    service.youtube_statuses["owner"] = ("live", "Receiving YouTube live-chat messages.")
    service.active_youtube_chat_ids["owner"] = "chat"
    return service


def test_auth_failure_keeps_account_link_but_clears_chat_availability():
    service = linked_service()
    assert service.get_youtube_delivery_state("owner")["receiving"]
    service.require_youtube_reauthorization("owner", "Reconnect YouTube.")
    state = service.get_youtube_delivery_state("owner")
    assert state["linked"]
    assert state["reauth_required"]
    assert not state["receiving"]
    assert "owner" not in service.active_youtube_chat_ids
    assert service.get_youtube_state("owner").connected  # linked-account compatibility
    assert set(state) == {"linked", "receiving", "reauth_required", "status", "detail"}


@pytest.mark.parametrize("status", ["waiting", "error", "unavailable"])
def test_non_live_states_do_not_claim_delivery(status):
    service = linked_service()
    service.youtube_statuses["owner"] = (status, "Not receiving.")
    assert not service.get_youtube_delivery_state("owner")["receiving"]


@pytest.mark.asyncio
async def test_open_feed_reports_auth_failure_and_recovery_without_reload():
    service = linked_service()
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    events = stream_chat_events(request, service, "owner", "commands")
    async def status_event():
        for _ in range(8):
            event = await asyncio.wait_for(anext(events), 1)
            if event.startswith("event: youtube-status"):
                return json.loads(event.split("data: ", 1)[1])
        raise AssertionError("Missing YouTube state")

    try:
        assert (await status_event())["receiving"]
        service.require_youtube_reauthorization("owner", "Reconnect YouTube.")
        service.subscribers["owner"].copy().pop().put_nowait({"event": "chat-preferences"})
        assert (await status_event())["reauth_required"]
        service.youtube_reauth_required.clear()
        service.youtube_statuses["owner"] = ("live", "Receiving.")
        service.active_youtube_chat_ids["owner"] = "new-chat"
        service.subscribers["owner"].copy().pop().put_nowait({"event": "chat-preferences"})
        state = await status_event()
        assert state["receiving"] and not state["reauth_required"]
    finally:
        await events.aclose()
