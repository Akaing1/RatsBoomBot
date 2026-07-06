import re

from twitchio.ext import commands


USERNAME_PATTERN = re.compile(r"[^a-zA-Z0-9_]")


def clean_username(username: str) -> str:
    return USERNAME_PATTERN.sub("", username.replace("@", "").strip())


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:
    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = chatter.id == ctx.broadcaster.id

    return is_moderator or is_broadcaster


async def send_shoutout_message(bot, broadcaster_id: str, username: str) -> bool:
    username = clean_username(username)

    if not username:
        return False

    channel = bot.create_partialuser(broadcaster_id)

    await channel.send_message(
        sender=bot.user,
        message=(
            f"Go check out @{username}! "
            f"They are a cool rat: https://twitch.tv/{username}"
        )
    )

    return True


class ShoutoutCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="so")
    async def shoutout(self, ctx: commands.Context, username: str | None = None):
        if not is_mod_or_broadcaster(ctx):
            await ctx.reply("Only the broadcaster or mods can use !so.")
            return

        if not username:
            await ctx.reply("Use it like this: !so username")
            return

        username = clean_username(username)

        if not username:
            await ctx.reply("Use it like this: !so username")
            return

        if username.lower() == ctx.broadcaster.name.lower():
            await ctx.reply("You cannot shoutout the broadcaster.")
            return

        success = await send_shoutout_message(
            bot=self.bot,
            broadcaster_id=ctx.broadcaster.id,
            username=username
        )

        if not success:
            await ctx.reply("I could not shoutout that user.")
