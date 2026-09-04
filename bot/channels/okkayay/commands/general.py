from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile


class OkkayayCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)

    @commands.command(name="oktest")
    async def ok_test(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await ctx.send("Okkayay is loaded!")
