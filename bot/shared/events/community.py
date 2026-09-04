import logging

from twitchio.ext import commands

from bot.profiles import FeatureName, get_active_profile, render_profile_message

LOGGER = logging.getLogger("RatBoomBot")


async def award_subscription_points(bot, payload) -> int:
    broadcaster_id = str(payload.broadcaster.id)
    services = bot.services
    profile = get_active_profile(broadcaster_id)

    if services is None or profile is None:
        return 0

    if not services.features.is_enabled(broadcaster_id, FeatureName.POINTS):
        return 0

    amount = int(profile.points.subscription_reward)

    if amount <= 0:
        return 0

    user_id = str(payload.user.id)
    username = str(payload.user.name)
    await services.points.add_points(broadcaster_id, user_id, username, amount)
    services.stream_logs.write(broadcaster_id, "POINTS", f"Awarded {amount} subscription points to {username} ({user_id}).")
    return amount


async def award_cheer_points(bot, payload) -> int:
    cheer = getattr(payload, "cheer", None)

    if cheer is None:
        return 0

    broadcaster_id = str(payload.broadcaster.id)
    services = bot.services
    profile = get_active_profile(broadcaster_id)

    if services is None or profile is None:
        return 0

    if not services.features.is_enabled(broadcaster_id, FeatureName.POINTS):
        return 0

    bits = int(cheer.bits)
    reward_per_minimum = int(profile.points.cheer_reward)
    minimum_bits = int(profile.points.cheer_minimum_bits)

    if reward_per_minimum <= 0 or minimum_bits <= 0 or bits < minimum_bits:
        return 0

    amount = bits * reward_per_minimum // minimum_bits

    user_id = str(payload.chatter.id)
    username = str(payload.chatter.name)

    if not user_id or user_id == "None" or username.lower() == "anonymous_cheerer":
        return 0

    await services.points.add_points(broadcaster_id, user_id, username, amount)
    services.stream_logs.write(broadcaster_id, "POINTS", f"Awarded {amount} cheer points to {username} ({user_id}) for {bits} Bits.")
    return amount


class CommunityEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    async def send_profile_message(self, broadcaster_id: str, template: str | None, **values) -> None:
        try:
            message = render_profile_message(template, **values)
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
            await self.bot.services.chat_identity.send_message(broadcaster, message)
        except Exception:
            LOGGER.exception(
                "[Events] Failed to send community message for broadcaster %s.",
                broadcaster_id
            )
            raise

    def community_events_enabled(self, broadcaster_id: str) -> bool:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Events] Community event received before services were initialized."
            )
            return False

        if not services.features.is_enabled(broadcaster_id, FeatureName.COMMUNITY_EVENTS):
            LOGGER.debug(
                "[Events] Community responses are disabled for broadcaster %s.",
                broadcaster_id
            )
            return False

        return True

    @commands.Component.listener()
    async def event_follow(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        username = payload.user.name
        services = self.bot.services

        LOGGER.info(
            "[Events] %s followed %s (%s).",
            username,
            broadcaster_name,
            broadcaster_id
        )

        if services is None:
            LOGGER.warning(
                "[Events] Follow event received before services were initialized."
            )
        else:
            services.stream_logs.write(broadcaster_id, "FOLLOW", f"{username} followed the channel.")

        if not self.community_events_enabled(broadcaster_id):
            return

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.debug(
                "[Events] No active profile found for follow event in %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return

        await self.send_profile_message(broadcaster_id, profile.community_messages.follow, username=username)

    @commands.Component.listener()
    async def event_subscription(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        username = payload.user.name
        services = self.bot.services

        LOGGER.info(
            "[Events] %s subscribed to %s (%s).",
            username,
            broadcaster_name,
            broadcaster_id
        )

        if services is None:
            LOGGER.warning(
                "[Events] Subscription event received before services were initialized."
            )
        else:
            services.stream_logs.write(broadcaster_id, "SUBSCRIPTION", f"{username} subscribed.")

            try:
                await award_subscription_points(self.bot, payload)
            except Exception:
                LOGGER.exception(
                    "[Points] Failed to award subscription points to %s in broadcaster %s.",
                    username,
                    broadcaster_id
                )

        if not self.community_events_enabled(broadcaster_id):
            return

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.debug(
                "[Events] No active profile found for subscription event in %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return

        await self.send_profile_message(broadcaster_id, profile.community_messages.subscription, username=username)

    @commands.Component.listener()
    async def event_subscription_message(self, payload) -> None:
        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        username = payload.user.name
        months = payload.cumulative_months
        services = self.bot.services

        LOGGER.info(
            "[Events] %s resubscribed to %s (%s) for %d months.",
            username,
            broadcaster_name,
            broadcaster_id,
            months
        )

        if services is None:
            LOGGER.warning(
                "[Events] Resubscription event received before services were initialized."
            )
        else:
            services.stream_logs.write(broadcaster_id, "RESUB", f"{username} resubscribed for {months} months.")

        if not self.community_events_enabled(broadcaster_id):
            return

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
