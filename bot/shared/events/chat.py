import logging

from twitchio.ext import commands

LOGGER = logging.getLogger("Bot")


class ChatEvents(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload):
        broadcaster_id = str(payload.broadcaster.id)

        LOGGER.info(
            "[%s] %s: %s",
            payload.broadcaster.name,
            payload.chatter.name,
            payload.text
        )

        if not self.bot.services:
            return

        self.bot.services.stream_logs.write(
            broadcaster_id,
            "CHAT",
            f"{payload.chatter.name}: {payload.text}"
        )

        self.bot.services.timers.track_message(payload)
        await self.bot.services.points.track_message(payload)
        