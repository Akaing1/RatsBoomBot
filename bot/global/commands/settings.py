from twitchio.ext import commands


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:
    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = chatter.id == ctx.broadcaster.id

    return is_moderator or is_broadcaster


class SettingsCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setdiscord")
    async def set_discord(self, ctx: commands.Context, url: str | None = None):
        if not self.bot.services:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.reply("Only the broadcaster or mods can set the Discord link.")
            return

        if not url:
            await ctx.reply("Use it like this: !setdiscord https://discord.gg/yourlink")
            return

        await self.bot.services.broadcaster_settings.set_discord_url(
            broadcaster_id=ctx.broadcaster.id,
            discord_url=url
        )

        await ctx.reply("Discord link updated for this channel.")

    @commands.command(name="setyoutube")
    async def set_youtube(self, ctx: commands.Context, url: str | None = None):
        if not self.bot.services:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.reply("Only the broadcaster or mods can set the YouTube link.")
            return

        if not url:
            await ctx.reply("Use it like this: !setyoutube https://youtube.com/@yourchannel")
            return

        await self.bot.services.broadcaster_settings.set_youtube_url(
            broadcaster_id=ctx.broadcaster.id,
            youtube_url=url
        )

        await ctx.reply("YouTube link updated for this channel.")

    @commands.command(name="timers")
    async def timers(self, ctx: commands.Context, status: str | None = None):
        if not self.bot.services:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.reply("Only the broadcaster or mods can change timer settings.")
            return

        if status is None:
            settings = await self.bot.services.broadcaster_settings.get_settings(ctx.broadcaster.id)

            state = "enabled" if settings.timers_enabled else "disabled"
            await ctx.reply(f"Timers are currently {state} for this channel.")
            return

        normalized = status.lower().strip()

        if normalized not in {"on", "off", "enable", "disable", "enabled", "disabled"}:
            await ctx.reply("Use it like this: !timers on or !timers off")
            return

        enabled = normalized in {"on", "enable", "enabled"}

        await self.bot.services.broadcaster_settings.set_timers_enabled(
            broadcaster_id=ctx.broadcaster.id,
            enabled=enabled,
        )

        state = "enabled" if enabled else "disabled"
        await ctx.reply(f"Timers are now {state} for this channel.")
