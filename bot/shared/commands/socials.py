import logging
from typing import TYPE_CHECKING

from twitchio.ext import commands

from bot.profiles import GlobalCommandGroup, get_active_profile, render_profile_message
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_group_enabled


LOGGER = logging.getLogger("RatBoomBot")


class SocialCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def send_message(ctx: commands.Context, template: str, **values) -> None:
        message = render_profile_message(template, **values)

        if message:
            await ctx.reply(message)

    async def get_settings(self, ctx: commands.Context) -> "BroadcasterSettings | None":
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Commands] Social command could not run because services are unavailable."
            )
            return None

        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Commands] Social command could not resolve its broadcaster."
            )
            return None

        if not is_global_group_enabled(self.bot, ctx, GlobalCommandGroup.SOCIALS):
            LOGGER.debug(
                "[Socials] Social commands are disabled for broadcaster %s.",
                broadcaster_id
            )
            return None

        try:
            return await services.broadcaster_settings.get_settings(broadcaster_id)
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to load social settings for broadcaster %s.",
                broadcaster_id
            )
            return None

    @commands.group(invoke_fallback=True)
    async def socials(self, ctx: commands.Context) -> None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        LOGGER.debug(
            "[Commands] User %s invoked !socials in broadcaster %s.",
            ctx.chatter.name,
            broadcaster_id or "unknown"
        )

        settings = await self.get_settings(ctx)

        if settings is None:
            return

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.warning("[Commands] Social command could not find a profile for broadcaster %s.", broadcaster_id)
            return

        discord = settings.discord_url or "not set"
        youtube = settings.youtube_url or "not set"

        await self.send_message(ctx, profile.social_messages.overview, discord_url=discord, youtube_url=youtube)

    @socials.command(name="discord")
    async def socials_discord(self, ctx: commands.Context) -> None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        LOGGER.debug(
            "[Commands] User %s invoked !socials discord in broadcaster %s.",
            ctx.chatter.name,
            broadcaster_id or "unknown"
        )

        settings = await self.get_settings(ctx)

        if settings is None:
            return

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.warning("[Commands] Discord command could not find a profile for broadcaster %s.", broadcaster_id)
            return

        if not settings.discord_url:
            LOGGER.debug(
                "[Commands] Discord URL is not configured for broadcaster %s.",
                broadcaster_id or "unknown"
            )

            await self.send_message(ctx, profile.social_messages.discord_unavailable)
            return

        await self.send_message(ctx, profile.social_messages.discord, discord_url=settings.discord_url)

    @socials.command(name="youtube")
    async def socials_youtube(self, ctx: commands.Context) -> None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        LOGGER.debug(
            "[Commands] User %s invoked !socials youtube in broadcaster %s.",
            ctx.chatter.name,
            broadcaster_id or "unknown"
        )

        settings = await self.get_settings(ctx)

        if settings is None:
            return

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.warning("[Commands] YouTube command could not find a profile for broadcaster %s.", broadcaster_id)
            return

        if not settings.youtube_url:
            LOGGER.debug(
                "[Commands] YouTube URL is not configured for broadcaster %s.",
                broadcaster_id or "unknown"
            )

            await self.send_message(ctx, profile.social_messages.youtube_unavailable)
            return

        await self.send_message(ctx, profile.social_messages.youtube, youtube_url=settings.youtube_url)
