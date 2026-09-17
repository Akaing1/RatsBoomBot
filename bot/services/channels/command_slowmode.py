import time

from twitchio.ext import commands


class SlowmodeBlocked(commands.GuardFailure):
    """A silently ignored command attempt."""


class CommandSlowmodeService:
    COOLDOWN_SECONDS = 120

    def __init__(self, db):
        self.db = db
        self.enabled_channels = set()
        self.deadlines = {}

    async def setup(self) -> None:
        async with self.db.acquire() as connection:
            rows = await connection.fetchall("SELECT broadcaster_id FROM command_slowmode WHERE enabled = 1")
        self.enabled_channels = {str(row["broadcaster_id"]) for row in rows}

    async def set_enabled(self, broadcaster_id: str, enabled: bool) -> None:
        broadcaster_id = str(broadcaster_id)
        async with self.db.acquire() as connection:
            await connection.execute("INSERT INTO command_slowmode (broadcaster_id, enabled) VALUES (?, ?) ON CONFLICT(broadcaster_id) DO UPDATE SET enabled = excluded.enabled", (broadcaster_id, int(enabled)))
        if enabled:
            self.enabled_channels.add(broadcaster_id)
        else:
            self.enabled_channels.discard(broadcaster_id)
            self.deadlines = {key: value for key, value in self.deadlines.items() if key[0] != broadcaster_id}

    def allow(self, ctx) -> bool:
        # Groups may run global guards more than once for the same invocation.
        if getattr(ctx, "_slowmode_allowed", False):
            return True
        broadcaster_id = str(ctx.broadcaster.id)
        user_id = str(ctx.chatter.id)
        if broadcaster_id not in self.enabled_channels or getattr(ctx.chatter, "moderator", False) or user_id == broadcaster_id or ctx.command.name == "kamikaze":
            return True
        now = time.monotonic()
        key = (broadcaster_id, user_id)
        if self.deadlines.get(key, 0) > now:
            return False
        self.deadlines = {key: deadline for key, deadline in self.deadlines.items() if deadline > now}
        self.deadlines[key] = now + self.COOLDOWN_SECONDS
        ctx._slowmode_allowed = True
        return True
