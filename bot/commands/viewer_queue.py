import logging

from twitchio.ext import commands

LOGGER = logging.getLogger("Bot")


def get_broadcaster_id(ctx: commands.Context) -> str:
    return ctx.broadcaster.id


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:
    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = chatter.id == ctx.broadcaster.id

    return is_moderator or is_broadcaster


def get_chatter_name(ctx: commands.Context) -> str:
    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)
    return chatter.name


class ViewerQueueCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="open")
    async def open_queue(self, ctx: commands.Context):
        if not self.bot.services:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.send("Only the broadcaster or mods can open the queue.")
            return

        broadcaster_id = get_broadcaster_id(ctx)
        message = self.bot.services.viewer_queue.open_queue(broadcaster_id)

        await ctx.send(message)

    @commands.command(name="close")
    async def close_queue(self, ctx: commands.Context):
        if not self.bot.services:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.send("Only the broadcaster or mods can close the queue.")
            return

        broadcaster_id = get_broadcaster_id(ctx)
        message = self.bot.services.viewer_queue.close_queue(broadcaster_id)

        await ctx.send(message)

    @commands.command(name="join")
    async def join_queue(self, ctx: commands.Context):
        if not self.bot.services:
            return

        broadcaster_id = get_broadcaster_id(ctx)
        username = get_chatter_name(ctx)

        success, message = self.bot.services.viewer_queue.join(
            broadcaster_id,
            username,
        )

        await ctx.send(message)

    @commands.command(name="leave")
    async def leave_queue(self, ctx: commands.Context):
        if not self.bot.services:
            return

        broadcaster_id = get_broadcaster_id(ctx)
        username = get_chatter_name(ctx)

        success, message = self.bot.services.viewer_queue.leave(
            broadcaster_id,
            username,
        )

        await ctx.send(message)

    @commands.command(name="queue")
    async def show_queue(self, ctx: commands.Context):
        if not self.bot.services:
            return

        broadcaster_id = get_broadcaster_id(ctx)
        queue = self.bot.services.viewer_queue.list_queue(broadcaster_id)

        if not queue:
            await ctx.send("The viewer queue is currently empty.")
            return

        preview = queue[:5]
        queue_text = ", ".join(
            f"{index + 1}. {name}"
            for index, name in enumerate(preview)
        )

        if len(queue) > 5:
            queue_text += f" ... and {len(queue) - 5} more"

        await ctx.send(f"Current queue: {queue_text}")

    @commands.command(name="next")
    async def next_viewer(self, ctx: commands.Context):
        if not self.bot.services:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.send("Only the broadcaster or mods can use !next.")
            return

        broadcaster_id = get_broadcaster_id(ctx)

        success, message = self.bot.services.viewer_queue.next_viewer(
            broadcaster_id
        )

        await ctx.send(message)

    @commands.command(name="clear")
    async def clear_queue(self, ctx: commands.Context):
        if not self.bot.services:
            return

        if not is_mod_or_broadcaster(ctx):
            await ctx.send("Only the broadcaster or mods can clear the queue.")
            return

        broadcaster_id = get_broadcaster_id(ctx)
        message = self.bot.services.viewer_queue.clear(broadcaster_id)

        await ctx.send(message)