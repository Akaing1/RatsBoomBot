from twitchio.ext import commands


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

        timer_component = self.bot.get_component("AnnouncementTimers")

        if timer_component:
            timer_component.track_message(payload)