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

        if self.bot.services:
            self.bot.services.timers.track_message(payload)
            await self.bot.services.points.track_message(payload)

    @commands.Component.listener()
    async def event_follow(self, payload):
        broadcaster = self.bot.create_partialuser(id=payload.broadcaster.id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=f"{payload.user.name} has snuck their way into the basement! Thanks for following!"
        )

    @commands.Component.listener()
    async def event_subscription(self, payload):
        broadcaster = self.bot.create_partialuser(id=payload.broadcaster.id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=f"{payload.user.name} has subscribed! Rats stronk together!"
        )

    @commands.Component.listener()
    async def event_subscription_message(self, payload):
        broadcaster = self.bot.create_partialuser(id=payload.broadcaster.id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=(
                f"{payload.user.name} resubscribed for "
                f"{payload.cumulative_months} months! "
                f"Thank you for your continued support!"
            )
        )
