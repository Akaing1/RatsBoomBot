"""Explicit grants. No implicit access from Twitch moderator status."""
from storage.transactions import immediate_transaction
from storage.for_you import NOTE_SELECT


async def channels_for_user(db, user_id):
    async with db.acquire() as connection:
        return [dict(row) for row in await connection.fetchall(
            "SELECT * FROM channel_access WHERE user_id = ? ORDER BY channel_name", (user_id,))]


async def grants_for_owner(db, owner):
    async with db.acquire() as connection:
        return [dict(row) for row in await connection.fetchall(
            "SELECT * FROM channel_access WHERE broadcaster_id = ? ORDER BY user_name", (owner,))]


async def audit(connection, channel, actor, action, subject):
    await connection.execute("INSERT INTO channel_access_audit (broadcaster_id, actor_id, action, subject_id) VALUES (?, ?, ?, ?)",
                             (channel, actor, action, subject))


async def set_grant(db, owner, user, channel_name, user_name, permission):
    if permission not in ('view', 'edit', 'super', 'revoke') or owner == user:
        raise ValueError('Invalid access grant.')
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            if permission == 'revoke':
                await connection.execute("DELETE FROM channel_access WHERE broadcaster_id = ? AND user_id = ?", (owner, user))
            else:
                await connection.execute("""INSERT INTO channel_access VALUES (?, ?, ?, ?, 'dashboard', ?)
                    ON CONFLICT(broadcaster_id, user_id, feature) DO UPDATE SET
                    channel_name = excluded.channel_name, user_name = excluded.user_name, permission = excluded.permission""",
                    (owner, user, channel_name, user_name, permission))
            await audit(connection, owner, owner, 'access:' + permission, user)


async def require_grant(connection, channel, actor, edit=False):
    row = await connection.fetchone("SELECT * FROM channel_access WHERE broadcaster_id = ? AND user_id = ? AND feature = 'dashboard'", (channel, actor))
    if row is None or (edit and row['permission'] not in ('edit', 'super')):
        raise PermissionError('You no longer have access to this channel.')
    return dict(row)


async def delegated_notes(db, channel, actor, offset=0):
    async with db.acquire() as connection:
        # A single transaction keeps authorization and the returned data consistent.
        async with immediate_transaction(connection):
            grant = await require_grant(connection, channel, actor)
            rows = await connection.fetchall(NOTE_SELECT + " WHERE n.broadcaster_id = ? ORDER BY n.position LIMIT 21 OFFSET ?", (channel, offset))
    return grant, [dict(row) for row in rows[:20]], len(rows) > 20


async def save_delegated_note(db, channel, actor, identity, revision, title, notes):
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            await require_grant(connection, channel, actor, edit=True)
            row = await connection.fetchone("SELECT note_key FROM streamer_notes WHERE broadcaster_id = ? AND note_id = ? AND revision = ?", (channel, identity, revision))
            if row is None:
                raise ValueError('This note changed or was removed. Copy your edits, reload, then try again.')
            await connection.execute("UPDATE streamer_notes SET title = ?, notes = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP WHERE broadcaster_id = ? AND note_id = ?", (title.strip(), notes, channel, identity))
            await connection.execute("UPDATE streamer_workspace SET notes = ?, notes_revision = notes_revision + 1 WHERE broadcaster_id = ? AND note_key = ?", (notes, channel, row['note_key']))
            await audit(connection, channel, actor, 'notes:save', identity)


async def create_delegated_note(db, channel, actor, submission_id, title, notes):
    """Recheck access and create an idempotent For You note in one transaction."""
    key = f'moderator:{actor}:{submission_id}'
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            await require_grant(connection, channel, actor, edit=True)
            existing = await connection.fetchone(NOTE_SELECT + " WHERE n.broadcaster_id = ? AND n.note_key = ?", (channel, key))
            if existing:
                return dict(existing)
            await connection.execute("INSERT INTO streamer_notes (broadcaster_id, note_key, title, notes) VALUES (?, ?, ?, ?)",
                                     (channel, key, title.strip(), notes))
            note = await connection.fetchone(NOTE_SELECT + " WHERE n.broadcaster_id = ? AND n.note_key = ?", (channel, key))
            await audit(connection, channel, actor, 'notes:create', note['note_id'])
            return dict(note)
