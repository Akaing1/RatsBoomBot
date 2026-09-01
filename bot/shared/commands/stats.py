import logging
from urllib.parse import quote

from twitchio.ext import commands

from bot.profiles import GlobalCommandName
from bot.shared.commands.helpers import is_global_command_enabled
from config.settings import settings

LOGGER = logging.getLogger("RatBoomBot")


class StatsCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def stats(self, ctx: commands.Context, username: str = "") -> None:
        if not is_global_command_enabled(self.bot, ctx, GlobalCommandName.STATS):
            return

        services = self.bot.services

        if services is None:
            return

        requested_name = username.strip().removeprefix("@").strip() or str(ctx.chatter.name)
        identity = await services.chatter_stats.resolve_identity(requested_name)

        if identity is None:
            await ctx.reply(f"I don't have a public chatter profile for {requested_name} yet.")
            return

        profile_name = str(identity["login"])
        profile_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/chatters/{quote(profile_name)}"
        await ctx.reply(f"View {identity['display_name']}'s RatsBoomBot profile: {profile_url}")

        LOGGER.debug("[Chatter Stats] User %s requested the public profile for %s.", ctx.chatter.name, profile_name)
