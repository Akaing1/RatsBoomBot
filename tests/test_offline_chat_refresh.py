from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bot.services.channels.broadcaster import BroadcasterService
from bot.services.channels.live_chat import LiveChatService, UnifiedChatMessage
from web.shared.live_chat import clear_stale_chat_on_refresh


@pytest.mark.parametrize("minutes,live,expected", [
    (59, False, False), (60, False, True), (61, False, True),
    (120, True, False),
])
def test_refresh_clears_only_after_confirmed_hour_offline(minutes, live, expected):
    now = datetime(2026, 10, 8, tzinfo=UTC)
    broadcaster = SimpleNamespace(id="123", is_live=live,
                                 offline_since=now - timedelta(minutes=minutes))
    service = Mock()
    assert clear_stale_chat_on_refresh(service, broadcaster, now=now) is expected
    if expected:
        service.clear_chat.assert_called_once_with("123", platform="both")
    else:
        service.clear_chat.assert_not_called()


def test_unknown_offline_duration_does_not_clear_chat():
    service = Mock()
    assert not clear_stale_chat_on_refresh(service, SimpleNamespace(id="123", is_live=False))
    service.clear_chat.assert_not_called()


def test_offline_polls_preserve_start_and_live_resets_it():
    service = BroadcasterService(None, ["123"])
    broadcaster = service.broadcasters["123"]
    service.update_live_state("123", False)
    started = broadcaster.offline_since
    assert started is not None
    service.update_live_state("123", False)
    assert broadcaster.offline_since == started
    service.update_live_state("123", True)
    assert broadcaster.offline_since is None
    assert broadcaster.is_live


def test_offline_refresh_clears_both_platforms_and_notifies_open_feeds():
    service = LiveChatService(None)
    for platform in ("twitch", "youtube"):
        service.publish("123", UnifiedChatMessage(
            id=platform, platform=platform, kind="chat", username="viewer",
            display_name="Viewer", message="hello", timestamp="2026-10-08T00:00:00Z"))
    queue = service.subscribe("123")
    other = service.subscribe("456")
    now = datetime(2026, 10, 8, tzinfo=UTC)
    broadcaster = SimpleNamespace(id="123", is_live=False,
                                 offline_since=now - timedelta(hours=1))
    assert clear_stale_chat_on_refresh(service, broadcaster, now=now)
    assert service.history("123") == []
    assert queue.get_nowait() == {"event": "chat-clear", "platform": "both"}
    assert other.empty()
