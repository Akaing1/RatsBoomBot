import logging
import random

import twitchio
from twitchio.ext import commands

LOGGER = logging.getLogger("RatBoomBot")


class UtilityCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def log_command(ctx: commands.Context, command_name: str) -> None:

        LOGGER.debug(
            "[Commands] User %s invoked !%s in broadcaster %s.",
            ctx.chatter.name,
            command_name,
            ctx.broadcaster.id
        )

    @commands.command()
    async def hi(self, ctx: commands.Context, user: twitchio.User = None):
        self.log_command(ctx, "hi")

        if user is None:
            await ctx.reply(f"Hallo {ctx.chatter.name}!")
            return

        await ctx.reply(f"{ctx.chatter.name} says hallo {user}!")

    @commands.command()
    async def choice(self, ctx: commands.Context, *choices: str):
        self.log_command(ctx, "choice")

        if not choices:
            LOGGER.debug(
                "[Commands] User %s invoked !choice without options.",
                ctx.chatter.name
            )

            await ctx.reply(
                "Give me some choices! Example: !choice pizza sushi tacos"
            )
            return

        selected_choice = random.choice(choices)

        LOGGER.debug(
            "[Commands] !choice selected %s from %d options.",
            selected_choice,
            len(choices)
        )

        await ctx.reply(f"Hmmmm... I choose: {selected_choice}!")

    @commands.command()
    async def kaboom(self, ctx: commands.Context, user: twitchio.User = None):
        self.log_command(ctx, "kaboom")

        if user is None:
            await ctx.reply(f"{ctx.chatter.name} has blown up!")
            return

        await ctx.send(f"{ctx.chatter.name} has blown {user} up! KABOOM!")

    @commands.command()
    async def stinky(self, ctx: commands.Context, user: twitchio.User = None):
        self.log_command(ctx, "stinky")

        stinky_percentage = random.randint(0, 100)

        LOGGER.debug(
            "[Commands] !stinky generated %d for user %s.",
            stinky_percentage,
            user or ctx.chatter.name
        )

        if stinky_percentage < 20:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is pretty clean today! "
                    f"Only {stinky_percentage}% stinky."
                )
                return

            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is pretty clean today! "
                f"Only {stinky_percentage}% stinky."
            )
            return

        if stinky_percentage < 50:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is kinda clean today... "
                    f"Only {stinky_percentage}% stinky."
                )
                return

            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is kinda clean today... "
                f"Only {stinky_percentage}% stinky."
            )
            return

        if stinky_percentage > 80:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is {stinky_percentage}% stinky today! "
                    "You need a shower!"
                )
                return

            await ctx.send(
                f"{ctx.chatter.name} thinks {user} is "
                f"{stinky_percentage}% stinky today! They need a shower!"
            )
            return

        if user is None:
            await ctx.reply(
                f"{ctx.chatter.name} is kinda stinky today... "
                f"Only {stinky_percentage}% stinky."
            )
            return

        await ctx.reply(
            f"{ctx.chatter.name} thinks {user} is kinda stinky today... "
            f"Only {stinky_percentage}% stinky."
        )

    @commands.command()
    async def lucky(self, ctx: commands.Context, user: twitchio.User = None):
        self.log_command(ctx, "lucky")

        lucky_percentage = random.randint(0, 100)

        LOGGER.debug(
            "[Commands] !lucky generated %d for user %s.",
            lucky_percentage,
            user or ctx.chatter.name
        )

        if lucky_percentage < 20:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is unlucky! "
                    f"You are {lucky_percentage}% lucky. Don't gamble!"
                )
                return

            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is unlucky! "
                f"They are {lucky_percentage}% lucky. "
                "Don't let them gamble!"
            )
            return

        if lucky_percentage < 50:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is kinda unlucky today... "
                    f"Only {lucky_percentage}% lucky."
                )
                return

            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is kinda unlucky today... "
                f"Only {lucky_percentage}% lucky."
            )
            return

        if lucky_percentage > 80:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is {lucky_percentage}% lucky today! "
                    "Go buy a lottery ticket!"
                )
                return

            await ctx.send(
                f"{ctx.chatter.name} thinks {user} is "
                f"{lucky_percentage}% lucky today! "
                "Go buy a lottery ticket!"
            )
            return

        if user is None:
            await ctx.reply(
                f"{ctx.chatter.name} is kinda lucky today... "
                f"Only {lucky_percentage}% lucky."
            )
            return

        await ctx.reply(
            f"{ctx.chatter.name} thinks {user} is kinda lucky today... "
            f"Only {lucky_percentage}% lucky."
        )

    @commands.command()
    async def smart(self, ctx: commands.Context, user: twitchio.User = None):
        self.log_command(ctx, "smart")

        smart_percentage = random.randint(0, 100)

        LOGGER.debug(
            "[Commands] !smart generated %d for user %s.",
            smart_percentage,
            user or ctx.chatter.name
        )

        if smart_percentage < 20:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} might have pebbles in their head today! "
                    f"You are {smart_percentage}% smart today!"
                )
                return

            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} might have pebbles "
                f"in their head today! They are {smart_percentage}% smart today!"
            )
            return

        if smart_percentage < 50:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is kinda dumbo today... "
                    f"Only {smart_percentage}% smart..."
                )
                return

            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is kinda dumbo today... "
                f"Only {smart_percentage}% smart..."
            )
            return

        if smart_percentage > 80:
            if user is None:
                await ctx.reply(
                    f"{ctx.chatter.name} is a genius! "
                    f"You are {smart_percentage}% smart today!"
                )
                return

            await ctx.send(
                f"{ctx.chatter.name} thinks {user} is a genius! "
                f"They are {smart_percentage}% smart today!"
            )
            return

        if user is None:
            await ctx.reply(
                f"{ctx.chatter.name} is kinda smart today... "
                f"Only {smart_percentage}% smart."
            )
            return

        await ctx.reply(
            f"{ctx.chatter.name} thinks {user} is kinda smart today... "
            f"Only {smart_percentage}% smart."
        )

    @commands.command()
    async def lurk(self, ctx: commands.Context):
        self.log_command(ctx, "lurk")

        await ctx.reply(
            f"{ctx.chatter.name} has been spotted by a human and scattered! "
            "See you soon!"
        )

    @commands.command(name="help")
    async def help(self, ctx: commands.Context):
        self.log_command(ctx, "help")

        if not self.bot.services:
            LOGGER.warning(
                "[Commands] !help could not run because services are unavailable."
            )
            return

        await ctx.reply(
            self.bot.services.help.format_help_message()
        )
