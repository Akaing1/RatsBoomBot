from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile, FeatureName
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.points import PointsCommandHandler


class OnedaybreadPointsCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="mews", invoke_fallback=True)
    async def points(self, ctx: commands.Context, target: LocalizedUser = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_balance(ctx, target, "mews")

    @points.command(name="leaderboard")
    async def points_leaderboard(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_leaderboard(ctx, "mews")

    @points.command(name="reset")
    async def points_reset(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.reset_points(ctx, "mews")

    @points.command(name="add")
    async def points_add(self, ctx: commands.Context, target: LocalizedUser, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.add_points(ctx, target, amount, "mews")

    @points.command(name="gamble")
    async def points_gamble(self, ctx: commands.Context, amount: str) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.gamble(ctx, amount, "mews")

    @points.group(name="duel", invoke_fallback=True)
    async def points_duel(self, ctx: commands.Context, opponent: LocalizedUser = None, amount: str = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.create_duel(ctx, opponent, amount, "mews")

    @points_duel.command(name="accept")
    async def points_duel_accept(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.accept_duel(ctx, "mews")

    @points_duel.command(name="decline")
    async def points_duel_decline(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.decline_duel(ctx, "mews")
