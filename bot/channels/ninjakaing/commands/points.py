from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile, FeatureName
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.points import PointsCommandHandler


class NinjakaingPointsCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="bread", invoke_fallback=True)
    async def bread(self, ctx: commands.Context, target: LocalizedUser = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_balance(ctx, target, "bread")

    @bread.command(name="leaderboard")
    async def bread_leaderboard(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_leaderboard(ctx, "bread")

    @bread.command(name="reset")
    async def bread_reset(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.reset_points(ctx, "bread")

    @bread.command(name="add")
    async def bread_add(self, ctx: commands.Context, target: LocalizedUser, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.add_points(ctx, target, amount, "bread")

    @bread.command(name="gamble")
    async def bread_gamble(self, ctx: commands.Context, amount: str) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.gamble(ctx, amount, "bread")

    @bread.group(name="duel", invoke_fallback=True)
    async def bread_duel(self, ctx: commands.Context, opponent: LocalizedUser = None, amount: str = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.create_duel(ctx, opponent, amount, "bread")

    @bread_duel.command(name="accept")
    async def bread_duel_accept(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.accept_duel(ctx, "bread")

    @bread_duel.command(name="decline")
    async def bread_duel_decline(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.decline_duel(ctx, "bread")
