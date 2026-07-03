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

        if user is None:
            await ctx.reply(f"{ctx.chatter.name} is stinky!")
            return
        await ctx.send(f"{ctx.chatter.name} thinks {user} is stinky! Eww!")

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
