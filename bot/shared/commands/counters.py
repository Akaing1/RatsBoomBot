import logging

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class CounterCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    async def increment_counter(self, ctx: commands.Context, counter_name: str) -> int | None:

        broadcaster_id = str(ctx.broadcaster.id)
        username = ctx.chatter.name

        if not self.bot.services:
            LOGGER.warning(
                "[Commands] !%s could not run because services are unavailable.",
                counter_name
            )
            return None

        LOGGER.debug(
            "[Commands] User %s invoked !%s in broadcaster %s.",
            username,
            counter_name,
            broadcaster_id
        )

        try:
            count = await self.bot.services.counters.increment_counter(
                counter_name
            )
        except Exception:
            LOGGER.exception(
                "[Counters] Failed to increment counter %s for broadcaster %s.",
                counter_name,
                broadcaster_id
            )
            return None

        LOGGER.info(
            "[Counters] User %s incremented counter %s to %d in broadcaster %s.",
            username,
            counter_name,
            count,
            broadcaster_id
        )

        return count

    @commands.command(name="explode", aliases=["rat"])
    async def explode(self, ctx: commands.Context):
        exploded_count = await self.increment_counter(
            ctx,
            "explode"
        )

        if exploded_count is None:
            return

        await ctx.send(
            f"Rat has exploded {exploded_count} times."
        )

    @commands.command(name="reklop")
    async def reklop(self, ctx: commands.Context):
        reklop_count = await self.increment_counter(
            ctx,
            "reklop"
        )

        if reklop_count is None:
            return

        await ctx.send(
            f"Reklop is a femboy o7! He has been with "
            f"{reklop_count} guys! ninjak83Yay2"
        )

    @commands.command(name="randy")
    async def randy(self, ctx: commands.Context):
        randy_count = await self.increment_counter(
            ctx,
            "randy"
        )

        if randy_count is None:
            return

        await ctx.send(
            f"Randy has inted {randy_count} times. "
            "He is a terrorist player and should be banned. ninjak83Sip"
        )

    @commands.command(name="car")
    async def car(self, ctx: commands.Context):
        car_count = await self.increment_counter(
            ctx,
            "car"
        )

        if car_count is None:
            return

        await ctx.send(
            f"Car has been blown up by a creeper "
            f"{car_count} times! ninjak83Heh"
        )
