"""Cached channel commands with one shared channel cooldown, no script execution."""
import asyncio
import json
import logging
import time
from types import SimpleNamespace

from twitchio.exceptions import HTTPException, MessageRejectedError

from storage.custom_commands import list_commands, run_command


class CustomCommandService:
    def __init__(self, db):
        self.db = db
        self.commands = {}
        self.deadlines = {}
        self.delivering = set()
        self.next_send = {}
        self.backoff = {}

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
        if channel in self.delivering:
            return
        now = time.monotonic()
        if self.backoff.get(channel, 0) > now:
            return
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
        self.delivering.add(channel)
        try:
            try:
                result = await run_command(self.db, channel, command, user=chatter.name, channel_name=ctx.broadcaster.name, args=args, role=role)
            except ValueError as error:
                logging.getLogger(__name__).warning('Custom command %s in channel %s failed: %s', command['name'], channel, error)
                return
            await self._deliver(ctx, channel, result['messages'])
        finally:
            self.delivering.discard(channel)

    async def _deliver(self, ctx, channel, messages):
        logger = logging.getLogger(__name__)
        retried = False
        for message in messages:
            while True:
                delay = self.next_send.get(channel, 0) - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                self.next_send[channel] = time.monotonic() + 1.1
                try:
                    await ctx.send(message)
                    break
                except MessageRejectedError as error:
                    # Duplicate greetings must not prevent later, distinct replies.
                    logger.warning('Custom command reply rejected in channel %s (%s).', channel, error.code)
                    break
                except HTTPException as error:
                    if error.status != 429:
                        raise
                    self.backoff[channel] = time.monotonic() + 30
                    logger.warning('Custom command chat rate limited in channel %s; %s.', channel,
                                   'stopping delivery after one retry' if retried else 'retrying reply in 30 seconds')
                    if retried:
                        return
                    retried = True
                    await asyncio.sleep(30)
                    # Retry only this reply, never the interpreter or counter changes.
