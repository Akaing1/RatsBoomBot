import logging

from twitchio.ext import commands

from bot.commands.shoutout import send_shoutout_message

LOGGER = logging.getLogger("Bot")


def get_nested_attr(obj, *names):
    current = obj

    for name in names:
        if current is None:
            return None

        current = getattr(current, name, None)

    return current


class ChatEvents(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload):
        print(
            f"[{payload.broadcaster.name}] "
            f"{payload.chatter.name}: "
            f"{payload.text}"
        )

        if self.bot.services:
            self.bot.services.timers.track_message(payload)
            await self.bot.services.points.track_message(payload)

    @commands.Component.listener()
    async def event_follow(self, payload):
        broadcaster = self.bot.create_partialuser(payload.broadcaster.id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=(
                f"{payload.user.name} has snuck their way into the basement! "
                f"Thanks for following!"
            )
        )

    @commands.Component.listener()
    async def event_subscription(self, payload):
        broadcaster = self.bot.create_partialuser(payload.broadcaster.id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=f"{payload.user.name} has subscribed! Rats stronk together!"
        )

    @commands.Component.listener()
    async def event_subscription_message(self, payload):
        broadcaster = self.bot.create_partialuser(payload.broadcaster.id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=(
                f"{payload.user.name} resubscribed for "
                f"{payload.cumulative_months} months! "
                f"Thank you for your continued support!"
            ),
        )

    @commands.Component.listener()
    async def event_channel_points_custom_reward_redemption_add(self, payload):
        await self.handle_channel_point_redemption(payload)

    @commands.Component.listener()
    async def event_channel_points_redemption_add(self, payload):
        await self.handle_channel_point_redemption(payload)

    @commands.Component.listener()
    async def event_custom_reward_redemption_add(self, payload):
        await self.handle_channel_point_redemption(payload)

    async def handle_channel_point_redemption(self, payload):
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

        result = await self.bot.services.redeems.handle_redemption(
            broadcaster_id=broadcaster_id,
            user_id=user_id,
            username=username,
            reward_title=reward_title,
            redemption_id=redemption_id
        )

        if not result.handled:
            return

        if result.message is None:
            return

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=result.message
        )

    @commands.Component.listener()
    async def event_custom_redemption_add(self, payload):
        await self.handle_channel_point_redemption(payload)

    @commands.Component.listener()
    async def event_raid(self, payload):
        await self.handle_raid(payload)

    async def handle_raid(self, payload):
        raider = getattr(payload, "from_broadcaster", None)
        broadcaster = getattr(payload, "to_broadcaster", None)
        viewer_count = getattr(payload, "viewer_count", 0)

        if raider is None or broadcaster is None:
            LOGGER.warning("Could not process raid payload: %r", payload)
            return

        raider_name = getattr(raider, "name", None)

        if not raider_name:
            LOGGER.warning("Could not find raider name from payload: %r", payload)
            return

        try:
            viewer_count = int(viewer_count)
        except (TypeError, ValueError):
            viewer_count = 0

        viewer_word = "viewer" if viewer_count == 1 else "viewers"

        channel = self.bot.create_partialuser(broadcaster.id)

        await channel.send_message(
            sender=self.bot.user,
            message=(
                f"@{raider_name} has raided the basement with "
                f"{viewer_count} {viewer_word}! Rats stronk together!"
            )
        )

        await send_shoutout_message(
            bot=self.bot,
            broadcaster_id=broadcaster.id,
            username=raider_name
        )
