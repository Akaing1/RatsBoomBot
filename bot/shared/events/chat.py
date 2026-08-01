import logging

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class ChatEvents(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload):

        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name
        chatter_name = payload.chatter.name
        message = payload.text

        LOGGER.debug(
            "[Chat] [%s] %s: %s",
            broadcaster_name,
            chatter_name,
            message
        )

        if not self.bot.services:
            LOGGER.warning(
                "[Chat] Received chat message before services were initialized."
            )
            return

        self.bot.services.stream_logs.write(
            broadcaster_id,
            "CHAT",
            f"{chatter_name}: {message}"
        )

        self.bot.services.timers.track_message(payload)

        try:
            await self.bot.services.points.track_message(payload)
        except Exception:
            LOGGER.exception(
                "[Chat] Failed to process message rewards for %s in %s.",
                chatter_name,
                broadcaster_name
            )
