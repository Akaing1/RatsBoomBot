from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot.shared.events.community as community


def create_bot():
    services = SimpleNamespace(
        features=SimpleNamespace(is_enabled=MagicMock(return_value=True)),
        points=SimpleNamespace(add_points=AsyncMock(), add_points_once=AsyncMock(return_value=True)),
        chatters=SimpleNamespace(resolve=AsyncMock()),
        stream_logs=SimpleNamespace(write=MagicMock())
    )
    return SimpleNamespace(services=services)


@pytest.mark.asyncio
async def test_subscription_reward_is_awarded_silently(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(subscription_reward=500))
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        user=SimpleNamespace(id="viewer-1", name="viewer")
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_subscription_points(bot, payload)

    assert awarded == 500
    bot.services.points.add_points.assert_awaited_once_with("channel-1", "viewer-1", "viewer", 500)
    bot.services.stream_logs.write.assert_called_once()


@pytest.mark.asyncio
async def test_gifted_subscription_awards_points_without_chat_response(monkeypatch) -> None:
    bot = create_bot()
    bot.create_partialuser = MagicMock()
    bot.services.chat_identity = SimpleNamespace(send_message=AsyncMock())
    profile = SimpleNamespace(
        points=SimpleNamespace(subscription_reward=500),
        community_messages=SimpleNamespace(subscription="Thanks for subscribing, {username}!")
    )
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1", name="channel"),
        user=SimpleNamespace(id="viewer-1", name="viewer"),
        gift=True
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    component = community.CommunityEvents(bot)
    await component.event_subscription(payload)

    bot.services.points.add_points.assert_awaited_once_with("channel-1", "viewer-1", "viewer", 500)
    bot.services.chat_identity.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_regular_subscription_keeps_chat_response(monkeypatch) -> None:
    bot = create_bot()
    broadcaster = SimpleNamespace(id="channel-1", name="channel")
    bot.create_partialuser = MagicMock(return_value=broadcaster)
    bot.services.chat_identity = SimpleNamespace(send_message=AsyncMock())
    profile = SimpleNamespace(
        points=SimpleNamespace(subscription_reward=500),
        community_messages=SimpleNamespace(subscription="Thanks for subscribing, {username}!")
    )
    payload = SimpleNamespace(
        broadcaster=broadcaster,
        user=SimpleNamespace(id="viewer-1", name="viewer"),
        gift=False
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    component = community.CommunityEvents(bot)
    await component.event_subscription(payload)

    bot.services.points.add_points.assert_awaited_once_with("channel-1", "viewer-1", "viewer", 500)
    bot.services.chat_identity.send_message.assert_awaited_once_with(broadcaster, "Thanks for subscribing, viewer!")


@pytest.mark.asyncio
async def test_gift_batch_sends_one_condensed_response(monkeypatch) -> None:
    bot = create_bot()
    broadcaster = SimpleNamespace(id="channel-1", name="channel")
    bot.create_partialuser = MagicMock(return_value=broadcaster)
    bot.services.chat_identity = SimpleNamespace(send_message=AsyncMock())
    profile = SimpleNamespace(
        community_messages=SimpleNamespace(
            gifted_subscription="Thanks {username} for gifting {count} {subscription_word}!"
        )
    )
    payload = SimpleNamespace(
        broadcaster=broadcaster,
        user=SimpleNamespace(id="gifter-1", name="gifter"),
        total=5
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    component = community.CommunityEvents(bot)
    await component.event_subscription_gift(payload)

    bot.services.chat_identity.send_message.assert_awaited_once_with(
        broadcaster,
        "Thanks gifter for gifting 5 subs!"
    )
    bot.services.points.add_points.assert_not_awaited()
    bot.services.stream_logs.write.assert_called_once_with(
        "channel-1",
        "GIFTED SUBS",
        "gifter gifted 5 subscriptions."
    )


@pytest.mark.asyncio
async def test_anonymous_gift_batch_uses_anonymous_name(monkeypatch) -> None:
    bot = create_bot()
    broadcaster = SimpleNamespace(id="channel-1", name="channel")
    bot.create_partialuser = MagicMock(return_value=broadcaster)
    bot.services.chat_identity = SimpleNamespace(send_message=AsyncMock())
    profile = SimpleNamespace(
        community_messages=SimpleNamespace(
            gifted_subscription="Thanks {username} for gifting {count} {subscription_word}!"
        )
    )
    payload = SimpleNamespace(broadcaster=broadcaster, user=None, total=1)
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    component = community.CommunityEvents(bot)
    await component.event_subscription_gift(payload)

    bot.services.chat_identity.send_message.assert_awaited_once_with(
        broadcaster,
        "Thanks Anonymous for gifting 1 sub!"
    )


@pytest.mark.asyncio
async def test_cheer_reward_requires_minimum_bits(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=200, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="viewer-1", name="viewer"),
        cheer=SimpleNamespace(bits=99)
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_cheer_points(bot, payload)

    assert awarded == 0
    bot.services.points.add_points.assert_not_awaited()
    bot.services.stream_logs.write.assert_not_called()


@pytest.mark.asyncio
async def test_cheer_reward_scales_with_bits(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=50, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="viewer-1", name="viewer"),
        cheer=SimpleNamespace(bits=200)
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_cheer_points(bot, payload)

    assert awarded == 100
    bot.services.points.add_points.assert_awaited_once_with("channel-1", "viewer-1", "viewer", 100)
    bot.services.stream_logs.write.assert_called_once()


@pytest.mark.asyncio
async def test_cheer_reward_uses_the_exact_bit_ratio(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=50, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="viewer-1", name="viewer"),
        cheer=SimpleNamespace(bits=150)
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_cheer_points(bot, payload)

    assert awarded == 75
    bot.services.points.add_points.assert_awaited_once_with("channel-1", "viewer-1", "viewer", 75)


@pytest.mark.asyncio
async def test_sound_alert_reward_uses_trusted_bot_message(monkeypatch) -> None:
    bot = create_bot()
    bot.services.chatters.resolve.return_value = SimpleNamespace(id="viewer-1", name="viewer")
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=50, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        id="message-1",
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="sound-alerts-id", name="soundalerts"),
        text="viewer played Air Horn for 200 Bits"
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_sound_alert_points(bot, payload)

    assert awarded == 100
    bot.services.chatters.resolve.assert_awaited_once_with("channel-1", "viewer")
    bot.services.points.add_points_once.assert_awaited_once_with(
        "channel-1",
        "viewer-1",
        "viewer",
        100,
        source="sound_alerts",
        event_id="message-1"
    )
    bot.services.stream_logs.write.assert_called_once()


@pytest.mark.asyncio
async def test_sound_alert_reward_skips_anonymous_purchase(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=50, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        id="message-1",
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="sound-alerts-id", name="soundalerts"),
        text="Anonymous played Air Horn for 200 Bits"
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_sound_alert_points(bot, payload)

    assert awarded == 0
    bot.services.chatters.resolve.assert_not_awaited()
    bot.services.points.add_points_once.assert_not_awaited()


@pytest.mark.asyncio
async def test_sound_alert_reward_rejects_untrusted_sender(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=50, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        id="message-1",
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="viewer-2", name="not_soundalerts"),
        text="viewer played Air Horn for 200 Bits"
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_sound_alert_points(bot, payload)

    assert awarded == 0
    bot.services.chatters.resolve.assert_not_awaited()
    bot.services.points.add_points_once.assert_not_awaited()


@pytest.mark.asyncio
async def test_sound_alert_reward_ignores_duplicate_message(monkeypatch) -> None:
    bot = create_bot()
    bot.services.chatters.resolve.return_value = SimpleNamespace(id="viewer-1", name="viewer")
    bot.services.points.add_points_once.return_value = False
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=50, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        id="message-1",
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="sound-alerts-id", name="soundalerts"),
        text="viewer played Air Horn for 200 Bits"
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_sound_alert_points(bot, payload)

    assert awarded == 0
    bot.services.stream_logs.write.assert_not_called()
