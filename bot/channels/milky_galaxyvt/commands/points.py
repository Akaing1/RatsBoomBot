from twitchio import User
from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile, FeatureName
from bot.shared.commands.points import PointsCommandHandler


class MilkyGalaxyPointsCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="shards", invoke_fallback=True)
    async def shards(self, ctx: commands.Context, target: User = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_balance(ctx, target, "shards")

    @shards.command(name="leaderboard")
    async def shards_leaderboard(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_leaderboard(ctx, "shards")

    @shards.command(name="reset")
    async def shards_reset(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.reset_points(ctx, "shards")

    @shards.command(name="add")
    async def shards_add(self, ctx: commands.Context, target: User, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.add_points(ctx, target, amount, "shards")

    @shards.command(name="gamble")
    async def shards_gamble(self, ctx: commands.Context, amount: str) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.gamble(ctx, amount, "shards")

    @shards.group(name="duel", invoke_fallback=True)
    async def shards_duel(self, ctx: commands.Context, opponent: User = None, amount: str = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.create_duel(ctx, opponent, amount, "shards")

    @shards_duel.command(name="accept")
    async def shards_duel_accept(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.accept_duel(ctx, "shards")

    @shards_duel.command(name="decline")
    async def shards_duel_decline(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.decline_duel(ctx, "shards")
