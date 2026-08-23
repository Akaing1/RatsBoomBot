import logging
import re

from twitchio.ext import commands

from bot.profiles import GlobalCommandGroup
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_group_enabled

LOGGER = logging.getLogger("RatBoomBot")

USERNAME_PATTERN = re.compile(r"[^a-zA-Z0-9_]")


def clean_username(username: str) -> str:
    return USERNAME_PATTERN.sub("", username.replace("@", "").strip())


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:
    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)
    broadcaster_id = get_context_broadcaster_id(ctx)

    if chatter is None:
        return False

    if broadcaster_id is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = str(chatter.id) == broadcaster_id

    return is_moderator or is_broadcaster


async def send_shoutout_message(bot, broadcaster_id: str, username: str) -> bool:
    username = clean_username(username)

    if not username:
        LOGGER.debug(
            "[Shoutouts] Shoutout message skipped because the username was invalid."
        )
        return False

    return await bot.services.shoutouts.send_chat_message(broadcaster_id, username)


class ShoutoutCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="so", aliases=["shoutout"])
    async def shoutout(self, ctx: commands.Context, target: LocalizedUser = None) -> None:
        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Commands] !so could not run because services are unavailable."
            )
            return

        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Commands] !so could not resolve its broadcaster."
            )
            return

        caller = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)
        caller_name = getattr(caller, "name", "unknown")

        LOGGER.debug(
            "[Commands] User %s invoked !so in broadcaster %s with target %s.",
            caller_name,
            broadcaster_id,
            getattr(target, "display_name", None) or getattr(target, "name", "missing")
        )

        if not is_global_group_enabled(self.bot, ctx, GlobalCommandGroup.SHOUTOUTS):
            LOGGER.debug(
                "[Shoutouts] Shoutouts are disabled for broadcaster %s.",
                broadcaster_id
            )
            return

        if not is_mod_or_broadcaster(ctx):
            LOGGER.info(
                "[Commands] User %s was denied permission to run !so in broadcaster %s.",
                caller_name,
                broadcaster_id
            )

            await ctx.reply("Only the broadcaster or mods can use !so.")
            return

        if target is None:
            await ctx.reply("Use it like this: !so username")
            return

        if str(target.id) == broadcaster_id:
            await ctx.reply("You cannot shoutout the broadcaster.")
            return

        queued, response, position = services.shoutouts.enqueue(
            broadcaster_id=broadcaster_id,
            user_id=str(target.id),
            username=target.name,
            requested_by=caller_name
        )

        if not queued:
            await ctx.reply(response)
            return

        message_success = await send_shoutout_message(self.bot, broadcaster_id, target.name)

        if not message_success:
            LOGGER.warning(
                "[Shoutouts] Native shoutout for %s was queued, but the chat message failed.",
                target.name
            )

            await ctx.reply(response)
            return

        LOGGER.info(
            "[Shoutouts] %s was added to broadcaster %s shoutout queue at position %d.",
            target.name,
            broadcaster_id,
            position
        )
