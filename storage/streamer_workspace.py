"""Private workspace storage; timers use absolute deadlines, not background tasks."""
import time
import uuid
from datetime import datetime, UTC

from storage.transactions import immediate_transaction


async def read(connection, broadcaster_id):
    row = await connection.fetchone(
        "SELECT note_key, notes, notes_revision, timer_id, timer_label, timer_due_at FROM streamer_workspace WHERE broadcaster_id = ?",
        (str(broadcaster_id),),
    )
    state = dict(row) if row else dict(note_key="legacy", notes="", notes_revision=0, timer_id=None, timer_label="", timer_due_at=None)
    state["server_now"] = int(time.time())
    return state


def daily_key():
    return "day:" + datetime.now(UTC).date().isoformat()


async def select_note(connection, broadcaster_id, note_key):
    await connection.execute("INSERT OR IGNORE INTO streamer_workspace (broadcaster_id, note_key) VALUES (?, ?)", (str(broadcaster_id), note_key))
    current = await read(connection, broadcaster_id)
    if current['note_key'] != note_key:
        row = await connection.fetchone("SELECT notes FROM streamer_notes WHERE broadcaster_id = ? AND note_key = ?", (str(broadcaster_id), note_key))
        await connection.execute("UPDATE streamer_workspace SET note_key = ?, notes = ?, notes_revision = notes_revision + 1 WHERE broadcaster_id = ?", (note_key, row['notes'] if row else '', str(broadcaster_id)))


async def get_workspace(db, broadcaster_id, note_key=None):
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            await select_note(connection, broadcaster_id, note_key or daily_key())
            return await read(connection, broadcaster_id)


async def update_workspace(db, broadcaster_id, action, *, notes="", revision=0, label="", minutes=0, seconds=0, timer_id="", note_key=None):
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            await select_note(connection, broadcaster_id, note_key or daily_key())
            current = await read(connection, broadcaster_id)
            if action == "notes":
                if current["notes_revision"] != revision:
                    raise ValueError("Your notes changed in another tab. Copy your edits, then reload before saving.")
                await connection.execute(
                    "UPDATE streamer_workspace SET notes = ?, notes_revision = notes_revision + 1 WHERE broadcaster_id = ?",
                    (notes, str(broadcaster_id)),
                )
                await connection.execute("""INSERT INTO streamer_notes (broadcaster_id, note_key, notes, revision)
                    VALUES (?, ?, ?, 1) ON CONFLICT (broadcaster_id, note_key) DO UPDATE SET
                    notes = excluded.notes, revision = revision + 1, updated_at = CURRENT_TIMESTAMP""",
                    (str(broadcaster_id), current['note_key'], notes))
            elif action == "start":
                if (current["timer_id"] or "") != timer_id:
                    raise ValueError("The timer changed in another tab. Review it and try again.")
                await connection.execute(
                    "UPDATE streamer_workspace SET timer_id = ?, timer_label = ?, timer_due_at = ? WHERE broadcaster_id = ?",
                    (uuid.uuid4().hex, label, int(time.time()) + minutes * 60 + seconds, str(broadcaster_id)),
                )
            elif action == "clear":
                if current["timer_id"] != timer_id:
                    raise ValueError("The timer changed in another tab. Review it and try again.")
                await connection.execute(
                    "UPDATE streamer_workspace SET timer_id = NULL, timer_label = '', timer_due_at = NULL WHERE broadcaster_id = ?",
                    (str(broadcaster_id),),
                )
            else:
                raise ValueError("Unknown workspace action.")
            return await read(connection, broadcaster_id)
