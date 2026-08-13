from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile


class MeinyaCommands(ChannelComponent):

    def __init__(self, bot, profile: ChannelProfile, broadcaster_id: str):
        super().__init__(bot, profile, broadcaster_id)

    @commands.command(name="raid")
    async def raid(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await ctx.send("TombRaid GlitchCat PowerUpL NYXI RAID PowerUpR GlitchCat TombRaid")

    @commands.command(name="subraid")
    async def subraid(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await ctx.send("meinya3Sprays  meinya3Bark   Meinya sprays us if we don't raid  meinya3Sprays    meinya3Bark   Meinya sprays us if we don't raid  meinya3Sprays    meinya3Bark   Meinya sprays us if we don't raid")

