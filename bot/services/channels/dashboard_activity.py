"""Bounded, channel-scoped history for dashboard commands and moderator activity."""
import asyncio
import json
import logging
from collections import defaultdict, deque

LOGGER = logging.getLogger('RatBoomBot')


class DashboardActivityHistory:
    def __init__(self, db):
        self.db = db
        self.commands = defaultdict(lambda: deque(maxlen=100))
        self.mod_actions = defaultdict(lambda: deque(maxlen=100))
        self.ready = False
        self.dirty = set()
        self.tasks = {}

    async def setup(self):
        async with self.db.acquire() as connection:
            rows = await connection.fetchall('SELECT broadcaster_id, kind, entries_json FROM dashboard_activity_history')
        for row in rows:
            if row['kind'] not in {'commands', 'mod_actions'}:
                continue
            try:
                entries = json.loads(row['entries_json'])
                if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                    raise ValueError('Invalid activity history')
            except (TypeError, ValueError):
                LOGGER.warning('[Activity] Ignoring invalid history for %s.', row['broadcaster_id'])
                continue
            getattr(self, row['kind'])[str(row['broadcaster_id'])].extend(entries[-100:])
        self.ready = True

    def changed(self, broadcaster_id, kind):
        if not self.ready:
            return
        key = (str(broadcaster_id), kind)
        self.dirty.add(key)
        if key in self.tasks:
            return

        async def save():
            try:
                # Coalesce bursts without writing once for every event.
                await asyncio.sleep(.05)
                while key in self.dirty:
                    self.dirty.discard(key)
                    entries = list(getattr(self, kind)[key[0]])
                    async with self.db.acquire() as connection:
                        await connection.execute('''INSERT INTO dashboard_activity_history VALUES (?, ?, ?)
                            ON CONFLICT(broadcaster_id, kind) DO UPDATE SET entries_json = excluded.entries_json''',
                            (*key, json.dumps(entries, separators=(',', ':'))))
                        await connection.commit()
            except Exception:
                LOGGER.exception('[Activity] Could not save %s history for %s.', kind, key[0])
            finally:
                self.tasks.pop(key, None)

        self.tasks[key] = asyncio.create_task(save(), name=f'dashboard-activity-{kind}-{key[0]}')

    async def flush(self):
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks.values()))
