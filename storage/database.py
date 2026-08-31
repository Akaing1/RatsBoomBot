import logging
from typing import Any

import asqlite
from twitchio import eventsub

from config.settings import settings
from storage.migration_runner import run_migrations

LOGGER = logging.getLogger("RatBoomBot")


def create_channel_point_redemption_subscription(broadcaster_user_id: str):
    subscription_class = getattr(eventsub, "ChannelPointsRedeemAddSubscription", None)

    if subscription_class is None:
        subscription_class = getattr(eventsub, "ChannelPointsCustomRewardRedemptionAddSubscription", None)

    if subscription_class is None:
        LOGGER.warning(
            "[EventSub] Channel-point redemption subscriptions are unavailable "
            "for broadcaster %s because no supported TwitchIO subscription "
            "class was found.",
            broadcaster_user_id
        )
        return None

    return subscription_class(broadcaster_user_id=broadcaster_user_id)


def create_raid_subscription(broadcaster_user_id: str):
    subscription_class = getattr(eventsub, "ChannelRaidSubscription", None)

    if subscription_class is None:
        LOGGER.warning(
            "[EventSub] Raid subscriptions are unavailable for broadcaster %s "
            "because ChannelRaidSubscription was not found.",
            broadcaster_user_id
        )
        return None

    return subscription_class(to_broadcaster_user_id=broadcaster_user_id)


def create_broadcaster_subscriptions(broadcaster_user_id: str) -> list[Any]:
    broadcaster_user_id = str(broadcaster_user_id)

    LOGGER.debug(
        "[EventSub] Building subscriptions for broadcaster %s.",
        broadcaster_user_id
    )

    subscriptions: list[Any] = [
        eventsub.ChatMessageSubscription(broadcaster_user_id=broadcaster_user_id, user_id=settings.BOT_ID),
        eventsub.ChannelFollowSubscription(broadcaster_user_id=broadcaster_user_id, moderator_user_id=broadcaster_user_id),
        eventsub.ChannelSubscribeSubscription(broadcaster_user_id=broadcaster_user_id),
        eventsub.ChannelSubscribeMessageSubscription(broadcaster_user_id=broadcaster_user_id),
        eventsub.ChannelBanSubscription(broadcaster_user_id=broadcaster_user_id, moderator_user_id=broadcaster_user_id),
        eventsub.AdBreakBeginSubscription(broadcaster_user_id=broadcaster_user_id),
        eventsub.StreamOnlineSubscription(broadcaster_user_id=broadcaster_user_id),
        eventsub.StreamOfflineSubscription(broadcaster_user_id=broadcaster_user_id),
        eventsub.ChannelModerateV2Subscription(broadcaster_user_id=broadcaster_user_id, moderator_user_id=broadcaster_user_id),
        eventsub.ShoutoutCreateSubscription(broadcaster_user_id=broadcaster_user_id, moderator_user_id=broadcaster_user_id)
    ]

    channel_point_subscription = create_channel_point_redemption_subscription(broadcaster_user_id)

    if channel_point_subscription is not None:
        subscriptions.append(channel_point_subscription)

    raid_subscription = create_raid_subscription(broadcaster_user_id)

    if raid_subscription is not None:
        subscriptions.append(raid_subscription)

    LOGGER.info(
        "[EventSub] Prepared %d subscriptions for broadcaster %s.",
        len(subscriptions),
        broadcaster_user_id
    )

    for subscription in subscriptions:
        LOGGER.debug(
            "[EventSub] Prepared %s for broadcaster %s.",
            type(subscription).__name__,
            broadcaster_user_id
        )

    return subscriptions


async def setup_database(db: asqlite.Pool) -> tuple[list[tuple[Any, Any]], list[Any], list[str]]:
    LOGGER.info("[Database] Running database migrations.")
    await run_migrations(db)

    LOGGER.info("[Database] Loading stored OAuth tokens.")

    async with db.acquire() as connection:
        rows = await connection.fetchall(
            """
            SELECT user_id, token, refresh
            FROM tokens
            """
        )
        custom_bot_rows = await connection.fetchall(
            "SELECT DISTINCT bot_user_id FROM channel_chat_identities WHERE bot_user_id IS NOT NULL"
        )

    custom_bot_ids = {str(row["bot_user_id"]) for row in custom_bot_rows}

    tokens: list[tuple[Any, Any]] = []
    subscriptions: list[Any] = []
    broadcasters: list[str] = []

    for row in rows:
        user_id = str(row["user_id"])
        tokens.append((row["token"], row["refresh"]))

        if user_id == str(settings.BOT_ID) or user_id in custom_bot_ids:
            LOGGER.debug(
                "[OAuth] Loaded chat bot OAuth token for user %s.",
                user_id
            )
            continue

        broadcasters.append(user_id)
        subscriptions.extend(create_broadcaster_subscriptions(user_id))

        LOGGER.info(
            "[OAuth] Loaded broadcaster token for user %s.",
            user_id
        )

    LOGGER.info("[Database] Loaded %d OAuth tokens.", len(tokens))
    LOGGER.info("[Database] Loaded %d broadcaster tokens.", len(broadcasters))
    LOGGER.info("[EventSub] Prepared %d total subscriptions.", len(subscriptions))

    if not tokens:
        LOGGER.warning("[OAuth] No OAuth tokens were found in the database.")

    if not broadcasters:
        LOGGER.warning("[OAuth] No broadcaster tokens were found in the database.")

    return tokens, subscriptions, broadcasters


async def save_token(db: asqlite.Pool, user_id: str, token: str, refresh: str) -> None:
    user_id = str(user_id)

    query = """
    INSERT INTO tokens (user_id, token, refresh)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id)
    DO UPDATE SET
        token = excluded.token,
        refresh = excluded.refresh
    """

    LOGGER.debug("[OAuth] Saving token for user %s.", user_id)

    try:
        async with db.acquire() as connection:
            await connection.execute(query, (user_id, token, refresh))
    except Exception:
        LOGGER.exception(
            "[OAuth] Failed to save token for user %s.",
            user_id
        )
        raise

    LOGGER.info("[OAuth] Saved token for user %s.", user_id)


async def delete_token(db: asqlite.Pool, user_id: str) -> None:
    user_id = str(user_id)

    query = """
    DELETE FROM tokens
    WHERE user_id = ?
    """

    LOGGER.debug("[OAuth] Deleting token for user %s.", user_id)

    try:
        async with db.acquire() as connection:
            await connection.execute(query, (user_id,))
    except Exception:
        LOGGER.exception(
            "[OAuth] Failed to delete token for user %s.",
            user_id
        )
        raise

    LOGGER.info("[OAuth] Deleted token for user %s.", user_id)
