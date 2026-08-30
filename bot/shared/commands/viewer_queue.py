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
    QUEUE_MESSAGE_MAX_LENGTH = 450

    def __init__(self, bot):
        self.bot = bot

    @classmethod
    def format_queue_messages(cls, queue: list[str]) -> list[str]:
        entries = [f"{index}. {name}" for index, name in enumerate(queue, start=1)]
        messages = []
        prefix = "Current queue: "
        current_message = prefix

        for entry in entries:
            separator = "" if current_message == prefix else ", "
            candidate = f"{current_message}{separator}{entry}"

            if len(candidate) <= cls.QUEUE_MESSAGE_MAX_LENGTH:
                current_message = candidate
                continue

            messages.append(current_message)
            prefix = "Queue continued: "
            current_message = f"{prefix}{entry}"

        if current_message != prefix:
            messages.append(current_message)

        return messages

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

        message = await services.viewer_queue.open_queue(broadcaster_id)

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

        message = await services.viewer_queue.close_queue(broadcaster_id)

        await ctx.send(message)

    @commands.command(name="join")
    async def join_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "join")

        context = self.get_context(ctx, "join")

        if context is None:
            return

        broadcaster_id, services = context
        _, message = await services.viewer_queue.join(broadcaster_id, get_chatter_name(ctx))

        await ctx.send(message)

    @commands.command(name="leave")
    async def leave_queue(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "leave")

        context = self.get_context(ctx, "leave")

        if context is None:
            return

        broadcaster_id, services = context
        _, message = await services.viewer_queue.leave(broadcaster_id, get_chatter_name(ctx))

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

        for message in self.format_queue_messages(queue):
            await ctx.send(message)

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

        _, _, message = await services.viewer_queue.next_viewers(broadcaster_id, count)

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

        _, _, message = await services.viewer_queue.remove_position(broadcaster_id, position)

        await ctx.send(message)

    @commands.command(name="swap")
    async def swap_viewers(self, ctx: commands.Context, first_position: int | None = None, second_position: int | None = None) -> None:
        self.log_command(ctx, "swap")
        context = self.get_context(ctx, "swap")

        if context is None:
            return

        broadcaster_id, services = context

        if not self.has_permission(ctx, "swap"):
            await ctx.send("Only the broadcaster or mods can use !swap.")
            return

        if first_position is None or second_position is None:
            await ctx.send("Use it like this: !swap 2 5")
            return

        _, message = await services.viewer_queue.swap(broadcaster_id, first_position, second_position)
        await ctx.send(message)

    @commands.command(name="requeue")
    async def requeue_viewer(self, ctx: commands.Context, current_position: int | None = None, new_position: int | None = None) -> None:
        self.log_command(ctx, "requeue")
        context = self.get_context(ctx, "requeue")

        if context is None:
            return

        broadcaster_id, services = context

        if not self.has_permission(ctx, "requeue"):
            await ctx.send("Only the broadcaster or mods can use !requeue.")
            return

        if current_position is None or new_position is None:
            await ctx.send("Use it like this: !requeue 5 2")
            return

        _, message = await services.viewer_queue.requeue(broadcaster_id, current_position, new_position)
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

        message = await services.viewer_queue.clear(broadcaster_id)

        await ctx.send(message)
