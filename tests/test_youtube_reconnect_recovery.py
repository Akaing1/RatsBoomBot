import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import grpc
import pytest

from bot.services.channels import youtube_live_chat_pb2
from bot.services.channels.live_chat import LiveChatService


@pytest.mark.parametrize("prefix,message", [
    ("!", "!"), ("!", "!   "), ("!", " !"), ("!!", "!!"), ("?", "?\t"),
])
def test_prefix_only_youtube_message_does_not_block_batch(monkeypatch, prefix, message):
    monkeypatch.setattr("bot.services.channels.live_chat.settings.PREFIX", prefix)
    service = LiveChatService(None)
    service._publish_youtube_items("channel", [
        {"id": "prefix", "snippet": {"displayMessage": message}},
        {"id": "following", "snippet": {"displayMessage": "hello"}},
    ])
    history = service.history("channel")
    assert len(history) == 2
    assert {entry["kind"] for entry in history} == {"chat"}
    assert {entry["message"] for entry in history} == {message.strip(), "hello"}


@pytest.mark.asyncio
async def test_polling_handoff_keeps_chat_available_without_discovery_delay(monkeypatch):
    service = LiveChatService(None)
    service.started = True
    service.connections["channel"] = SimpleNamespace()
    service._find_active_live_chat = AsyncMock(return_value="chat")
    attempts = []

    async def stream(broadcaster, chat):
        assert service.active_youtube_chat_ids[broadcaster] == chat
        assert service.youtube_statuses[broadcaster][0] == "live"
        attempts.append(chat)
        if len(attempts) == 1:
            service.youtube_page_tokens[broadcaster] = (chat, "cursor")
            return False
        assert service.youtube_page_tokens[broadcaster] == (chat, "cursor")
        raise asyncio.CancelledError()

    service._stream_live_chat = stream
    sleep = AsyncMock()
    monkeypatch.setattr("bot.services.channels.live_chat.asyncio.sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await service._watch_youtube("channel")
    assert attempts == ["chat", "chat"]
    service._find_active_live_chat.assert_awaited_once_with("channel")
    sleep.assert_not_awaited()
    assert "channel" not in service.active_youtube_chat_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_during_backoff", [False, True])
async def test_deadline_retries_back_off_preserve_cursor_and_allow_cancellation(monkeypatch, cancel_during_backoff):
    service = LiveChatService(None)
    service.started = True
    connection = SimpleNamespace(
        access_token="access", expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()
    )
    service.connections["channel"] = connection
    service._ensure_access_token = AsyncMock(return_value=connection)
    service._poll_live_chat = AsyncMock()
    requests = []

    class Channel:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def unary_stream(self, *args, **kwargs):
            def call(request, **kwargs):
                requests.append(request)
                attempt = len(requests)

                async def events():
                    if attempt <= 7:
                        raise grpc.aio.AioRpcError(grpc.StatusCode.DEADLINE_EXCEEDED)
                    if attempt == 8:
                        yield youtube_live_chat_pb2.LiveChatMessageListResponse(next_page_token="saved")
                        raise grpc.aio.AioRpcError(grpc.StatusCode.DEADLINE_EXCEEDED)
                    yield youtube_live_chat_pb2.LiveChatMessageListResponse(offline_at="ended")
                return events()
            return call

    sleep = AsyncMock(side_effect=asyncio.CancelledError if cancel_during_backoff else None)
    monkeypatch.setattr("bot.services.channels.live_chat.grpc.aio.secure_channel", lambda *args: Channel())
    monkeypatch.setattr("bot.services.channels.live_chat.asyncio.sleep", sleep)
    if cancel_during_backoff:
        with pytest.raises(asyncio.CancelledError):
            await service._stream_live_chat("channel", "chat")
        assert len(requests) == 1
        sleep.assert_awaited_once_with(1.0)
    else:
        assert await service._stream_live_chat("channel", "chat") is True
        assert [call.args[0] for call in sleep.await_args_list] == [1, 2, 4, 8, 16, 30, 30, 1]
        assert requests[-1].page_token == "saved"
    service._poll_live_chat.assert_not_awaited()


def test_youtube_replay_survives_busy_twitch_and_cursor_reset(caplog):
    from bot.services.channels.live_chat import UnifiedChatMessage
    service = LiveChatService(None)
    queue = asyncio.Queue(maxsize=20)
    service.subscribers["channel"].add(queue)
    old = {"id": "old", "snippet": {"displayMessage": "hello", "publishedAt": "2026-10-27T12:00:00Z"}}
    service._publish_youtube_items("channel", [old])
    for index in range(1100):
        service.publish("channel", UnifiedChatMessage(str(index), "twitch", "chat", "u", "U", "hi", "now"))
    assert "youtube:old" not in service.message_ids["channel"]
    while not queue.empty():
        queue.get_nowait()
    service.youtube_page_tokens.clear()
    # Same text from a new message is legitimate; only the old ID is a replay.
    new = {**old, "id": "new"}
    with caplog.at_level("INFO"):
        service._publish_youtube_items("channel", [old, new, old])
    assert queue.qsize() == 1
    assert queue.get_nowait().id == "youtube:new"
    assert "Suppressed 2 replayed YouTube messages" in caplog.text
    assert service.history("channel")[-1]["id"] == "youtube:new"
    service._publish_youtube_items("other", [old])
    assert service.history("other")[-1]["id"] == "youtube:old"


def test_youtube_replay_memory_is_bounded():
    service = LiveChatService(None)
    service._publish_youtube_items("channel", [
        {"id": str(index), "snippet": {"displayMessage": "hi"}} for index in range(5100)
    ])
    assert len(service.youtube_message_ids["channel"]) == 5000
    assert len(service.youtube_message_id_order["channel"]) == 5000
    assert "youtube:0" not in service.youtube_message_ids["channel"]


@pytest.mark.asyncio
async def test_replay_ids_survive_same_chat_rediscovery_but_reset_for_new_stream(monkeypatch):
    service = LiveChatService(None)
    service.started = True
    service.connections['channel'] = SimpleNamespace()
    service._find_active_live_chat = AsyncMock(side_effect=['chat-a', 'chat-a', 'chat-b'])
    monkeypatch.setattr('bot.services.channels.live_chat.asyncio.sleep', AsyncMock())
    attempts = 0

    async def stream(channel, chat):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            service._publish_youtube_items(channel, [{'id': 'old', 'snippet': {'displayMessage': 'hello'}}])
        elif attempts == 2:
            assert 'youtube:old' in service.youtube_message_ids[channel]
        else:
            assert chat == 'chat-b'
            assert not service.youtube_message_ids[channel]
            raise asyncio.CancelledError()
        return True  # Stream ends; rediscovery can still return the same live chat.

    service._stream_live_chat = stream
    with pytest.raises(asyncio.CancelledError):
        await service._watch_youtube('channel')
    assert attempts == 3
