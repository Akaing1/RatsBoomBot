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

        await ctx.send(f"Reklop is a femboy o7! He has been with {reklop_count} guys! ninjak83Yay2 ")

    @commands.command(name="randy")
    async def randy(self, ctx: commands.Context):
        if not self.bot.services:
            return

        randy_count = await self.bot.services.counters.increment_counter("randy")

        await ctx.send(f"Randy has inted {randy_count} times. He is a terrorist player and should be banned. ninjak83Sip")

    @commands.command(name="car")
    async def car(self, ctx: commands.Context):
        if not self.bot.services:
            return

        car_count = await self.bot.services.counters.increment_counter("car")

        await ctx.send(f"Car has been blown up by a creeper {car_count} times! ninjak83Heh")
