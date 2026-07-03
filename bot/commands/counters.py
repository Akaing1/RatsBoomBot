from twitchio.ext import commands


class CounterCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="explode")
    async def explode(self, ctx: commands.Context):
        if not self.bot.services:
            return

        exploded_count = await self.bot.services.counters.increment_counter("explode")

        await ctx.send(f"Rat has exploded {exploded_count} times.")

    @commands.command(name="reklop")
    async def reklop(self, ctx: commands.Context):
        if not self.bot.services:
            return

        reklop_count = await self.bot.services.counters.increment_counter("reklop")

        await ctx.send(f"Reklop is a femboy o7! He has been with {reklop_count} guys!")
