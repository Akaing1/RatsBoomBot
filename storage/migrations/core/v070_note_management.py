"""Editable note titles, stable identities, and channel-owned ordering."""
async def migrate(connection):
    await connection.execute("ALTER TABLE streamer_notes ADD COLUMN title TEXT NOT NULL DEFAULT ''")
    await connection.execute("ALTER TABLE streamer_notes ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
    await connection.execute("ALTER TABLE streamer_notes ADD COLUMN note_id TEXT")
    await connection.execute("""WITH ordered AS (
        SELECT broadcaster_id, note_key, ROW_NUMBER() OVER (PARTITION BY broadcaster_id ORDER BY updated_at, note_key) AS n FROM streamer_notes)
        UPDATE streamer_notes SET position = (SELECT n FROM ordered WHERE ordered.broadcaster_id = streamer_notes.broadcaster_id AND ordered.note_key = streamer_notes.note_key), note_id = lower(hex(randomblob(16)))""")
    await connection.execute("CREATE UNIQUE INDEX streamer_note_identity ON streamer_notes(note_id)")
    await connection.execute("""CREATE TRIGGER streamer_note_identity AFTER INSERT ON streamer_notes
        WHEN NEW.note_id IS NULL BEGIN
        UPDATE streamer_notes SET note_id = lower(hex(randomblob(16))),
        position = (SELECT COALESCE(MAX(position), 0) + 1 FROM streamer_notes WHERE broadcaster_id = NEW.broadcaster_id AND note_key != NEW.note_key)
        WHERE broadcaster_id = NEW.broadcaster_id AND note_key = NEW.note_key; END""")
