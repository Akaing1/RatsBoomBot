import logging

from twitchio.ext import commands

from bot.profiles import get_active_profile
from bot.shared.commands.helpers import get_context_broadcaster_id

LOGGER = logging.getLogger("RatBoomBot")


class CounterCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    async def increment_counter(self, ctx: commands.Context, counter_name: str) -> int | None:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Commands] !%s could not run because services are unavailable.",
                counter_name
            )
            return None

        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Commands] !%s could not resolve its broadcaster.",
                counter_name
            )
            return None

        profile = get_active_profile(broadcaster_id)

        if profile is None or not profile.shared_counters_enabled:
            LOGGER.debug(
                "[Counters] Private command !%s is unavailable for broadcaster %s.",
                counter_name,
                broadcaster_id
            )
            return None

        username = ctx.chatter.name

        LOGGER.debug(
            "[Commands] User %s invoked !%s in broadcaster %s.",
            username,
            counter_name,
            broadcaster_id
        )

        try:
            count = await services.counters.increment_counter(counter_name)
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
    async def explode(self, ctx: commands.Context) -> None:
        exploded_count = await self.increment_counter(ctx, "explode")

        if exploded_count is None:
            return

        await ctx.send(f"Rat has exploded {exploded_count} times.")

    @commands.command(name="reklop")
    async def reklop(self, ctx: commands.Context) -> None:
        reklop_count = await self.increment_counter(ctx, "reklop")

        if reklop_count is None:
            return

        await ctx.send(
            f"Reklop is a femboy o7! He has been with "
            f"{reklop_count} guys!"
        )

    @commands.command(name="randy")
    async def randy(self, ctx: commands.Context) -> None:
        randy_count = await self.increment_counter(ctx, "randy")

        if randy_count is None:
            return

        await ctx.send(
            f"Randy has inted {randy_count} times. "
            "He is a terrorist player and should be banned."
        )

    @commands.command(name="bark", aliases=["wxlfiix"])
    async def bark(self, ctx: commands.Context) -> None:
        bark_count = await self.increment_counter(ctx, "wxlfiix")

        if bark_count is None:
            return

        await ctx.send(f"There have been {bark_count} barking incidents! Someone stop @WxlfiiX!")

    @commands.command(name="car")
    async def car(self, ctx: commands.Context) -> None:
        car_count = await self.increment_counter(ctx, "car")

        if car_count is None:
            return

        await ctx.send(
            f"Car has been blown up by a creeper "
            f"{car_count} times!"
        )
