from twitchio.ext import commands

from bot.profiles import GlobalCommandName
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_command_enabled
from bot.shared.commands.viewer_queue import is_mod_or_broadcaster


class QuoteCommands(commands.Component):
    MAX_MESSAGE_LENGTH = 350

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="quote")
    async def quote(self, ctx: commands.Context, *, argument: str | None = None) -> None:
        broadcaster_id = get_context_broadcaster_id(ctx)
        if broadcaster_id is None or not is_global_command_enabled(self.bot, ctx, GlobalCommandName.QUOTE):
            return

        argument = (argument or "").strip()
        action, _, value = argument.partition(" ")
        action = action.casefold()
        service = self.bot.services.quotes

        if action == "add":
            message = value.strip()
            if not message or len(message) > self.MAX_MESSAGE_LENGTH:
                await ctx.reply(f"Use !quote add <message> (up to {self.MAX_MESSAGE_LENGTH} characters).")
                return
            number = await service.add(broadcaster_id, message, str(ctx.chatter.id))
            await ctx.reply(f'Quote {number} added: "{message}"')
            return

        if action == "remove":
            if not is_mod_or_broadcaster(ctx):
                await ctx.reply("Only the broadcaster or mods can remove quotes.")
                return
            if not value.strip().isdecimal() or int(value.strip()) < 1:
                await ctx.reply("Use !quote remove <number>.")
                return
            number = int(value.strip())
            removed = await service.remove(broadcaster_id, number)
            await ctx.reply(f"Quote {number} removed." if removed else f"Quote {number} was not found.")
            return

        if action in {"", "random"}:
            if value.strip():
                await ctx.reply("Use !quote random or !quote <number>.")
                return
            selected = await service.random(broadcaster_id)
            if selected is None:
                await ctx.reply("No quotes have been added yet. Use !quote add <message>.")
                return
            number, message = selected
        elif argument.isdecimal() and int(argument) > 0:
            number = int(argument)
            message = await service.get(broadcaster_id, number)
            if message is None:
                await ctx.reply(f"Quote {number} was not found.")
                return
        else:
            await ctx.reply("Use !quote random, !quote <number>, !quote add <message>, or !quote remove <number>.")
            return

        await ctx.reply(f'Quote {number}: "{message}"')
