"""Durable account observations and bounded message evidence; never enforces bans."""
import asyncio
import hashlib
import time
import uuid
from datetime import UTC, datetime


class ModerationShadow:
    WINDOW = 300
    GRACE = 10
    PER_USER = 10
    MAX_MESSAGES = 10000

    def __init__(self, db):
        self.db = db
        self.lock = asyncio.Lock()

    @staticmethod
    def timestamp(value, fallback):
        if isinstance(value, datetime):
            return value.timestamp(), 'eventsub'
        return fallback, 'received'

    async def correlate(self, connection, broadcaster_id, user_id):
        # A late arrival is eligible only inside the grace period, and only if
        # its event timestamp precedes the ban. Receipt order alone is not proof.
        await connection.execute('''INSERT OR IGNORE INTO moderation_ban_messages
            SELECT b.id, m.id FROM moderation_external_bans b
            JOIN moderation_shadow_messages m
              ON b.broadcaster_id=m.broadcaster_id AND b.user_id=m.user_id
            WHERE b.broadcaster_id=? AND b.user_id=?
              AND m.sent_at BETWEEN b.banned_at-300 AND b.banned_at
              AND m.received_at<=b.received_at+10
              AND (m.received_at<=b.received_at OR m.timestamp_source='eventsub')''',
            (broadcaster_id, user_id))

    async def message(self, payload, fingerprint, flagged, protected):
        now = time.time()
        sent, timestamp_source = self.timestamp(getattr(payload, 'timestamp', None), now)
        channel, user = str(payload.broadcaster.id), str(payload.chatter.id)
        message_id = getattr(payload, 'id', None) or str(uuid.uuid4())
        async with self.lock, self.db.acquire() as c:
            await c.execute('''INSERT OR IGNORE INTO moderation_shadow_messages
                (message_key,broadcaster_id,user_id,username,message,fingerprint,sent_at,
                 received_at,timestamp_source,flagged,protected)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (f'{channel}:{message_id}', channel, user, payload.chatter.name,
                 payload.text, fingerprint, sent, now, timestamp_source, int(flagged), int(protected)))
            await self.correlate(c, channel, user)
            # Retain linked evidence and flags for review. Only transient,
            # unlinked ordinary chat is capped and expires after five minutes.
            await c.execute('''DELETE FROM moderation_shadow_messages WHERE flagged=0
                AND id NOT IN (SELECT message_id FROM moderation_ban_messages)
                AND (received_at<? OR (broadcaster_id=? AND user_id=? AND id NOT IN
                  (SELECT id FROM moderation_shadow_messages WHERE broadcaster_id=? AND user_id=?
                   ORDER BY received_at DESC LIMIT 10)) OR id IN
                  (SELECT id FROM moderation_shadow_messages WHERE flagged=0
                   AND id NOT IN (SELECT message_id FROM moderation_ban_messages)
                   ORDER BY received_at DESC LIMIT -1 OFFSET 10000))''',
                (now-self.WINDOW, channel, user, channel, user))

    async def ban(self, *, broadcaster_id, user_id, username, moderator_id,
                  moderator_name, reason, source, banned_at=None):
        now = time.time()
        timestamp, timestamp_source = self.timestamp(banned_at, now)
        # Twitch timestamps distinguish repeat bans from redelivery. When the
        # transport supplies none, retain the event rather than discard evidence.
        key = hashlib.sha256(f'{source}:{broadcaster_id}:{user_id}:{timestamp}'.encode()).hexdigest()
        async with self.lock, self.db.acquire() as c:
            row = await c.fetchone('''INSERT OR IGNORE INTO moderation_external_bans
                (event_key,broadcaster_id,user_id,username,moderator_id,moderator_name,
                 source,reason,banned_at,received_at,timestamp_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
                (key, str(broadcaster_id), str(user_id), username, str(moderator_id),
                 moderator_name, source, reason, timestamp, now, timestamp_source))
            await self.correlate(c, str(broadcaster_id), str(user_id))
        return row is not None

    async def dashboard(self):
        async with self.db.acquire() as c:
            bans = await c.fetchall('''SELECT b.*, COUNT(m.id) AS matches,
                COALESCE(MAX(m.flagged),0) AS flagged,
                GROUP_CONCAT(m.message, char(10)) AS messages
                FROM moderation_external_bans b LEFT JOIN moderation_ban_messages bm ON bm.ban_id=b.id
                LEFT JOIN moderation_shadow_messages m ON m.id=bm.message_id
                GROUP BY b.id ORDER BY b.received_at DESC LIMIT 100''')
            flags = await c.fetchall('''SELECT m.* FROM moderation_shadow_messages m
                WHERE flagged=1 AND NOT EXISTS
                (SELECT 1 FROM moderation_ban_messages bm WHERE bm.message_id=m.id)
                ORDER BY received_at DESC LIMIT 100''')
            patterns = await c.fetchall('''SELECT m.fingerprint, MIN(m.message) AS example,
                COUNT(DISTINCT m.user_id) AS accounts, COUNT(DISTINCT b.broadcaster_id) AS channels,
                MAX(m.protected) AS protected_seen
                FROM moderation_shadow_messages m
                JOIN moderation_ban_messages bm ON bm.message_id=m.id
                JOIN moderation_external_bans b ON b.id=bm.ban_id
                GROUP BY m.fingerprint ORDER BY accounts DESC LIMIT 100''')
        now = time.time()
        rows = []
        for ban in bans:
            row = dict(ban)
            row['match_status'] = 'None' if not row['matches'] else ('Single candidate' if row['matches']==1 else 'Multiple candidates')
            row['outcome'] = ('Awaiting delayed messages' if now < row['received_at']+self.GRACE else
                              'Observation gap' if not row['matches'] else
                              'Agreement' if row['flagged'] else 'Detection gap')
            row['time'] = datetime.fromtimestamp(row['banned_at'], UTC).isoformat(timespec='seconds')+' UTC'
            rows.append(row)
        return dict(bans=rows, flags=[dict(r) for r in flags], patterns=[dict(r) for r in patterns])
