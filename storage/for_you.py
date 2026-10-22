"""Channel-scoped archive and quote manager operations."""
from storage.transactions import immediate_transaction


async def notes_page(db, channel, offset=0):
    async with db.acquire() as connection:
        rows = await connection.fetchall("SELECT note_key, notes, revision, updated_at FROM streamer_notes WHERE broadcaster_id = ? ORDER BY updated_at DESC, note_key DESC LIMIT 21 OFFSET ?", (channel, offset))
    return dict(items=[dict(row) for row in rows[:20]], more=len(rows) > 20)


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
