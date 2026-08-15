import logging
from typing import TYPE_CHECKING

from twitchio.ext import commands

from bot.profiles import GlobalCommandGroup
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_group_enabled

if TYPE_CHECKING:
    from bot.services.container import ServiceContainer

LOGGER = logging.getLogger("RatBoomBot")


def get_chatter_name(ctx: commands.Context) -> str:
    chatter = getattr(ctx, "chatter", None) or getattr(ctx, "author", None)

    if chatter is None:
        return "unknown"

    return chatter.name


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


class ViewerQueueCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    def get_context(self, ctx: commands.Context, command_name: str) -> tuple[str, "ServiceContainer"] | None:
        services = self.bot.services

        if services is None:
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

        if not is_global_group_enabled(self.bot, ctx, GlobalCommandGroup.VIEWER_QUEUE):
            LOGGER.debug(
                "[Viewer Queue] Viewer queue is disabled for broadcaster %s.",
                broadcaster_id
            )
            return None

        return broadcaster_id, services

    @staticmethod
    def has_permission(ctx: commands.Context, command_name: str) -> bool:
        if is_mod_or_broadcaster(ctx):
            return True

        LOGGER.info(
            "[Commands] User %s was denied permission to run !%s in broadcaster %s.",
            get_chatter_name(ctx),
            command_name,
            get_context_broadcaster_id(ctx) or "unknown"
        )

        return False

    @staticmethod
    def log_command(ctx: commands.Context, command_name: str) -> None:
        LOGGER.debug(
            "[Commands] User %s invoked !%s in broadcaster %s.",
            get_chatter_name(ctx),
            command_name,
            get_context_broadcaster_id(ctx) or "unknown"
        )

    @commands.command(name="open")
    async def open_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "open")

        context = self.get_context(ctx, "open")

        if context is None:
            return

        broadcaster_id, services = context

        if not self.has_permission(ctx, "open"):
            await ctx.send("Only the broadcaster or mods can open the queue.")
            return

        message = services.viewer_queue.open_queue(broadcaster_id)

        await ctx.send(message)

    @commands.command(name="close")
    async def close_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "close")

        context = self.get_context(ctx, "close")

        if context is None:
            return

        broadcaster_id, services = context

        if not self.has_permission(ctx, "close"):
            await ctx.send("Only the broadcaster or mods can close the queue.")
            return

        message = services.viewer_queue.close_queue(broadcaster_id)

        await ctx.send(message)

    @commands.command(name="join")
    async def join_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "join")

        context = self.get_context(ctx, "join")

        if context is None:
            return

        broadcaster_id, services = context
        _, message = services.viewer_queue.join(broadcaster_id, get_chatter_name(ctx))

        await ctx.send(message)

    @commands.command(name="leave")
    async def leave_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "leave")

        context = self.get_context(ctx, "leave")

        if context is None:
            return

        broadcaster_id, services = context
        _, message = services.viewer_queue.leave(broadcaster_id, get_chatter_name(ctx))

        await ctx.send(message)

    @commands.command(name="queue")
    async def show_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "queue")

        context = self.get_context(ctx, "queue")

        if context is None:
            return

        broadcaster_id, services = context
        queue = services.viewer_queue.list_queue(broadcaster_id)

        if not queue:
            await ctx.send("The viewer queue is currently empty.")
            return

        preview = queue[:5]
        queue_text = ", ".join(f"{index + 1}. {name}" for index, name in enumerate(preview))

        if len(queue) > 5:
            queue_text += f" ... and {len(queue) - 5} more"

        await ctx.send(f"Current queue: {queue_text}")

    @commands.command(name="next")
    async def next_viewers(self, ctx: commands.Context, count: int = 1) -> None:
        self.log_command(ctx, "next")

        context = self.get_context(ctx, "next")

        if context is None:
            return

        broadcaster_id, services = context

        if not self.has_permission(ctx, "next"):
            await ctx.send("Only the broadcaster or mods can use !next.")
            return

        _, _, message = services.viewer_queue.next_viewers(broadcaster_id, count)

        await ctx.send(message)

    @commands.command(name="remove")
    async def remove_viewer(self, ctx: commands.Context, position: int | None = None) -> None:
        self.log_command(ctx, "remove")

        context = self.get_context(ctx, "remove")

        if context is None:
            return

        broadcaster_id, services = context

        if not self.has_permission(ctx, "remove"):
            await ctx.send("Only the broadcaster or mods can use !remove.")
            return

        if position is None:
            await ctx.send("Use it like this: !remove 3")
            return

        _, _, message = services.viewer_queue.remove_position(broadcaster_id, position)

        await ctx.send(message)

    @commands.command(name="clear")
    async def clear_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "clear")

        context = self.get_context(ctx, "clear")

        if context is None:
            return

        broadcaster_id, services = context

        if not self.has_permission(ctx, "clear"):
            await ctx.send("Only the broadcaster or mods can clear the queue.")
            return

        message = services.viewer_queue.clear(broadcaster_id)

        await ctx.send(message)
