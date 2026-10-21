"""Private workspace storage; timers use absolute deadlines, not background tasks."""
import time
import uuid

from storage.transactions import immediate_transaction


async def read(connection, broadcaster_id):
    row = await connection.fetchone(
        "SELECT notes, notes_revision, timer_id, timer_label, timer_due_at FROM streamer_workspace WHERE broadcaster_id = ?",
        (str(broadcaster_id),),
    )
    state = dict(row) if row else dict(notes="", notes_revision=0, timer_id=None, timer_label="", timer_due_at=None)
    state["server_now"] = int(time.time())
    return state


async def get_workspace(db, broadcaster_id):
    async with db.acquire() as connection:
        return await read(connection, broadcaster_id)


async def update_workspace(db, broadcaster_id, action, *, notes="", revision=0, label="", minutes=0, seconds=0, timer_id=""):
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            await connection.execute(
                "INSERT OR IGNORE INTO streamer_workspace (broadcaster_id) VALUES (?)", (str(broadcaster_id),)
            )
            current = await read(connection, broadcaster_id)
            if action == "notes":
                if current["notes_revision"] != revision:
                    raise ValueError("Your notes changed in another tab. Copy your edits, then reload before saving.")
                await connection.execute(
                    "UPDATE streamer_workspace SET notes = ?, notes_revision = notes_revision + 1 WHERE broadcaster_id = ?",
                    (notes, str(broadcaster_id)),
                )
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
