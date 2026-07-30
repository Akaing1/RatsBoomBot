from twitchio.ext import commands
import logging

from bot.profiles import get_active_profile, render_profile_message

LOGGER = logging.getLogger("Bot")


class CommunityEvents(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    async def send_profile_message(self, broadcaster_id: str, template: str | None, **values) -> None:
        message = render_profile_message(
            template,
            **values,
        )

        if message is None:
            return

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=message,
        )

    @commands.Component.listener()
    async def event_follow(self, payload):
        LOGGER.info(
            "Follow event received: broadcaster=%s follower=%s",
            payload.broadcaster.id,
            payload.user.name
        )
        broadcaster_id = str(payload.broadcaster.id)
        username = payload.user.name

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "FOLLOW",
                f"{username} followed the channel.",
            )

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return

        await self.send_profile_message(
            broadcaster_id,
            profile.community_messages.follow,
            username=username,
        )

    @commands.Component.listener()
    async def event_subscription(self, payload):
        broadcaster_id = str(payload.broadcaster.id)
        username = payload.user.name

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "SUBSCRIPTION",
                f"{username} subscribed.",
            )

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return

        await self.send_profile_message(
            broadcaster_id,
            profile.community_messages.subscription,
            username=username,
        )

    @commands.Component.listener()
    async def event_subscription_message(self, payload):
        broadcaster_id = str(payload.broadcaster.id)
        username = payload.user.name
        months = payload.cumulative_months

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "RESUB",
                f"{username} resubscribed for {months} months.",
            )

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            return

        await self.send_profile_message(
            broadcaster_id,
            profile.community_messages.resubscription,
            username=username,
            months=months,
        )
