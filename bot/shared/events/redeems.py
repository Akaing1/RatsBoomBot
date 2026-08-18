import logging
from typing import Any

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


def get_nested_attr(obj: Any, *names: str) -> Any | None:
    current = obj

    for name in names:
        if current is None:
            return None

        current = getattr(current, name, None)

    return current


class RedeemEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_custom_redemption_add(self, payload) -> None:
        await self.handle_channel_point_redemption(payload)

    async def handle_channel_point_redemption(self, payload) -> None:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Events] Redemption event received before services were initialized."
            )
            return

        broadcaster_id = get_nested_attr(payload, "broadcaster", "id")
        broadcaster_name = get_nested_attr(payload, "broadcaster", "name")
        user_id = get_nested_attr(payload, "user", "id")
        username = get_nested_attr(payload, "user", "name")
        reward_title = get_nested_attr(payload, "reward", "title")
        redemption_id = getattr(payload, "id", None)
        user_input = getattr(payload, "user_input", None)
        redeemed_at = getattr(payload, "redeemed_at", None)

        if user_input is None:
            user_input = getattr(payload, "input", None)

        if broadcaster_id is None:
            broadcaster_id = getattr(payload, "broadcaster_id", None)

        if user_id is None:
            user_id = getattr(payload, "user_id", None)

        if username is None:
            username = getattr(payload, "user_name", None)

        if reward_title is None:
            reward_title = getattr(payload, "reward_title", None)

        if redemption_id is None:
            redemption_id = getattr(payload, "redemption_id", None)

        if not broadcaster_id or not user_id or not username or not reward_title:
            LOGGER.warning(
                "[Events] Could not process channel point redemption payload: %r",
                payload
            )
            return

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)

        LOGGER.info(
            "[Events] %s redeemed '%s' in %s (%s).",
            username,
            reward_title,
            broadcaster_name or "unknown",
            broadcaster_id
        )

        services.stream_logs.write(
            broadcaster_id,
            "REDEEM",
            f"{username} redeemed: {reward_title}"
        )

        active_session = services.stream_logs.get_active_session(broadcaster_id)
        stream_id = active_session.stream_id if active_session is not None else None

        if stream_id is None:
            stream_id = await services.redeems.get_current_stream_id(broadcaster_id)

        try:
            await services.redeems.record_activity(
                redemption_id=redemption_id,
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                reward_title=reward_title,
                user_input=user_input,
                stream_id=stream_id,
                redeemed_at=redeemed_at
            )
        except Exception:
            LOGGER.exception(
                "[Events] Failed to save dashboard activity for redemption '%s' from %s.",
                reward_title,
                username
            )

        try:
            result = await services.redeems.handle_redemption(
                broadcaster_id=broadcaster_id,
                user_id=user_id,
                username=username,
                reward_title=reward_title,
                redemption_id=redemption_id,
                stream_id=stream_id
            )
        except Exception:
            LOGGER.exception(
                "[Events] Failed to process redemption '%s' from %s.",
                reward_title,
                username
            )
            raise

        if not result.handled:
            LOGGER.debug(
                "[Events] Redemption '%s' was not handled.",
                reward_title
            )
            return

        if result.message is None:
            LOGGER.debug(
                "[Events] Redemption '%s' completed without a response message.",
                reward_title
            )
            return

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        try:
            await broadcaster.send_message(sender=self.bot.user, message=result.message)
        except Exception:
            LOGGER.exception(
                "[Events] Failed to send redemption response for '%s'.",
                reward_title
            )
            raise
