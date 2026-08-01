import logging

from twitchio.ext import commands

from bot.profiles import get_active_profile, render_profile_message

LOGGER = logging.getLogger("RatBoomBot")


class CommunityEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    async def send_profile_message(self, broadcaster_id: str, template: str | None, **values) -> None:

        try:
            message = render_profile_message(
                template,
                **values
            )
        except Exception:
            LOGGER.exception(
                "[Events] Failed to render community message for broadcaster %s.",
                broadcaster_id
            )
            raise

        if message is None:
            LOGGER.debug(
                "[Events] Community message is disabled for broadcaster %s.",
                broadcaster_id
            )
            return

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        try:
            await broadcaster.send_message(
                sender=self.bot.user,
                message=message
            )
        except Exception:
            LOGGER.exception(
                "[Events] Failed to send community message for broadcaster %s.",
                broadcaster_id
            )
            raise

    @commands.Component.listener()
    async def event_follow(self, payload):

        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        username = payload.user.name

        LOGGER.info(
            "[Events] %s followed %s (%s).",
            username,
            broadcaster_name,
            broadcaster_id
        )

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "FOLLOW",
                f"{username} followed the channel."
            )
        else:
            LOGGER.warning(
                "[Events] Follow event received before services were initialized."
            )

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.debug(
                "[Events] No active profile found for follow event in %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return

        await self.send_profile_message(
            broadcaster_id,
            profile.community_messages.follow,
            username=username
        )

    @commands.Component.listener()
    async def event_subscription(self, payload):

        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        username = payload.user.name

        LOGGER.info(
            "[Events] %s subscribed to %s (%s).",
            username,
            broadcaster_name,
            broadcaster_id
        )

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "SUBSCRIPTION",
                f"{username} subscribed."
            )
        else:
            LOGGER.warning(
                "[Events] Subscription event received before services were initialized."
            )

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.debug(
                "[Events] No active profile found for subscription event in %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return

        await self.send_profile_message(
            broadcaster_id,
            profile.community_messages.subscription,
            username=username
        )

    @commands.Component.listener()
    async def event_subscription_message(self, payload):

        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        username = payload.user.name
        months = payload.cumulative_months

        LOGGER.info(
            "[Events] %s resubscribed to %s (%s) for %d months.",
            username,
            broadcaster_name,
            broadcaster_id,
            months
        )

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "RESUB",
                f"{username} resubscribed for {months} months."
            )
        else:
            LOGGER.warning(
                "[Events] Resubscription event received before services were initialized."
            )

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.debug(
                "[Events] No active profile found for resubscription event in %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return

        await self.send_profile_message(
            broadcaster_id,
            profile.community_messages.resubscription,
            username=username,
            months=months
        )
