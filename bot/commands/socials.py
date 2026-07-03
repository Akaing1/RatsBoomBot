from twitchio.ext import commands

from config.settings import settings


class SocialCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_fallback=True)
    async def socials(self, ctx: commands.Context):
        await ctx.reply(f"discord : {settings.DISCORD}. | youtube : {settings.YOUTUBE}")

    @socials.command(name="discord")
    async def socials_discord(self, ctx: commands.Context):
        await ctx.reply(f"Lost something? Maybe you left it in the basement: {settings.DISCORD}")

    @socials.command(name="youtube")
    async def socials_youtube(self, ctx: commands.Context):
        await ctx.reply(f"Missed something? Go check out Rat's youtube! {settings.YOUTUBE}")
