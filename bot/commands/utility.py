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

    @commands.command(name="help")
    async def help(self, ctx: commands.Context):
        commands_list = []

        for command in self.bot.commands.values():
            if command.name != command.qualified_name.split()[-1]:
                continue

            commands_list.append(command.qualified_name)

        commands_list = sorted(set(commands_list))

        await ctx.reply(
            "Available commands: " +
            ", ".join(f"!{cmd}" for cmd in commands_list)
        )
