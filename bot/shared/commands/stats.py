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
    async def stats(self, ctx: commands.Context) -> None:
        if not is_global_command_enabled(self.bot, ctx, GlobalCommandName.STATS):
            return

        services = self.bot.services

        if services is None:
            return

        broadcaster = getattr(ctx, "broadcaster", None)
        broadcaster_id = str(getattr(broadcaster, "id", ""))
        current_channel = services.broadcasters.get_broadcasters().get(broadcaster_id)
        channel_login = getattr(current_channel, "login", None) or getattr(broadcaster, "name", None)

        if not channel_login:
            await ctx.reply("I can't find this channel's chatter profile right now.")
            return

        profile_name = await self._profile_login(ctx)
        profile_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/chatters/{quote(profile_name, safe='')}/channels/{quote(str(channel_login), safe='')}"
        await ctx.reply(f"Your stats in {getattr(current_channel, 'display_name', None) or channel_login}: {profile_url}")

        LOGGER.debug("[Chatter Stats] User %s requested their channel profile in %s.", ctx.chatter.name, channel_login)

    @commands.command()
    async def me(self, ctx: commands.Context) -> None:
        if not is_global_command_enabled(self.bot, ctx, GlobalCommandName.ME):
            return

        profile_name = await self._profile_login(ctx)
        profile_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/chatters/{quote(profile_name, safe='')}"
        await ctx.reply(f"Your RatsBoomBot profile: {profile_url}")

        LOGGER.debug("[Chatter Stats] User %s requested their global profile.", ctx.chatter.name)

    async def _profile_login(self, ctx: commands.Context) -> str:
        identity = await self.bot.services.chatter_stats.resolve_identity(str(ctx.chatter.id))
        return str(identity["login"]) if identity is not None else str(ctx.chatter.name)
