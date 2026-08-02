import logging
import re

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")

USERNAME_PATTERN = re.compile(r"[^a-zA-Z0-9_]")


def clean_username(username: str) -> str:

    return USERNAME_PATTERN.sub(
        "",
        username.replace("@", "").strip()
    )


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:

    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = str(chatter.id) == str(ctx.broadcaster.id)

    return is_moderator or is_broadcaster


async def send_shoutout_message(bot, broadcaster_id: str, username: str) -> bool:

    broadcaster_id = str(broadcaster_id)
    username = clean_username(username)

    if not username:
        LOGGER.debug(
            "[Shoutouts] Shoutout message skipped because the username was invalid."
        )
        return False

    channel = bot.create_partialuser(
        broadcaster_id
    )

    try:
        await channel.send_message(
            sender=bot.user,
            message=(
                f"Go check out @{username}! "
                f"They are a cool rat: https://twitch.tv/{username}"
            )
        )
    except Exception:
        LOGGER.exception(
            "[Shoutouts] Failed to send shoutout message for %s in broadcaster %s.",
            username,
            broadcaster_id
        )
        return False

    LOGGER.info(
        "[Shoutouts] Sent shoutout message for %s in broadcaster %s.",
        username,
        broadcaster_id
    )

    return True


class ShoutoutCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="so", aliases=["shoutout"])
    async def shoutout(self, ctx: commands.Context, username: str | None = None):

        broadcaster_id = str(ctx.broadcaster.id)
        caller_name = ctx.chatter.name

        LOGGER.debug(
            "[Commands] User %s invoked !so in broadcaster %s with target %s.",
            caller_name,
            broadcaster_id,
            username or "missing"
        )

        if not is_mod_or_broadcaster(ctx):
            LOGGER.info(
                "[Commands] User %s was denied permission to run !so in broadcaster %s.",
                caller_name,
                broadcaster_id
            )

            await ctx.reply(
                "Only the broadcaster or mods can use !so."
            )
            return

        if not username:
            await ctx.reply(
                "Use it like this: !so username"
            )
            return

        cleaned_username = clean_username(
            username
        )

        if not cleaned_username:
            await ctx.reply(
                "Use it like this: !so username"
            )
            return

        if cleaned_username.lower() == ctx.broadcaster.name.lower():
            await ctx.reply(
                "You cannot shoutout the broadcaster."
            )
            return

        try:
            target = await self.bot.fetch_user(
                login=cleaned_username
            )
        except Exception:
            LOGGER.exception(
                "[Shoutouts] Failed to resolve Twitch user %s.",
                cleaned_username
            )

            await ctx.reply(
                "I could not look up that Twitch user."
            )
            return

        if target is None:
            await ctx.reply(
                f"I could not find a Twitch user named {cleaned_username}."
            )
            return

        queued, response, position = self.bot.services.shoutouts.enqueue(
            broadcaster_id=broadcaster_id,
            user_id=str(target.id),
            username=target.name,
            requested_by=caller_name
        )

        if not queued:
            await ctx.reply(
                response
            )
            return

        message_success = await send_shoutout_message(
            bot=self.bot,
            broadcaster_id=broadcaster_id,
            username=target.name
        )

        if not message_success:
            LOGGER.warning(
                "[Shoutouts] Native shoutout for %s was queued, but the chat message failed.",
                target.name
            )

            await ctx.reply(
                response
            )
            return

        LOGGER.info(
            "[Shoutouts] %s was added to broadcaster %s shoutout queue at position %d.",
            target.name,
            broadcaster_id,
            position
        )
