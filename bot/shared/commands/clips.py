import logging

from twitchio.ext import commands

from bot.profiles import GlobalCommandGroup, get_active_profile, render_profile_message
from bot.services.engagement import ClipInProgressError, ClipOnCooldownError
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_group_enabled

LOGGER = logging.getLogger("RatBoomBot")


class ClipCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="clip", aliases=["clips"])
    async def clip(self, ctx: commands.Context, option: str | None = None) -> None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None or not is_global_group_enabled(self.bot, ctx, GlobalCommandGroup.CLIPS):
            return

        profile = get_active_profile(broadcaster_id)
        services = self.bot.services

        if profile is None or services is None:
            LOGGER.warning("[Clips] !clip could not run because its profile or services were unavailable.")
            return

        config = profile.clips
        username = ctx.chatter.name
        option = (option or "").strip().casefold()

        if option not in {"", "short"}:
            await ctx.reply(config.messages.usage)
            return

        duration = config.short_duration if option == "short" else config.duration

        try:
            created_clip = await services.clips.create_clip(broadcaster_id, profile.channel_name, username, duration, config)
        except ClipOnCooldownError as error:
            message = render_profile_message(config.messages.cooldown, username=username, seconds=error.remaining_seconds)
            await ctx.reply(message)
            return
        except ClipInProgressError:
            message = render_profile_message(config.messages.in_progress, username=username)
            await ctx.reply(message)
            return
        except Exception as error:
            LOGGER.exception("[Clips] Twitch rejected a %d-second clip for broadcaster %s.", duration, broadcaster_id)
            await ctx.reply(self.error_message(error, config, username))
            return

        processing_message = render_profile_message(config.messages.processing, username=username, duration=duration)
        await ctx.reply(processing_message)
        clip = await services.clips.wait_for_clip(broadcaster_id, created_clip.id, config.processing_timeout_seconds)

        if clip is None:
            clip_url = f"https://clips.twitch.tv/{created_clip.id}"
            LOGGER.warning("[Clips] Clip %s was accepted but was not available after %d seconds.", created_clip.id, config.processing_timeout_seconds)
        else:
            clip_url = clip.url

        message = render_profile_message(config.messages.success, username=username, clip_url=clip_url, duration=duration)
        await ctx.send(message)
        LOGGER.info("[Clips] User %s created a %d-second clip %s for broadcaster %s.", username, duration, created_clip.id, broadcaster_id)

    @staticmethod
    def error_message(error: Exception, config, username: str) -> str:
        status = getattr(error, "status", None)

        if status == 404:
            template = config.messages.offline
        elif status == 403:
            template = config.messages.unavailable
        elif status == 401:
            template = config.messages.authorization_required
        else:
            template = config.messages.failed

        return render_profile_message(template, username=username)
