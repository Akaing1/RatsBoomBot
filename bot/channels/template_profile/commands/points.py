from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile, FeatureName
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.points import PointsCommandHandler


class TemplatePointsCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="placeholder_points", invoke_fallback=True)
    async def points(self, ctx: commands.Context, target: LocalizedUser = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_balance(ctx, target, "placeholder_points")

    @points.command(name="leaderboard")
    async def points_leaderboard(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_leaderboard(ctx, "placeholder_points")

    @points.command(name="reset")
    async def points_reset(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.reset_points(ctx, "placeholder_points")

    @points.command(name="add")
    async def points_add(self, ctx: commands.Context, target: LocalizedUser, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.add_points(ctx, target, amount, "placeholder_points")

    @points.command(name="give")
    async def points_give(self, ctx: commands.Context, target: LocalizedUser, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.give_points(ctx, target, amount, "placeholder_points")

    @points.command(name="gamble")
    async def points_gamble(self, ctx: commands.Context, amount: str) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.gamble(ctx, amount, "placeholder_points")

    @points.group(name="duel", invoke_fallback=True)
    async def points_duel(self, ctx: commands.Context, opponent: LocalizedUser = None, amount: str = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.create_duel(ctx, opponent, amount, "placeholder_points")

    @points_duel.command(name="accept")
    async def points_duel_accept(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.accept_duel(ctx, "placeholder_points")

    @points_duel.command(name="decline")
    async def points_duel_decline(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.decline_duel(ctx, "placeholder_points")
