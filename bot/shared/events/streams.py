import logging

from twitchio.ext import commands

from bot.profiles import FeatureName, get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


class StreamEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_stream_online(self, payload) -> None:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Events] Stream online event received before services were initialized."
            )
            return

        broadcaster = getattr(payload, "broadcaster", None)
        broadcaster_id = getattr(broadcaster, "id", None)

        if broadcaster_id is None:
            broadcaster_id = getattr(payload, "broadcaster_id", None)

        stream_id = getattr(payload, "id", None)

        if stream_id is None:
            stream_id = getattr(payload, "stream_id", None)

        if broadcaster_id is None or stream_id is None:
            LOGGER.warning(
                "[Events] Could not start stream logger from payload: %r",
                payload
            )
            return

        broadcaster_id = str(broadcaster_id)
        stream_id = str(stream_id)
        channel_name = getattr(broadcaster, "name", None)

        LOGGER.info(
            "[Events] Stream started for %s (%s).",
            channel_name or "unknown",
            broadcaster_id
        )

        await services.stream_logs.start_session(broadcaster_id=broadcaster_id, stream_id=stream_id, channel_name=channel_name)
        await services.passive_points.start_for_stream(broadcaster_id, stream_id)
        active_event = await services.raid_bosses.get_active_event(broadcaster_id)
        event, failed_reward = await services.raid_bosses.register_stream(broadcaster_id, stream_id)
        profile = get_active_profile(broadcaster_id)
        raids_enabled = profile is not None and profile.raid_bosses.enabled and services.features.is_enabled(broadcaster_id, FeatureName.RAID_BOSSES)

        if active_event is not None and event is None and failed_reward:
            remaining_ratio = active_event.current_hp / active_event.max_hp
            fraction = "half" if remaining_ratio <= 0.25 else "one quarter of"
            await services.raid_bosses.send_announcement(broadcaster_id, f"The subjugation of {active_event.boss_name} has failed after {active_event.stream_limit} streams. Raiders earned {fraction} the reward pool ({failed_reward:,} points) based on contribution.", "purple")

            if raids_enabled:
                await services.raid_bosses.schedule_spawn(broadcaster_id, profile.raid_bosses, stream_id=stream_id)
        elif active_event is not None:
            await services.raid_bosses.start_reminders(broadcaster_id, stream_id)
        elif raids_enabled:
            await services.raid_bosses.schedule_spawn(broadcaster_id, profile.raid_bosses, stream_id=stream_id)

    @commands.Component.listener()
    async def event_stream_offline(self, payload) -> None:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Events] Stream offline event received before services were initialized."
            )
            return

        broadcaster = getattr(payload, "broadcaster", None)
        broadcaster_id = getattr(broadcaster, "id", None)

        if broadcaster_id is None:
            broadcaster_id = getattr(payload, "broadcaster_id", None)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Events] Could not stop stream logger from payload: %r",
                payload
            )
            return

        broadcaster_id = str(broadcaster_id)
        channel_name = getattr(broadcaster, "name", None)

        LOGGER.info(
            "[Events] Stream ended for %s (%s).",
            channel_name or "unknown",
            broadcaster_id
        )

        await services.raid_bosses.cancel_announcements(broadcaster_id)
        await services.passive_points.stop_for_stream(broadcaster_id)
        await services.stream_logs.end_session(broadcaster_id)
