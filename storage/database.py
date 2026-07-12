from typing import Any

import asqlite
from twitchio import eventsub

from config.settings import settings


def create_channel_point_redemption_subscription(broadcaster_user_id: str):
    subscription_class = getattr(
        eventsub,
        "ChannelPointsRedeemAddSubscription",
        None
    )

    if subscription_class is None:
        subscription_class = getattr(
            eventsub,
            "ChannelPointsCustomRewardRedemptionAddSubscription",
            None
        )

    if subscription_class is None:
        return None

    return subscription_class(
        broadcaster_user_id=broadcaster_user_id
    )


def create_raid_subscription(broadcaster_user_id: str):
    subscription_class = getattr(eventsub, "ChannelRaidSubscription", None)

    if subscription_class is None:
        return None

    return subscription_class(
        to_broadcaster_user_id=broadcaster_user_id
    )


def create_broadcaster_subscriptions(broadcaster_user_id: str) -> list[Any]:
    subs: list[Any] = [
        eventsub.ChatMessageSubscription(
            broadcaster_user_id=broadcaster_user_id,
            user_id=settings.BOT_ID,
        ),
        eventsub.ChannelFollowSubscription(
            broadcaster_user_id=broadcaster_user_id,
            moderator_user_id=broadcaster_user_id,
        ),
        eventsub.ChannelSubscribeSubscription(
            broadcaster_user_id=broadcaster_user_id,
        ),
        eventsub.ChannelSubscribeMessageSubscription(
            broadcaster_user_id=broadcaster_user_id,
        ),
        eventsub.ChannelBanSubscription(
            broadcaster_user_id=broadcaster_user_id,
            moderator_user_id=broadcaster_user_id,
        ),
        eventsub.AdBreakBeginSubscription(
            broadcaster_user_id=broadcaster_user_id,
        ),
        eventsub.StreamOnlineSubscription(
            broadcaster_user_id=broadcaster_user_id
        ),
        eventsub.StreamOfflineSubscription(
            broadcaster_user_id=broadcaster_user_id
        )
    ]

    channel_point_sub = create_channel_point_redemption_subscription(
        broadcaster_user_id
    )

    if channel_point_sub is not None:
        subs.append(channel_point_sub)

    raid_sub = create_raid_subscription(broadcaster_user_id)

    if raid_sub is not None:
        subs.append(raid_sub)

    return subs


async def setup_database(db: asqlite.Pool) -> tuple[list[tuple[Any, Any]], list[Any], list[str]]:
    query = """
    CREATE TABLE IF NOT EXISTS tokens(
        user_id TEXT PRIMARY KEY,
        token TEXT NOT NULL,
        refresh TEXT NOT NULL
    )
    """

    async with db.acquire() as connection:
        await connection.execute(query)

        rows = await connection.fetchall("SELECT * FROM tokens")

        tokens = []
        subs = []
        broadcasters = []

        for row in rows:
            tokens.append((row["token"], row["refresh"]))

            if row["user_id"] == settings.BOT_ID:
                continue

            broadcasters.append(row["user_id"])
            subs.extend(create_broadcaster_subscriptions(row["user_id"]))

        return tokens, subs, broadcasters


async def save_token(db: asqlite.Pool, user_id: str, token: str, refresh: str):
    query = """
    INSERT INTO tokens (user_id, token, refresh)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id)
    DO UPDATE SET
        token = excluded.token,
        refresh = excluded.refresh
    """

    async with db.acquire() as connection:
        await connection.execute(
            query,
            (
                user_id,
                token,
                refresh,
            )
        )


async def delete_token(db: asqlite.Pool, user_id: str) -> None:
    query = """
    DELETE FROM tokens
    WHERE user_id = ?
    """

    async with db.acquire() as connection:
        await connection.execute(query, (user_id,))
