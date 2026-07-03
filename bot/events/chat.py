from twitchio.ext import commands


class ChatEvents(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload) -> None:
        print(
            f"[{payload.broadcaster.name}] "
            f"{payload.chatter.name}: "
            f"{payload.text}"
        )

        if self.bot.services:
            self.bot.services.timers.track_message(payload)