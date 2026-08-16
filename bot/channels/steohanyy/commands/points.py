from twitchio import User
from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile, FeatureName
from bot.shared.commands.points import PointsCommandHandler


class SteohanyydrinksCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="drinks", invoke_fallback=True)
    async def drinks(self, ctx: commands.Context, target: User = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_balance(ctx, target, "drinks")

    @drinks.command(name="leaderboard")
    async def drinks_leaderboard(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_leaderboard(ctx, "drinks")

    @drinks.command(name="reset")
    async def drinks_reset(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.reset_points(ctx, "drinks")

    @drinks.command(name="add")
    async def drinks_add(self, ctx: commands.Context, target: User, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.add_points(ctx, target, amount, "drinks")

    @drinks.command(name="gamble")
    async def drinks_gamble(self, ctx: commands.Context, amount: str) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.gamble(ctx, amount, "drinks")

    @drinks.group(name="duel", invoke_fallback=True)
    async def drinks_duel(self, ctx: commands.Context, opponent: User = None, amount: str = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.create_duel(ctx, opponent, amount, "drinks")

    @drinks_duel.command(name="accept")
    async def drinks_duel_accept(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.accept_duel(ctx, "drinks")

    @drinks_duel.command(name="decline")
    async def drinks_duel_decline(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.decline_duel(ctx, "drinks")
