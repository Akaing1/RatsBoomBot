from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile


class MeinyaCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)

    @commands.command(name="hbd")
    async def hbd(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await ctx.send("Happy Birthday Meinya!")

    @commands.command(name="throne")
    async def throne(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await ctx.send("If you would like to support my 2.0 model, head to my throne: https://throne.com/meinya/item/81c32121-0be2-44c6-b29f-be926b04b92b")
