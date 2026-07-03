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
