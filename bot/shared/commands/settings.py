import logging

from twitchio.ext import commands

from bot.profiles import GlobalCommandGroup
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_group_enabled

LOGGER = logging.getLogger("RatBoomBot")

VALID_TIMER_STATUSES = {
    "on",
    "off",
    "enable",
    "disable",
    "enabled",
    "disabled"
}

ENABLED_TIMER_STATUSES = {
    "on",
    "enable",
    "enabled"
}


def get_chatter(ctx: commands.Context):
    return getattr(ctx, "chatter", None) or getattr(ctx, "author", None)


def get_chatter_name(ctx: commands.Context) -> str:
    chatter = get_chatter(ctx)

    if chatter is None:
        return "unknown"

    return chatter.name


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:
    chatter = get_chatter(ctx)
    broadcaster_id = get_context_broadcaster_id(ctx)

    if chatter is None:
        return False

    if broadcaster_id is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = str(chatter.id) == broadcaster_id

    return is_moderator or is_broadcaster


class SettingsCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    def get_context(self, ctx: commands.Context, command_name: str) -> str | None:
        if self.bot.services is None:
            LOGGER.warning(
                "[Commands] !%s could not run because services are unavailable.",
                command_name
            )
            return None

        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Commands] !%s could not resolve its broadcaster.",
                command_name
            )
            return None

        if not is_global_group_enabled(self.bot, ctx, GlobalCommandGroup.SETTINGS):
            LOGGER.debug(
                "[Settings] Settings commands are disabled for broadcaster %s because the channel profile is disabled.",
                broadcaster_id
            )
            return None

        return broadcaster_id

    def has_permission(self, ctx: commands.Context, command_name: str) -> bool:
        if is_mod_or_broadcaster(ctx):
            return True

        LOGGER.info(
            "[Commands] User %s was denied permission to run !%s in broadcaster %s.",
            get_chatter_name(ctx),
            command_name,
            get_context_broadcaster_id(ctx) or "unknown"
        )

        return False

    @commands.group(name="set", invoke_fallback=True)
    async def set_channel(self, ctx: commands.Context) -> None:
        broadcaster_id = self.get_context(ctx, "set")

        if broadcaster_id is None:
            return

        if not self.has_permission(ctx, "set"):
            await ctx.reply("Only the broadcaster or mods can change the stream game or title.")
            return

        await ctx.reply("Use !set game <game name> or !set title <stream title>.")

    @set_channel.command(name="game")
    async def set_game(self, ctx: commands.Context, *, game_name: str | None = None) -> None:
        broadcaster_id = self.get_context(ctx, "set game")

        if broadcaster_id is None:
            return

        username = get_chatter_name(ctx)

        if not self.has_permission(ctx, "set game"):
            await ctx.reply("Only the broadcaster or mods can change the stream game.")
            return

        game_name = (game_name or "").strip()

        if not game_name:
            await ctx.reply("Use it like this: !set game <game name>")
            return

        try:
            game = await self.bot.fetch_game(name=game_name)
        except Exception:
            LOGGER.exception("[Settings] Failed to find game %s for broadcaster %s.", game_name, broadcaster_id)
            await ctx.reply("Twitch could not look up that game right now. Please try again later.")
            return

        if game is None:
            await ctx.reply(f'I could not find a Twitch category named "{game_name}".')
            return

        try:
            broadcaster = self.bot.create_partialuser(broadcaster_id)
            await broadcaster.modify_channel(game_id=str(game.id))
        except Exception as error:
            LOGGER.exception("[Settings] Failed to update the game for broadcaster %s.", broadcaster_id)
            await self._send_update_error(ctx, error, "game")
            return

        resolved_name = getattr(game, "name", game_name)
        LOGGER.info("[Settings] User %s changed broadcaster %s's game to %s (%s).", username, broadcaster_id, resolved_name, game.id, extra={"broadcaster_id": broadcaster_id})
        await ctx.reply(f'Stream game updated to "{resolved_name}".')

    @set_channel.command(name="title")
    async def set_title(self, ctx: commands.Context, *, title: str | None = None) -> None:
        broadcaster_id = self.get_context(ctx, "set title")

        if broadcaster_id is None:
            return

        username = get_chatter_name(ctx)

        if not self.has_permission(ctx, "set title"):
            await ctx.reply("Only the broadcaster or mods can change the stream title.")
            return

        title = (title or "").strip()

        if not title:
            await ctx.reply("Use it like this: !set title <stream title>")
            return

        try:
            broadcaster = self.bot.create_partialuser(broadcaster_id)
            await broadcaster.modify_channel(title=title)
        except Exception as error:
            LOGGER.exception("[Settings] Failed to update the title for broadcaster %s.", broadcaster_id)
            await self._send_update_error(ctx, error, "title")
            return

        LOGGER.info("[Settings] User %s changed broadcaster %s's stream title to %s.", username, broadcaster_id, title, extra={"broadcaster_id": broadcaster_id})
        await ctx.reply(f'Stream title updated to "{title}".')

    @staticmethod
    async def _send_update_error(ctx: commands.Context, error: Exception, field_name: str) -> None:
        if getattr(error, "status", None) in {401, 403}:
            await ctx.reply("The broadcaster needs to reconnect their Twitch account before I can update stream information.")
            return

        await ctx.reply(f"Twitch could not update the stream {field_name}. Please try again later.")

    @commands.command(name="setdiscord")
    async def set_discord(self, ctx: commands.Context, url: str | None = None) -> None:
        broadcaster_id = self.get_context(ctx, "setdiscord")

        if broadcaster_id is None:
            return

        services = self.bot.services
        username = get_chatter_name(ctx)

        LOGGER.debug(
            "[Commands] User %s invoked !setdiscord in broadcaster %s.",
            username,
            broadcaster_id
        )

        if not self.has_permission(ctx, "setdiscord"):
            await ctx.reply("Only the broadcaster or mods can set the Discord link.")
            return

        if not url:
            LOGGER.debug(
                "[Commands] !setdiscord was invoked without a URL in broadcaster %s.",
                broadcaster_id
            )

            await ctx.reply("Use it like this: !setdiscord https://discord.gg/yourlink")
            return

        try:
            await services.broadcaster_settings.set_discord_url(broadcaster_id=broadcaster_id, discord_url=url)
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to update Discord URL for broadcaster %s.",
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Commands] User %s updated the Discord URL for broadcaster %s.",
            username,
            broadcaster_id
        )

        await ctx.reply("Discord link updated for this channel.")

    @commands.command(name="setyoutube")
    async def set_youtube(self, ctx: commands.Context, url: str | None = None) -> None:
        broadcaster_id = self.get_context(ctx, "setyoutube")

        if broadcaster_id is None:
            return

        services = self.bot.services
        username = get_chatter_name(ctx)

        LOGGER.debug(
            "[Commands] User %s invoked !setyoutube in broadcaster %s.",
            username,
            broadcaster_id
        )

        if not self.has_permission(ctx, "setyoutube"):
            await ctx.reply("Only the broadcaster or mods can set the YouTube link.")
            return

        if not url:
            LOGGER.debug(
                "[Commands] !setyoutube was invoked without a URL in broadcaster %s.",
                broadcaster_id
            )

            await ctx.reply("Use it like this: !setyoutube https://youtube.com/@yourchannel")
            return

        try:
            await services.broadcaster_settings.set_youtube_url(broadcaster_id=broadcaster_id, youtube_url=url)
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to update YouTube URL for broadcaster %s.",
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Commands] User %s updated the YouTube URL for broadcaster %s.",
            username,
            broadcaster_id
        )

        await ctx.reply("YouTube link updated for this channel.")

    @commands.command(name="timers")
    async def timers(self, ctx: commands.Context, status: str | None = None) -> None:
        broadcaster_id = self.get_context(ctx, "timers")

        if broadcaster_id is None:
            return

        services = self.bot.services
        username = get_chatter_name(ctx)

        LOGGER.debug(
            "[Commands] User %s invoked !timers in broadcaster %s with status %s.",
            username,
            broadcaster_id,
            status or "current"
        )

        if not self.has_permission(ctx, "timers"):
            await ctx.reply("Only the broadcaster or mods can change timer settings.")
            return

        if status is None:
            try:
                settings = await services.broadcaster_settings.get_settings(broadcaster_id)
            except Exception:
                LOGGER.exception(
                    "[Commands] Failed to load timer settings for broadcaster %s.",
                    broadcaster_id
                )
                return

            if settings.timers_enabled:
                state = "enabled"
            else:
                state = "disabled"

            await ctx.reply(f"Timers are currently {state} for this channel.")
            return

        normalized_status = status.lower().strip()

        if normalized_status not in VALID_TIMER_STATUSES:
            LOGGER.debug(
                "[Commands] User %s supplied invalid timer status %s in broadcaster %s.",
                username,
                status,
                broadcaster_id
            )

            await ctx.reply("Use it like this: !timers on or !timers off")
            return

        enabled = normalized_status in ENABLED_TIMER_STATUSES

        try:
            await services.broadcaster_settings.set_timers_enabled(broadcaster_id=broadcaster_id, enabled=enabled)
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to update timer settings for broadcaster %s.",
                broadcaster_id
            )
            return

        if enabled:
            state = "enabled"
        else:
            state = "disabled"

        LOGGER.info(
            "[Commands] User %s %s timers for broadcaster %s.",
            username,
            state,
            broadcaster_id
        )

        await ctx.reply(f"Timers are now {state} for this channel.")
