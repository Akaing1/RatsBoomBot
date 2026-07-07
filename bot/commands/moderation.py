import random

from twitchio import User
from twitchio.ext import commands


class ModerationCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="kamikaze")
    async def kamikaze(self, ctx: commands.Context, target: User = None):
        if not self.bot.services:
            return

        DURATION = 10  # seconds
        caller = ctx.chatter
        broadcaster = ctx.broadcaster
        channel = self.bot.create_partialuser(broadcaster.id)

        if target is None or caller.id == target.id:
            await ctx.reply("You bomb yourself...")
            await channel.timeout_user(
                moderator=broadcaster.id,
                user=caller.id,
                duration=DURATION,
                reason="Blown up."
            )
            return

        isModerator = getattr(target, "moderator", False)
        if target.id == broadcaster.id or isModerator:
            await ctx.reply("You cannot bomb this target, try someone else.")
            return

        bomb = random.randint(1, 100)

        if bomb > 75:
            await ctx.send(f"{target.name} has been blown up and timed out for {DURATION} seconds.")
            await channel.timeout_user(
                moderator=broadcaster.id,
                user=target.id,
                duration=DURATION,
                reason="Blown up."
            )
            return

        await channel.timeout_user(
            moderator=broadcaster.id,
            user=ctx.chatter.id,
            duration=DURATION,
            reason="Blown up."
        )

        await ctx.send(f"{ctx.chatter.name} missed and blew themselves up~ they have been timed out for {DURATION} seconds.")
