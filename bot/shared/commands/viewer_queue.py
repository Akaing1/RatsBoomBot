import logging

from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


def get_broadcaster_id(ctx: commands.Context) -> str:

    return str(ctx.broadcaster.id)


def get_chatter_name(ctx: commands.Context) -> str:

    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return "unknown"

    return chatter.name


def is_mod_or_broadcaster(ctx: commands.Context) -> bool:

    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return False

    is_moderator = getattr(chatter, "moderator", False)
    is_broadcaster = str(chatter.id) == str(ctx.broadcaster.id)

    return is_moderator or is_broadcaster


class ViewerQueueCommands(commands.Component):

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
            get_chatter_name(ctx),
            command_name,
            get_broadcaster_id(ctx)
        )

        return False

    def log_command(self, ctx: commands.Context, command_name: str) -> None:

        LOGGER.debug(
            "[Commands] User %s invoked !%s in broadcaster %s.",
            get_chatter_name(ctx),
            command_name,
            get_broadcaster_id(ctx)
        )

    @commands.command(name="open")
    async def open_queue(self, ctx: commands.Context):
        self.log_command(ctx, "open")

        if not self.services_available("open"):
            return

        if not self.has_permission(ctx, "open"):
            await ctx.send(
                "Only the broadcaster or mods can open the queue."
            )
            return

        broadcaster_id = get_broadcaster_id(ctx)

        message = self.bot.services.viewer_queue.open_queue(
            broadcaster_id
        )

        await ctx.send(message)

    @commands.command(name="close")
    async def close_queue(self, ctx: commands.Context):
        self.log_command(ctx, "close")

        if not self.services_available("close"):
            return

        if not self.has_permission(ctx, "close"):
            await ctx.send(
                "Only the broadcaster or mods can close the queue."
            )
            return

        broadcaster_id = get_broadcaster_id(ctx)

        message = self.bot.services.viewer_queue.close_queue(
            broadcaster_id
        )

        await ctx.send(message)

    @commands.command(name="join")
    async def join_queue(self, ctx: commands.Context):
        self.log_command(ctx, "join")

        if not self.services_available("join"):
            return

        broadcaster_id = get_broadcaster_id(ctx)
        username = get_chatter_name(ctx)

        _, message = self.bot.services.viewer_queue.join(
            broadcaster_id,
            username
        )

        await ctx.send(message)

    @commands.command(name="leave")
    async def leave_queue(self, ctx: commands.Context):
        self.log_command(ctx, "leave")

        if not self.services_available("leave"):
            return

        broadcaster_id = get_broadcaster_id(ctx)
        username = get_chatter_name(ctx)

        _, message = self.bot.services.viewer_queue.leave(
            broadcaster_id,
            username
        )

        await ctx.send(message)

    @commands.command(name="queue")
    async def show_queue(self, ctx: commands.Context):
        self.log_command(ctx, "queue")

        if not self.services_available("queue"):
            return

        broadcaster_id = get_broadcaster_id(ctx)

        queue = self.bot.services.viewer_queue.list_queue(
            broadcaster_id
        )

        if not queue:
            await ctx.send(
                "The viewer queue is currently empty."
            )
            return

        preview = queue[:5]

        queue_text = ", ".join(
            f"{index + 1}. {name}"
            for index, name in enumerate(preview)
        )

        if len(queue) > 5:
            queue_text += f" ... and {len(queue) - 5} more"

        await ctx.send(
            f"Current queue: {queue_text}"
        )

    @commands.command(name="next")
    async def next_viewer(self, ctx: commands.Context):
        self.log_command(ctx, "next")

        if not self.services_available("next"):
            return

        if not self.has_permission(ctx, "next"):
            await ctx.send(
                "Only the broadcaster or mods can use !next."
            )
            return

        broadcaster_id = get_broadcaster_id(ctx)

        _, message = self.bot.services.viewer_queue.next_viewer(
            broadcaster_id
        )

        await ctx.send(message)

    @commands.command(name="clear")
    async def clear_queue(self, ctx: commands.Context):
        self.log_command(ctx, "clear")

        if not self.services_available("clear"):
            return

        if not self.has_permission(ctx, "clear"):
            await ctx.send(
                "Only the broadcaster or mods can clear the queue."
            )
            return

        broadcaster_id = get_broadcaster_id(ctx)

        message = self.bot.services.viewer_queue.clear(
            broadcaster_id
        )

        await ctx.send(message)
