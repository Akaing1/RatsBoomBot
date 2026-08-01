import logging

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class SocialCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    async def get_settings(self, ctx: commands.Context):

        if not self.bot.services:
            LOGGER.warning(
                "[Commands] Social command could not run because services are unavailable."
            )
            return None

        broadcaster_id = str(ctx.broadcaster.id)

        try:
            return await self.bot.services.broadcaster_settings.get_settings(
                broadcaster_id
            )
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to load social settings for broadcaster %s.",
                broadcaster_id
            )
            return None

    @commands.group(invoke_fallback=True)
    async def socials(self, ctx: commands.Context):
        LOGGER.debug(
            "[Commands] User %s invoked !socials in broadcaster %s.",
            ctx.chatter.name,
            ctx.broadcaster.id
        )

        settings = await self.get_settings(ctx)

        if settings is None:
            return

        discord = settings.discord_url or "not set"
        youtube = settings.youtube_url or "not set"

        await ctx.reply(
            f"discord: {discord} | youtube: {youtube}"
        )

    @socials.command(name="discord")
    async def socials_discord(self, ctx: commands.Context):
        LOGGER.debug(
            "[Commands] User %s invoked !socials discord in broadcaster %s.",
            ctx.chatter.name,
            ctx.broadcaster.id
        )

        settings = await self.get_settings(ctx)

        if settings is None:
            return

        if not settings.discord_url:
            LOGGER.debug(
                "[Commands] Discord URL is not configured for broadcaster %s.",
                ctx.broadcaster.id
            )

            await ctx.reply(
                "No Discord link has been set for this channel yet."
            )
            return

        await ctx.reply(
            "Lost something? Maybe you left it in the basement: "
            f"{settings.discord_url}"
        )

    @socials.command(name="youtube")
    async def socials_youtube(self, ctx: commands.Context):
        LOGGER.debug(
            "[Commands] User %s invoked !socials youtube in broadcaster %s.",
            ctx.chatter.name,
            ctx.broadcaster.id
        )

        settings = await self.get_settings(ctx)

        if settings is None:
            return

        if not settings.youtube_url:
            LOGGER.debug(
                "[Commands] YouTube URL is not configured for broadcaster %s.",
                ctx.broadcaster.id
            )

            await ctx.reply(
                "No YouTube link has been set for this channel yet."
            )
            return

        await ctx.reply(
            "Missed something? Go check out Rat's youtube! "
            f"{settings.youtube_url}"
        )
