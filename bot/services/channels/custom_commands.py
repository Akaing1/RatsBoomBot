"""Cached channel commands with one shared channel cooldown, no script execution."""
import json
import logging
import time
from types import SimpleNamespace

from storage.custom_commands import list_commands, run_command


class CustomCommandService:
    def __init__(self, db):
        self.db = db
        self.commands = {}
        self.deadlines = {}

    async def setup(self):
        async with self.db.acquire() as connection:
            rows = await connection.fetchall('SELECT broadcaster_id, name, definition FROM custom_commands')
        self.commands = {}
        for row in rows:
            self.commands.setdefault(row['broadcaster_id'], {})[row['name']] = json.loads(row['definition'])

    async def reload(self, channel):
        self.commands[str(channel)] = {entry['command']['name']: entry['command'] for entry in await list_commands(self.db, channel)}

    async def handle(self, ctx):
        # Only called for an unknown command; registered commands and points aliases win.
        if not ctx.prefix or not ctx.invoked_with or ctx.message is None:
            return
        channel = str(ctx.broadcaster.id)
        command = self.commands.get(channel, {}).get(ctx.invoked_with.casefold())
        if not command or not command['enabled']:
            return
        chatter = ctx.chatter
        if ctx.bot.services.chat_identity.is_custom_bot(str(chatter.id)):
            return
        role = 'broadcaster' if str(chatter.id) == channel else 'moderator' if chatter.moderator else 'everyone'
        if command['permission'] != 'everyone' and role not in {command['permission'], 'broadcaster'}:
            return
        now = time.monotonic()
        if self.deadlines.get(channel, 0) > now:
            return
        proxy = SimpleNamespace(broadcaster=ctx.broadcaster, chatter=chatter,
                                command=SimpleNamespace(name=command['name'], qualified_name=command['name']))
        if not ctx.bot.services.command_slowmode.allow(proxy):
            return
        self.deadlines = {key: value for key, value in self.deadlines.items() if value > now}
        self.deadlines[channel] = now + command['cooldown']
        parts = ctx.message.text[len(ctx.prefix):].strip().split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else ''
        try:
            result = await run_command(self.db, channel, command, user=chatter.name, channel_name=ctx.broadcaster.name, args=args, role=role)
        except ValueError as error:
            logging.getLogger(__name__).warning('Custom command %s in channel %s failed: %s', command['name'], channel, error)
            return
        for message in result['messages']:
            await ctx.send(message)
