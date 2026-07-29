from twitchio.ext import commands


class CommunityEvents(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.Component.listener()
    async def event_follow(self, payload):
        broadcaster_id = str(payload.broadcaster.id)
        username = payload.user.name

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "FOLLOW",
                f"{username} followed the channel."
            )

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=(
                f"{username} has snuck their way into the basement! "
                f"Thanks for following!"
            )
        )

    @commands.Component.listener()
    async def event_subscription(self, payload):
        broadcaster_id = str(payload.broadcaster.id)
        username = payload.user.name

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "SUBSCRIPTION",
                f"{username} subscribed."
            )

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=f"{username} has subscribed! Rats stronk together!"
        )

    @commands.Component.listener()
    async def event_subscription_message(self, payload):
        broadcaster_id = str(payload.broadcaster.id)
        username = payload.user.name

        if self.bot.services:
            self.bot.services.stream_logs.write(
                broadcaster_id,
                "RESUB",
                f"{username} resubscribed for {payload.cumulative_months} months."
            )

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        await broadcaster.send_message(
            sender=self.bot.user,
            message=(
                f"{username} resubscribed for "
                f"{payload.cumulative_months} months! "
                f"Thank you for your continued support!"
            )
        )
        