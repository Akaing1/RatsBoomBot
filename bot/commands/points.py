import twitchio
from twitchio.ext import commands


class PointsCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="bread", invoke_fallback=True)
    async def bread(self, ctx: commands.Context):
        if not self.bot.services:
            return

        points = await self.bot.services.points.get_points(ctx.chatter.id)

        await ctx.reply(
            f"{ctx.chatter.name}, you have stolen {points} pieces of stale bread!"
        )

    @bread.command(name="leaderboard")
    async def bread_leaderboard(self, ctx: commands.Context):
        if not self.bot.services:
            return

        rows = await self.bot.services.points.get_leaderboard(limit=5)

        if not rows:
            await ctx.reply("No stale bread has been collected yet. What an upstanding citizen!")
            return

        leaderboard = " | ".join(
            f"{index + 1}. {row['username']}: {row['points']} bread"
            for index, row in enumerate(rows)
        )

        await ctx.reply(f"Top stale bread hoarders: {leaderboard}")

    @bread.command(name="reset")
    async def bread_reset(self, ctx: commands.Context):
        if not self.bot.services:
            return

        if ctx.chatter.id != ctx.broadcaster.id:
            await ctx.reply("Only the broadcaster can reset the stale bread stash.")
            return

        await self.bot.services.points.reset_all_points()

        await ctx.send("All stale bread has been thrown away. The leaderboard has been reset.")

    @bread.command(name="add")
    async def bread_add(self, ctx: commands.Context, user: twitchio.user, amount: int):
        if not self.bot.services:
            return

        is_broadcaster = ctx.chatter.id == ctx.broadcaster.id
        is_moderator = ctx.chatter.moderator

        if not is_moderator or not is_broadcaster:
            await ctx.reply("Only moderators can add stale bread to viewers.")
            return

        if amount <= 0:
            await ctx.reply("Bread amount must be greater than 0.")
            return

        await self.bot.services.points.add_points(
            user_id=user.id,
            username=user.name,
            amount=amount,
        )

        await ctx.send(f"{amount} pieces of stale bread have been added to {user.name}'s stash.")
