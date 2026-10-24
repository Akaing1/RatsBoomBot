from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot.services.channels.live_chat import ChatSegment, LiveChatService
from bot.services.channels.chat_notices import notification_details
from bot.shared.events.chat import ChatEvents
from bot.shared.events.redeems import RedeemEvents
from web.shared.raid_chat import chat_event


def notice_payload(kind, **data):
    return SimpleNamespace(
        id=f"notice-{kind}", broadcaster=SimpleNamespace(id="1"),
        chatter=SimpleNamespace(id="2", name="viewer", display_name="Viewer"),
        notice_type=kind, system_message=f"Viewer: {kind}", text="hello", fragments=[], badges=[],
        **{kind: SimpleNamespace(**data)}
    )


@pytest.mark.parametrize("kind,data,label", [
    ("sub", {}, "Subscription"), ("sub", {"prime": True}, "Prime subscription"),
    ("resub", {"streak_months": 6}, "Resubscription"),
    ("resub", {"prime": True, "streak_months": 12}, "Prime resubscription"),
    ("sub_gift", {}, "Gift sub"), ("community_sub_gift", {}, "Gift subs"),
    ("watch_streak", {"streak_count": 10}, "Watch streak"),
    ("prime_paid_upgrade", {}, "Prime subscription upgrade"),
    ("raid", {"viewer_count": 25}, "Incoming raid"),
])
def test_dashboard_and_preview_share_notification_display(kind, data, label):
    service = LiveChatService(None)
    payload = notice_payload(kind, **data)
    message = service.publish_twitch_notification(payload)
    assert message.notice_label == label
    assert message.message == "hello"
    assert message.notice.startswith(payload.system_message)
    assert message.user_id == "2"
    if data.get("streak_months"):
        assert f"{data['streak_months']} consecutive months" in message.notice
    service.publish_twitch_notification(payload)
    assert len(service.history("1")) == 1
    event = {"message_id": payload.id, "message": {"text": "hello"}, "notice_type": kind,
             "system_message": payload.system_message, kind: data}
    rendered = chat_event("channel.chat.notification", event)["message"]
    assert rendered["notice_label"] == message.notice_label
    assert rendered["notice"] == message.notice
    assert rendered["message"] == "hello"


def test_watch_streak_needs_no_new_sdk_fields_and_unhandled_notices_are_ignored():
    service = LiveChatService(None)
    payload = notice_payload("watch_streak")
    del payload.watch_streak
    payload.system_message = "Viewer watched 10 consecutive streams!"
    assert "10 consecutive streams" in service.publish_twitch_notification(payload).notice
    assert service.publish_twitch_notification(notice_payload("announcement")) is None
    assert chat_event("channel.chat.notification", {"notice_type": "announcement"}) is None


def test_anonymous_gift_notices_do_not_reveal_identity():
    payload = notice_payload("community_sub_gift")
    payload.anonymous = True
    message = LiveChatService(None).publish_twitch_notification(payload)
    assert message.display_name == "Anonymous"
    assert message.user_id == ""


def test_subscription_streak_does_not_repeat_twice_in_the_notice():
    summary = "Viewer has subscribed for 6 consecutive months!"
    assert notification_details("resub", summary, {"streak_months": 6})["notice"] == summary


def test_empty_notices_skip_text_and_emote_processing(monkeypatch):
    service = LiveChatService(None)
    payload = notice_payload("sub")
    payload.text = ""
    service._apply_seventv_emotes = Mock(side_effect=AssertionError("No text to process"))
    assert service.publish_twitch_notification(payload).segments == ()
    monkeypatch.setattr(LiveChatService, "apply_emote_catalog", Mock(side_effect=AssertionError("No text to process")))
    rendered = chat_event("channel.chat.notification", {"message_id": "notice", "notice_type": "sub",
        "system_message": "Viewer subscribed!", "message": {"text": "", "fragments": [{"type": "text", "text": ""}]}},
        emotes={"Kappa": ChatSegment("emote", "Kappa")})
    assert rendered["message"]["segments"] == []


def test_known_emotes_do_not_allocate_unused_text_segments(monkeypatch):
    segment = ChatSegment("text", "Kappa hello")
    emote = ChatSegment("emote", "Kappa", "https://example.invalid/emote")
    construct = Mock(wraps=ChatSegment)
    monkeypatch.setattr("bot.services.channels.live_chat.ChatSegment", construct)
    rendered = LiveChatService.apply_emote_catalog((segment,), {"Kappa": emote})
    assert rendered[0] is emote
    assert [part.text for part in rendered] == ["Kappa", " ", "hello"]
    assert construct.call_count == 2


def test_redemption_without_input_is_visible_with_cost_and_deduplicated():
    service = LiveChatService(None)
    args = dict(broadcaster_id="1", redemption_id="r1", user_id="2", username="Viewer",
                reward_title="Hydrate", redeemed_at=datetime(2026, 10, 18, tzinfo=UTC), cost=1000)
    message = service.publish_redemption(**args)
    service.publish_redemption(**args)
    assert message.is_redeem
    assert message.notice == "Redeemed Hydrate · 1,000 points"
    assert message.message == ""
    assert len(service.history("1")) == 1
    assert service.publish_redemption(**{**args, "redemption_id": "r2", "user_input": "hi"}).message == "hi"


def test_preview_reward_chat_messages_are_categorized_as_redeems():
    rendered = chat_event("channel.chat.message", {"message_id": "1",
        "channel_points_custom_reward_id": "r", "message": {"text": "my input"}})["message"]
    assert rendered["is_redeem"]
    assert rendered["notice_label"] == "Redeem"
    assert rendered["message"] == "my input"


@pytest.mark.asyncio
async def test_notification_listener_publishes_to_dashboard_chat():
    service = LiveChatService(None)
    events = ChatEvents(SimpleNamespace(services=SimpleNamespace(live_chat=service)))
    await events.event_chat_notification(notice_payload("sub", prime=True))
    assert service.history("1")[0]["notice_label"] == "Prime subscription"


@pytest.mark.asyncio
async def test_redemption_listener_publishes_unmanaged_rewards_without_public_replies():
    service = LiveChatService(None)
    services = SimpleNamespace(live_chat=service,
        stream_logs=SimpleNamespace(write=Mock(), get_active_session=lambda _: SimpleNamespace(stream_id="stream")),
        redeems=SimpleNamespace(record_activity=AsyncMock(), handle_redemption=AsyncMock(return_value=SimpleNamespace(handled=False))))
    events = RedeemEvents(SimpleNamespace(services=services))
    payload = SimpleNamespace(id="r1", broadcaster=SimpleNamespace(id="1", name="channel"),
        user=SimpleNamespace(id="2", name="viewer"), reward=SimpleNamespace(title="Hydrate", cost=100), user_input="")
    await events.event_custom_redemption_add(payload)
    assert service.history("1")[0]["notice"] == "Redeemed Hydrate · 100 points"
    services.redeems.record_activity.assert_awaited_once()


def test_installed_twitchio_preserves_watch_streak_system_message():
    from twitchio import ChatNotification

    event = {key: None for key in ("sub", "resub", "sub_gift", "community_sub_gift", "gift_paid_upgrade",
        "prime_paid_upgrade", "raid", "pay_it_forward", "announcement", "bits_badge_tier", "charity_donation",
        "shared_chat_sub", "shared_chat_resub", "shared_chat_sub_gift", "shared_chat_community_sub_gift",
        "shared_chat_gift_paid_upgrade", "shared_chat_prime_paid_upgrade", "shared_chat_raid",
        "shared_chat_pay_it_forward", "shared_chat_announcement")}
    event.update(broadcaster_user_id="1", broadcaster_user_login="channel", broadcaster_user_name="Channel",
        chatter_user_id="2", chatter_user_login="viewer", chatter_user_name="Viewer", chatter_is_anonymous=False,
        color="", badges=[], system_message="Viewer watched 10 consecutive streams!", message_id="streak",
        message={"text": "", "fragments": []}, notice_type="watch_streak", watch_streak={"streak_count": 10})
    payload = ChatNotification(event, http=Mock())
    assert "10 consecutive streams" in LiveChatService(None).publish_twitch_notification(payload).notice
