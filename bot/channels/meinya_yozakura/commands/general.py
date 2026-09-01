from twitchio.ext import commands

from bot.channels.component import ChannelComponent
from bot.profiles import ChannelProfile
from bot.shared.commands.socials import send_discord_response, send_youtube_response


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

    @commands.command(name="discord")
    async def discord(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await send_discord_response(self.bot, ctx)

    @commands.command(name="youtube")
    async def youtube(self, ctx: commands.Context) -> None:
        if not await self.require_profile_channel(ctx):
            return

        await send_youtube_response(self.bot, ctx)
