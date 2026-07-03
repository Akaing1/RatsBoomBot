from twitchio.ext import commands


class SocialCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_fallback=True)
    async def socials(self, ctx: commands.Context):
        await ctx.send("discord.gg/... | youtube.com/...")

    @socials.command(name="discord")
    async def socials_discord(self, ctx: commands.Context):
        await ctx.send("discord.gg/...")
