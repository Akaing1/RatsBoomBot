from twitchio.ext import commands


class ViewerQueueCommands(commands.Component):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="join")
    async def join_queue(self, ctx: commands.Context):
        username = ctx.author.name
        success, message = self.bot.services.viewer_queue.join(username)
        await ctx.send(message)

    @commands.command(name="leave")
    async def leave_queue(self, ctx: commands.Context):
        username = ctx.author.name
        success, message = self.bot.services.viewer_queue.leave(username)
        await ctx.send(message)

    @commands.command(name="queue")
    async def show_queue(self, ctx: commands.Context):
        queue = self.bot.services.viewer_queue.list_queue()

        if not queue:
            await ctx.send("The viewer queue is currently empty.")
            return

        preview = queue[:5]
        queue_text = ", ".join(f"{i + 1}. {name}" for i, name in enumerate(preview))

        if len(queue) > 5:
            queue_text += f" ... and {len(queue) - 5} more"

        await ctx.send(f"Current queue: {queue_text}")

    @commands.command(name="next")
    async def next_viewer(self, ctx: commands.Context):
        isNotModerator = getattr(ctx.author, "moderator", False)
        if isNotModerator and ctx.author.name.lower() != ctx.channel.name.lower():
            await ctx.send("Only the broadcaster or mods can use !next.")
            return

        username = self.bot.services.viewer_queue.next_viewer()

        if username is None:
            await ctx.send("The queue is empty.")
            return

        await ctx.send(f"Next up: @{username}!")

    @commands.command(name="clear")
    async def clear_queue(self, ctx: commands.Context):
        isNotModerator = getattr(ctx.author, "moderator", False)
        if isNotModerator and ctx.author.name.lower() != ctx.channel.name.lower():
            await ctx.send("Only the broadcaster or mods can clear the queue.")
            return

        self.bot.services.viewer_queue.clear()
        await ctx.send("Viewer queue cleared.")