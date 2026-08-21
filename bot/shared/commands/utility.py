import logging
import random

from twitchio.ext import commands

from bot.profiles import GlobalCommandName
from bot.shared.commands.converters import LocalizedUser
from bot.shared.commands.helpers import get_context_broadcaster_id, is_global_command_enabled

LOGGER = logging.getLogger("RatBoomBot")


class UtilityCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def log_command(ctx: commands.Context, command_name: str) -> None:
        broadcaster_id = get_context_broadcaster_id(ctx)

        LOGGER.debug(
            "[Commands] User %s invoked !%s in broadcaster %s.",
            ctx.chatter.name,
            command_name,
            broadcaster_id or "unknown"
        )

    def command_enabled(self, ctx: commands.Context, command: GlobalCommandName) -> bool:
        broadcaster_id = get_context_broadcaster_id(ctx)

        if broadcaster_id is None:
            LOGGER.warning(
                "[Commands] Could not resolve the broadcaster for global command %s.",
                command.value
            )
            return False

        if not is_global_command_enabled(self.bot, ctx, command):
            LOGGER.debug(
                "[Commands] !%s is disabled for broadcaster %s.",
                command.value,
                broadcaster_id
            )
            return False

        return True

    @commands.command()
    async def hi(self, ctx: commands.Context, user: LocalizedUser = None) -> None:
        self.log_command(ctx, "hi")

        if not self.command_enabled(ctx, GlobalCommandName.HI):
            return

        if user is None:
            await ctx.reply(f"Hallo {ctx.chatter.name}!")
            return

        await ctx.reply(f"{ctx.chatter.name} says hallo {user}!")

    @commands.command()
    async def choice(self, ctx: commands.Context, *choices: str) -> None:
        self.log_command(ctx, "choice")

        if not self.command_enabled(ctx, GlobalCommandName.CHOICE):
            return

        if not choices:
            LOGGER.debug(
                "[Commands] User %s invoked !choice without options.",
                ctx.chatter.name
            )

            await ctx.reply("Give me some choices! Example: !choice pizza sushi tacos")
            return

        selected_choice = random.choice(choices)

        LOGGER.debug(
            "[Commands] !choice selected %s from %d options.",
            selected_choice,
            len(choices)
        )

        await ctx.reply(f"Hmmmm... I choose: {selected_choice}!")

    @commands.command()
    async def kaboom(self, ctx: commands.Context, user: LocalizedUser = None) -> None:
        self.log_command(ctx, "kaboom")

        if not self.command_enabled(ctx, GlobalCommandName.KABOOM):
            return

        if user is None:
            await ctx.reply(f"{ctx.chatter.name} has blown up!")
            return

        await ctx.send(f"{ctx.chatter.name} has blown {user} up! KABOOM!")

    @commands.command()
    async def stinky(self, ctx: commands.Context, user: LocalizedUser = None) -> None:
        self.log_command(ctx, "stinky")

        if not self.command_enabled(ctx, GlobalCommandName.STINKY):
            return

        stinky_percentage = random.randint(0, 100)
        target_name = user or ctx.chatter.name

        LOGGER.debug(
            "[Commands] !stinky generated %d for user %s.",
            stinky_percentage,
            target_name
        )

        if stinky_percentage < 20:
            if user is None:
                message = f"{ctx.chatter.name} is pretty clean today! Only {stinky_percentage}% stinky."
            else:
                message = f"{ctx.chatter.name} thinks {user} is pretty clean today! Only {stinky_percentage}% stinky."

            await ctx.reply(message)
            return

        if stinky_percentage < 50:
            if user is None:
                message = f"{ctx.chatter.name} is kinda clean today... Only {stinky_percentage}% stinky."
            else:
                message = f"{ctx.chatter.name} thinks {user} is kinda clean today... Only {stinky_percentage}% stinky."

            await ctx.reply(message)
            return

        if stinky_percentage > 80:
            if user is None:
                message = f"{ctx.chatter.name} is {stinky_percentage}% stinky today! You need a shower!"
                await ctx.reply(message)
            else:
                message = f"{ctx.chatter.name} thinks {user} is {stinky_percentage}% stinky today! They need a shower!"
                await ctx.send(message)

            return

        if user is None:
            message = f"{ctx.chatter.name} is kinda stinky today... Only {stinky_percentage}% stinky."
        else:
            message = f"{ctx.chatter.name} thinks {user} is kinda stinky today... Only {stinky_percentage}% stinky."

        await ctx.reply(message)

    @commands.command()
    async def lucky(self, ctx: commands.Context, user: LocalizedUser = None) -> None:
        self.log_command(ctx, "lucky")

        if not self.command_enabled(ctx, GlobalCommandName.LUCKY):
            return

        lucky_percentage = random.randint(0, 100)
        target_name = user or ctx.chatter.name

        LOGGER.debug(
            "[Commands] !lucky generated %d for user %s.",
            lucky_percentage,
            target_name
        )

        if lucky_percentage < 20:
            if user is None:
                message = f"{ctx.chatter.name} is unlucky! You are {lucky_percentage}% lucky. Don't gamble!"
            else:
                message = f"{ctx.chatter.name} thinks {user} is unlucky! They are {lucky_percentage}% lucky. Don't let them gamble!"

            await ctx.reply(message)
            return

        if lucky_percentage < 50:
            if user is None:
                message = f"{ctx.chatter.name} is kinda unlucky today... Only {lucky_percentage}% lucky."
            else:
                message = f"{ctx.chatter.name} thinks {user} is kinda unlucky today... Only {lucky_percentage}% lucky."

            await ctx.reply(message)
            return

        if lucky_percentage > 80:
            if user is None:
                message = f"{ctx.chatter.name} is {lucky_percentage}% lucky today! Go buy a lottery ticket!"
                await ctx.reply(message)
            else:
                message = f"{ctx.chatter.name} thinks {user} is {lucky_percentage}% lucky today! Go buy a lottery ticket!"
                await ctx.send(message)

            return

        if user is None:
            message = f"{ctx.chatter.name} is kinda lucky today... Only {lucky_percentage}% lucky."
        else:
            message = f"{ctx.chatter.name} thinks {user} is kinda lucky today... Only {lucky_percentage}% lucky."

        await ctx.reply(message)

    @commands.command()
    async def smart(self, ctx: commands.Context, user: LocalizedUser = None) -> None:
        self.log_command(ctx, "smart")

        if not self.command_enabled(ctx, GlobalCommandName.SMART):
            return

        smart_percentage = random.randint(0, 100)
        target_name = user or ctx.chatter.name

        LOGGER.debug(
            "[Commands] !smart generated %d for user %s.",
            smart_percentage,
            target_name
        )

        if smart_percentage < 20:
            if user is None:
                message = f"{ctx.chatter.name} might have pebbles in their head today! You are {smart_percentage}% smart today!"
            else:
                message = f"{ctx.chatter.name} thinks {user} might have pebbles in their head today! They are {smart_percentage}% smart today!"

            await ctx.reply(message)
            return

        if smart_percentage < 50:
            if user is None:
                message = f"{ctx.chatter.name} is kinda dumbo today... Only {smart_percentage}% smart..."
            else:
                message = f"{ctx.chatter.name} thinks {user} is kinda dumbo today... Only {smart_percentage}% smart..."

            await ctx.reply(message)
            return

        if smart_percentage > 80:
            if user is None:
                message = f"{ctx.chatter.name} is a genius! You are {smart_percentage}% smart today!"
                await ctx.reply(message)
            else:
                message = f"{ctx.chatter.name} thinks {user} is a genius! They are {smart_percentage}% smart today!"
                await ctx.send(message)

            return

        if user is None:
            message = f"{ctx.chatter.name} is kinda smart today... Only {smart_percentage}% smart."
        else:
            message = f"{ctx.chatter.name} thinks {user} is kinda smart today... Only {smart_percentage}% smart."

        await ctx.reply(message)

    @commands.command()
    async def height(self, ctx: commands.Context, user: LocalizedUser = None) -> None:
        self.log_command(ctx, "height")

        if not self.command_enabled(ctx, GlobalCommandName.HEIGHT):
            return

        total_inches = random.randint(12, 96)
        feet, inches = divmod(total_inches, 12)
        height = f"{feet}' {inches}\""

        if user is None:
            message = f"{ctx.chatter.name} is {height} tall!"
        else:
            message = f"{ctx.chatter.name} measured {user} at {height} tall!"

        LOGGER.debug(
            "[Commands] !height generated %d inches for user %s.",
            total_inches,
            user or ctx.chatter.name
        )

        await ctx.reply(message)

    @commands.command()
    async def pp(self, ctx: commands.Context, user: LocalizedUser = None) -> None:
        self.log_command(ctx, "pp")

        if not self.command_enabled(ctx, GlobalCommandName.PP):
            return

        inches = random.randint(-1, 20)

        if user is None:
            message = f"{ctx.chatter.name}'s pp is {inches}in!"
        else:
            message = f"{ctx.chatter.name} saw {user}'s pp and its {inches}in!"

        LOGGER.debug(
            "[Commands] !pp generated %d inches for user %s.",
            inches,
            user or ctx.chatter.name
        )

        await ctx.reply(message)

    @commands.command()
    async def lurk(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "lurk")

        if not self.command_enabled(ctx, GlobalCommandName.LURK):
            return

        await ctx.reply(
            f"{ctx.chatter.name} has been spotted by a human and scattered! "
            "See you soon!"
        )

    @commands.command(name="help")
    async def help(self, ctx: commands.Context) -> None:
        self.log_command(ctx, "help")

        if not self.command_enabled(ctx, GlobalCommandName.HELP):
            return

        services = self.bot.services

        if services is None:
            LOGGER.warning(
                "[Commands] !help could not run because services are unavailable."
            )
            return

        await ctx.reply(services.help.format_help_message())
