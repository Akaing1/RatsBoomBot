import logging

from twitchio.ext import commands

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

        await services.stream_logs.end_session(broadcaster_id)
