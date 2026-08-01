import logging

from twitchio.ext import commands

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


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:

    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = str(chatter.id) == str(ctx.broadcaster.id)

    return is_moderator or is_broadcaster


class SettingsCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    def services_available(self, command_name: str) -> bool:

        if self.bot.services:
            return True

        LOGGER.warning(
            "[Commands] !%s could not run because services are unavailable.",
            command_name
        )

        return False

    def has_permission(self, ctx: commands.Context, command_name: str) -> bool:

        if is_mod_or_broadcaster(ctx):
            return True

        LOGGER.info(
            "[Commands] User %s was denied permission to run !%s in broadcaster %s.",
            ctx.chatter.name,
            command_name,
            ctx.broadcaster.id
        )

        return False

    @commands.command(name="setdiscord")
    async def set_discord(self, ctx: commands.Context, url: str | None = None):
        broadcaster_id = str(ctx.broadcaster.id)

        LOGGER.debug(
            "[Commands] User %s invoked !setdiscord in broadcaster %s.",
            ctx.chatter.name,
            broadcaster_id
        )

        if not self.services_available("setdiscord"):
            return

        if not self.has_permission(ctx, "setdiscord"):
            await ctx.reply(
                "Only the broadcaster or mods can set the Discord link."
            )
            return

        if not url:
            LOGGER.debug(
                "[Commands] !setdiscord was invoked without a URL in broadcaster %s.",
                broadcaster_id
            )

            await ctx.reply(
                "Use it like this: !setdiscord https://discord.gg/yourlink"
            )
            return

        try:
            await self.bot.services.broadcaster_settings.set_discord_url(
                broadcaster_id=broadcaster_id,
                discord_url=url
            )
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to update Discord URL for broadcaster %s.",
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Commands] User %s updated the Discord URL for broadcaster %s.",
            ctx.chatter.name,
            broadcaster_id
        )

        await ctx.reply(
            "Discord link updated for this channel."
        )

    @commands.command(name="setyoutube")
    async def set_youtube(self, ctx: commands.Context, url: str | None = None):
        broadcaster_id = str(ctx.broadcaster.id)

        LOGGER.debug(
            "[Commands] User %s invoked !setyoutube in broadcaster %s.",
            ctx.chatter.name,
            broadcaster_id
        )

        if not self.services_available("setyoutube"):
            return

        if not self.has_permission(ctx, "setyoutube"):
            await ctx.reply(
                "Only the broadcaster or mods can set the YouTube link."
            )
            return

        if not url:
            LOGGER.debug(
                "[Commands] !setyoutube was invoked without a URL in broadcaster %s.",
                broadcaster_id
            )

            await ctx.reply(
                "Use it like this: !setyoutube https://youtube.com/@yourchannel"
            )
            return

        try:
            await self.bot.services.broadcaster_settings.set_youtube_url(
                broadcaster_id=broadcaster_id,
                youtube_url=url
            )
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to update YouTube URL for broadcaster %s.",
                broadcaster_id
            )
            return

        LOGGER.info(
            "[Commands] User %s updated the YouTube URL for broadcaster %s.",
            ctx.chatter.name,
            broadcaster_id
        )

        await ctx.reply(
            "YouTube link updated for this channel."
        )

    @commands.command(name="timers")
    async def timers(self, ctx: commands.Context, status: str | None = None):
        broadcaster_id = str(ctx.broadcaster.id)

        LOGGER.debug(
            "[Commands] User %s invoked !timers in broadcaster %s with status %s.",
            ctx.chatter.name,
            broadcaster_id,
            status or "current"
        )

        if not self.services_available("timers"):
            return

        if not self.has_permission(ctx, "timers"):
            await ctx.reply(
                "Only the broadcaster or mods can change timer settings."
            )
            return

        if status is None:
            try:
                settings = await self.bot.services.broadcaster_settings.get_settings(
                    broadcaster_id
                )
            except Exception:
                LOGGER.exception(
                    "[Commands] Failed to load timer settings for broadcaster %s.",
                    broadcaster_id
                )
                return

            state = "enabled" if settings.timers_enabled else "disabled"

            await ctx.reply(
                f"Timers are currently {state} for this channel."
            )
            return

        normalized_status = status.lower().strip()

        if normalized_status not in VALID_TIMER_STATUSES:
            LOGGER.debug(
                "[Commands] User %s supplied invalid timer status %s in broadcaster %s.",
                ctx.chatter.name,
                status,
                broadcaster_id
            )

            await ctx.reply(
                "Use it like this: !timers on or !timers off"
            )
            return

        enabled = normalized_status in ENABLED_TIMER_STATUSES

        try:
            await self.bot.services.broadcaster_settings.set_timers_enabled(
                broadcaster_id=broadcaster_id,
                enabled=enabled
            )
        except Exception:
            LOGGER.exception(
                "[Commands] Failed to update timer settings for broadcaster %s.",
                broadcaster_id
            )
            return

        state = "enabled" if enabled else "disabled"

        LOGGER.info(
            "[Commands] User %s %s timers for broadcaster %s.",
            ctx.chatter.name,
            state,
            broadcaster_id
        )

        await ctx.reply(
            f"Timers are now {state} for this channel."
        )
