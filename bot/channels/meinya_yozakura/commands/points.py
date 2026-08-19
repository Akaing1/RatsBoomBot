from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile, FeatureName
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.points import PointsCommandHandler


class MeinyaPointsCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="petals", invoke_fallback=True)
    async def petals(self, ctx: commands.Context, target: LocalizedUser = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_balance(ctx, target, "petals")

    @petals.command(name="leaderboard")
    async def petals_leaderboard(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_leaderboard(ctx, "petals")

    @petals.command(name="reset")
    async def petals_reset(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.reset_points(ctx, "petals")

    @petals.command(name="add")
    async def petals_add(self, ctx: commands.Context, target: LocalizedUser, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.add_points(ctx, target, amount, "petals")

    @petals.command(name="gamble")
    async def petals_gamble(self, ctx: commands.Context, amount: str) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.gamble(ctx, amount, "petals")

    @petals.group(name="duel", invoke_fallback=True)
    async def petals_duel(self, ctx: commands.Context, opponent: LocalizedUser = None, amount: str = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.create_duel(ctx, opponent, amount, "petals")

    @petals_duel.command(name="accept")
    async def petals_duel_accept(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.accept_duel(ctx, "petals")

    @petals_duel.command(name="decline")
    async def petals_duel_decline(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.decline_duel(ctx, "petals")
