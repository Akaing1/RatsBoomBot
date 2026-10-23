"""Channel-scoped archive and quote manager operations."""
from storage.transactions import immediate_transaction


NOTE_SELECT = """SELECT n.*, CASE WHEN n.title != '' THEN n.title ELSE 'Unnamed note ' ||
    (SELECT COUNT(*) FROM streamer_notes p WHERE p.broadcaster_id = n.broadcaster_id AND p.title = '' AND p.position <= n.position)
    END AS display_name FROM streamer_notes n"""


async def notes_page(db, channel, offset=0):
    async with db.acquire() as connection:
        rows = await connection.fetchall(NOTE_SELECT + " WHERE n.broadcaster_id = ? ORDER BY n.position LIMIT 21 OFFSET ?", (channel, offset))
    return dict(items=[dict(row) for row in rows[:20]], more=len(rows) > 20)


async def manage_note(db, channel, action, identity='', revision=0, title='', notes=''):
    import uuid
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            if action == 'create':
                key = 'manual:' + uuid.uuid4().hex
                await connection.execute("INSERT INTO streamer_notes (broadcaster_id, note_key, title, notes) VALUES (?, ?, ?, ?)", (channel, key, title.strip(), notes))
                row = await connection.fetchone(NOTE_SELECT + " WHERE n.broadcaster_id = ? AND n.note_key = ?", (channel, key))
                return dict(row)
            row = await connection.fetchone("SELECT * FROM streamer_notes WHERE broadcaster_id = ? AND note_id = ?", (channel, identity))
            if row is None or row['revision'] != revision:
                raise ValueError('This note changed or was deleted. Keep your edits and reload the note list.')
            key, position = row['note_key'], row['position']
            if action == 'save':
                await connection.execute("UPDATE streamer_notes SET title = ?, notes = ?, revision = revision + 1, updated_at = CURRENT_TIMESTAMP WHERE broadcaster_id = ? AND note_id = ?", (title.strip(), notes, channel, identity))
                await connection.execute("UPDATE streamer_workspace SET notes = ?, notes_revision = notes_revision + 1 WHERE broadcaster_id = ? AND note_key = ?", (notes, channel, key))
            elif action == 'delete':
                await connection.execute("DELETE FROM streamer_notes WHERE broadcaster_id = ? AND note_id = ?", (channel, identity))
                await connection.execute("UPDATE streamer_notes SET position = position - 1 WHERE broadcaster_id = ? AND position > ?", (channel, position))
                await connection.execute("UPDATE streamer_workspace SET notes = '', notes_revision = notes_revision + 1 WHERE broadcaster_id = ? AND note_key = ?", (channel, key))
                return None
            elif action in ('up', 'down'):
                target = position + (-1 if action == 'up' else 1)
                other = await connection.fetchone("SELECT note_id FROM streamer_notes WHERE broadcaster_id = ? AND position = ?", (channel, target))
                if other:
                    await connection.execute("UPDATE streamer_notes SET position = ? WHERE broadcaster_id = ? AND note_id = ?", (position, channel, other['note_id']))
                    await connection.execute("UPDATE streamer_notes SET position = ? WHERE broadcaster_id = ? AND note_id = ?", (target, channel, identity))
            else:
                raise ValueError('Unknown note action.')
            result = await connection.fetchone(NOTE_SELECT + " WHERE n.broadcaster_id = ? AND n.note_id = ?", (channel, identity))
            return dict(result)


async def quotes_page(db, channel, search='', offset=0):
    async with db.acquire() as connection:
        rows = await connection.fetchall("SELECT manager_id, number, message, added_at FROM channel_quotes WHERE broadcaster_id = ? AND instr(lower(message), lower(?)) > 0 ORDER BY number DESC LIMIT 21 OFFSET ?", (channel, search, offset))
    return dict(items=[dict(row) for row in rows[:20]], more=len(rows) > 20)


async def change_quote(db, channel, identity, original, message=None):
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            row = await connection.fetchone("SELECT number, message FROM channel_quotes WHERE broadcaster_id = ? AND manager_id = ?", (channel, identity))
            if row is None or row['message'] != original:
                raise ValueError('This quote changed or was removed. Refresh the list and try again.')
            if message is not None:
                await connection.execute("UPDATE channel_quotes SET message = ? WHERE broadcaster_id = ? AND manager_id = ?", (message, channel, identity))
            else:
                await connection.execute("DELETE FROM channel_quotes WHERE broadcaster_id = ? AND manager_id = ?", (channel, identity))
                await connection.execute("UPDATE channel_quotes SET number = -number WHERE broadcaster_id = ? AND number > ?", (channel, row['number']))
                await connection.execute("UPDATE channel_quotes SET number = -number - 1 WHERE broadcaster_id = ? AND number < 0", (channel,))
                await connection.execute("UPDATE channel_quote_sequences SET last_number = last_number - 1 WHERE broadcaster_id = ?", (channel,))
