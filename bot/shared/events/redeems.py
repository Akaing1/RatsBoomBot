import logging
from typing import Any

from twitchio.ext import commands

LOGGER = logging.getLogger("Bot")


def get_nested_attr(obj: Any, *names: str):
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
    async def event_custom_redemption_add(self, payload):
        await self.handle_channel_point_redemption(payload)

    async def handle_channel_point_redemption(self, payload) -> None:
        if not self.bot.services:
            return

        broadcaster_id = get_nested_attr(payload, "broadcaster", "id")
        user_id = get_nested_attr(payload, "user", "id")
        username = get_nested_attr(payload, "user", "name")
        reward_title = get_nested_attr(payload, "reward", "title")
        redemption_id = getattr(payload, "id", None)

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
                "Could not process channel point redemption payload: %r",
                payload
            )
            return

        broadcaster_id = str(broadcaster_id)

        self.bot.services.stream_logs.write(
            broadcaster_id,
            "REDEEM",
            f"{username} redeemed: {reward_title}"
        )

        result = await self.bot.services.redeems.handle_redemption(
            broadcaster_id=broadcaster_id,
            user_id=str(user_id),
            username=username,
            reward_title=reward_title,
            redemption_id=redemption_id
        )

        if not result.handled or result.message is None:
            return

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=result.message
        )
        