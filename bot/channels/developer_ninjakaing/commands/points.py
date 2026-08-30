from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile, FeatureName
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.points import PointsCommandHandler


class DeveloperPointsCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)
        self.handler = PointsCommandHandler(bot)

    @commands.group(name="ores", invoke_fallback=True)
    async def ores(self, ctx: commands.Context, target: LocalizedUser = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_balance(ctx, target, "ores")

    @ores.command(name="leaderboard")
    async def ores_leaderboard(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.show_leaderboard(ctx, "ores")

    @ores.command(name="reset")
    async def ores_reset(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.reset_points(ctx, "ores")

    @ores.command(name="add")
    async def ores_add(self, ctx: commands.Context, target: LocalizedUser, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.add_points(ctx, target, amount, "ores")

    @ores.command(name="give")
    async def ores_give(self, ctx: commands.Context, target: LocalizedUser, amount: int) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.give_points(ctx, target, amount, "ores")

    @ores.command(name="gamble")
    async def ores_gamble(self, ctx: commands.Context, amount: str) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.gamble(ctx, amount, "ores")

    @ores.group(name="duel", invoke_fallback=True)
    async def ores_duel(self, ctx: commands.Context, opponent: LocalizedUser = None, amount: str = None) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.create_duel(ctx, opponent, amount, "ores")

    @ores_duel.command(name="accept")
    async def ores_duel_accept(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.accept_duel(ctx, "ores")

    @ores_duel.command(name="decline")
    async def ores_duel_decline(self, ctx: commands.Context) -> None:
        if not await self.require_feature(ctx, FeatureName.POINTS):
            return

        await self.handler.decline_duel(ctx, "ores")
