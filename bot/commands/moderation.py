from twitchio.ext import commands


class ModerationCommands(commands.Component):

    def __init__(self, bot):
        self.bot = bot
