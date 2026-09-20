from twitchio import eventsub

from storage.database import create_broadcaster_subscriptions


def test_broadcaster_subscriptions_include_aggregate_subscription_gifts() -> None:
    subscriptions = create_broadcaster_subscriptions("channel-1")

    assert any(isinstance(subscription, eventsub.ChannelSubscriptionGiftSubscription) for subscription in subscriptions)
    assert any(isinstance(subscription, eventsub.AutomodMessageHoldV2Subscription) for subscription in subscriptions)
    assert any(isinstance(subscription, eventsub.AutomodMessageUpdateV2Subscription) for subscription in subscriptions)
    assert any(isinstance(subscription, eventsub.ChatMessageDeleteSubscription) for subscription in subscriptions)
