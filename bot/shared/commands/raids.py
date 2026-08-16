import logging

from twitchio.ext import commands

from bot.profiles import FeatureName, get_active_profile, render_profile_message
from bot.shared.commands.helpers import get_context_broadcaster_id, is_feature_enabled
from bot.shared.commands.shoutout import clean_username

LOGGER = logging.getLogger("RatBoomBot")


class RaidCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def is_broadcaster(ctx: commands.Context, broadcaster_id: str) -> bool:
        chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)
        chatter_id = getattr(chatter, "id", None)
        return chatter_id is not None and str(chatter_id) == str(broadcaster_id)

    @commands.command(name="startraid")
    async def start_raid(self, ctx: commands.Context, target_name: str | None = None) -> None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None or not is_feature_enabled(self.bot, ctx, FeatureName.RAID_RESPONSES):
            return

        if not self.is_broadcaster(ctx, broadcaster_id):
            await ctx.reply("Only the broadcaster can start a raid.")
            return

        target_name = clean_username(target_name or "")

        if not target_name:
            await ctx.reply("Use it like this: !startraid channel_name")
            return

        profile = get_active_profile(broadcaster_id)

        if profile is None:
            LOGGER.warning("[Raids] !startraid could not find a profile for broadcaster %s.", broadcaster_id)
            return

        try:
            target = await self.bot.fetch_user(login=target_name)
        except Exception:
            LOGGER.exception("[Raids] Failed to resolve raid target %s for broadcaster %s.", target_name, broadcaster_id)
            await ctx.reply(f"I couldn't find @{target_name} on Twitch.")
            return

        if target is None:
            await ctx.reply(f"I couldn't find @{target_name} on Twitch.")
            return

        if str(target.id) == broadcaster_id:
            await ctx.reply("You cannot raid your own channel.")
            return

        outgoing = render_profile_message(profile.raid_messages.outgoing, target_name=target.name, target_url=f"https://twitch.tv/{target.name}")
        outgoing_subscriber = render_profile_message(profile.raid_messages.outgoing_subscriber, target_name=target.name, target_url=f"https://twitch.tv/{target.name}")

        if not outgoing or not outgoing_subscriber:
            await ctx.reply("Both outgoing raid messages must be configured before starting a raid.")
            return

        broadcaster = self.bot.create_partialuser(broadcaster_id)

        try:
            await broadcaster.start_raid(target)
        except Exception as error:
            LOGGER.exception("[Raids] Failed to start raid from broadcaster %s to %s (%s).", broadcaster_id, target.name, target.id)

            if getattr(error, "status", None) in {401, 403}:
                await ctx.reply("I need the broadcaster to reconnect their Twitch account before I can start raids.")
            else:
                await ctx.reply(f"Twitch could not start the raid to @{target.name}.")

            return

        await ctx.send(outgoing)
        await ctx.send(outgoing_subscriber)

        LOGGER.info("[Raids] Broadcaster %s started a raid to %s (%s).", broadcaster_id, target.name, target.id)
