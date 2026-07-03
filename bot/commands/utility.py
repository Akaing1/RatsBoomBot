import random

import twitchio
from twitchio.ext import commands


class UtilityCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hi(self, ctx: commands.Context, ):
        await ctx.reply(f"Hallo {ctx.chatter.name}!")

    @commands.command()
    async def choice(self, ctx: commands.Context, *choices: str):
        if not choices:
            await ctx.reply("Give me some choices! Example: !choice pizza sushi tacos")
            return
        await ctx.reply(f"Hmmmm... I choose: {random.choice(choices)}!")

    @commands.command(aliases=["thanks", "thank"])
    async def give(self, ctx: commands.Context, user: twitchio.User, amount: int, *, message: str | None = None, ):
        msg = (f"with message: {message}" if message else "")

        await ctx.send(f"{ctx.chatter.mention} "f"gave {amount} thanks "f"to {user.mention} {msg}")
