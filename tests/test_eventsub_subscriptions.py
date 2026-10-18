from twitchio import eventsub

from storage.database import create_broadcaster_subscriptions


def test_broadcaster_subscriptions_include_aggregate_subscription_gifts() -> None:
    subscriptions = create_broadcaster_subscriptions("channel-1")

    assert any(isinstance(subscription, eventsub.ChannelSubscriptionGiftSubscription) for subscription in subscriptions)
    assert any(isinstance(subscription, eventsub.AutomodMessageHoldV2Subscription) for subscription in subscriptions)
    assert any(isinstance(subscription, eventsub.AutomodMessageUpdateV2Subscription) for subscription in subscriptions)
    assert any(isinstance(subscription, eventsub.ChatMessageDeleteSubscription) for subscription in subscriptions)
    assert any(isinstance(subscription, eventsub.ChatNotificationSubscription) for subscription in subscriptions)
    raids = [subscription.condition for subscription in subscriptions if isinstance(subscription, eventsub.ChannelRaidSubscription)]
    assert any(condition.get("from_broadcaster_user_id") == "channel-1" for condition in raids)
    assert any(condition.get("to_broadcaster_user_id") == "channel-1" for condition in raids)
