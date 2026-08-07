from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile


class NinjakaingCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)

    @commands.command(name="ninjatest")
    async def ninja_test(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await ctx.send("The Ninjakaing channel profile is loaded!")
        