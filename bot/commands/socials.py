from twitchio.ext import commands


class SocialCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_fallback=True)
    async def socials(self, ctx: commands.Context):
        if not self.bot.services:
            return

        settings = await self.bot.services.broadcaster_settings.get_settings(ctx.broadcaster.id)

        discord = settings.discord_url or "not set"
        youtube = settings.youtube_url or "not set"

        await ctx.reply(f"discord: {discord} | youtube: {youtube}")

    @socials.command(name="discord")
    async def socials_discord(self, ctx: commands.Context):
        if not self.bot.services:
            return

        settings = await self.bot.services.broadcaster_settings.get_settings(ctx.broadcaster.id)

        if not settings.discord_url:
            await ctx.reply("No Discord link has been set for this channel yet.")
            return

        await ctx.reply(f"Lost something? Maybe you left it in the basement: {settings.discord_url}")

    @socials.command(name="youtube")
    async def socials_youtube(self, ctx: commands.Context):
        if not self.bot.services:
            return

        settings = await self.bot.services.broadcaster_settings.get_settings(ctx.broadcaster.id)

        if not settings.youtube_url:
            await ctx.reply("No YouTube link has been set for this channel yet.")
            return

        await ctx.reply(f"Missed something? Go check out Rat's youtube! {settings.youtube_url}")
