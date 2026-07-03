import random

import twitchio
from twitchio.ext import commands


class UtilityCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hi(self, ctx: commands.Context):
        await ctx.reply(f"Hallo {ctx.chatter.name}!")

    @commands.command()
    async def choice(self, ctx: commands.Context, *choices: str):
        if not choices:
            await ctx.reply("Give me some choices! Example: !choice pizza sushi tacos")
            return
        await ctx.reply(f"Hmmmm... I choose: {random.choice(choices)}!")

    @commands.command()
    async def kaboom(self, ctx: commands.Context, user: twitchio.User = None):
        if user is None:
            await ctx.reply(f"{ctx.chatter.name} has blown up!")
            return
        await ctx.send(f"{ctx.chatter.name} has blown {user} up! KABOOM!")

    @commands.command()
    async def stinky(self, ctx: commands.Context, user: twitchio.User = None):

        stinky_percentage = random.randint(0, 100)

        if stinky_percentage < 20:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is pretty clean today! Only {stinky_percentage}% stinky.")
                return
            await ctx.reply(f"{ctx.chatter.name} thinks {user} is pretty clean today! Only {stinky_percentage}% stinky.")
            return

        elif stinky_percentage < 50:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is kinda clean today... Only {stinky_percentage}% stinky.")
                return
            await ctx.reply(f"{ctx.chatter.name} thinks {user} is kinda clean today... Only {stinky_percentage}% stinky.")
            return

        elif stinky_percentage > 80:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is {stinky_percentage}% stinky today! You need a shower!")
                return
            await ctx.send(f"{ctx.chatter.name} thinks {user} is {stinky_percentage}% stinky today! They need a shower!")

        else:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is kinda stinky today... Only {stinky_percentage}% stinky.")
                return
            await ctx.reply(f"{ctx.chatter.name} thinks {user} is kinda stinky today... Only {stinky_percentage}% stinky.")
            return

    @commands.command()
    async def lucky(self, ctx: commands.Context, user: twitchio.User = None):

        lucky_percentage = random.randint(0, 100)

        if lucky_percentage < 20:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is unlucky! You are {lucky_percentage}% lucky. Don't gamble!")
                return
            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is unlucky! They are {lucky_percentage}% lucky. Don't let them gamble!")
            return

        elif lucky_percentage < 50:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is kinda unlucky today... Only {lucky_percentage}% lucky.")
                return
            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is kinda unlucky today... Only {lucky_percentage}% lucky.")
            return

        elif lucky_percentage > 80:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is {lucky_percentage}% lucky today! Go buy a lottery ticket!")
                return
            await ctx.send(
                f"{ctx.chatter.name} thinks {user} is {lucky_percentage}% lucky today! Go buy a lottery ticket!")

        else:
            if user is None:
                await ctx.reply(f"{ctx.chatter.name} is kinda lucky today... Only {lucky_percentage}% stinky.")
                return
            await ctx.reply(
                f"{ctx.chatter.name} thinks {user} is kinda lucky today... Only {lucky_percentage}% stinky.")
            return

    @commands.command()
    async def lurk(self, ctx: commands.Context):
        await ctx.reply(f"{ctx.chatter.name} has been spotted by a human and scattered! See you soon!")

    @commands.command(name="help")
    async def help(self, ctx: commands.Context):
        if not self.bot.services:
            return

        await ctx.reply(
            self.bot.services.help.format_help_message()
        )
