"""Archive streamer notes and give renumbered quotes stable manager identities."""
async def migrate(connection):
    await connection.execute("ALTER TABLE streamer_workspace ADD COLUMN note_key TEXT NOT NULL DEFAULT 'legacy'")
    await connection.execute("""CREATE TABLE streamer_notes (
        broadcaster_id TEXT NOT NULL, note_key TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
        revision INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (broadcaster_id, note_key))""")
    await connection.execute("""INSERT INTO streamer_notes (broadcaster_id, note_key, notes, revision)
        SELECT broadcaster_id, 'legacy', notes, notes_revision FROM streamer_workspace WHERE notes != ''""")
    await connection.execute("ALTER TABLE channel_quotes ADD COLUMN manager_id TEXT")
    await connection.execute("UPDATE channel_quotes SET manager_id = lower(hex(randomblob(16)))")
    await connection.execute("CREATE UNIQUE INDEX channel_quote_manager_id ON channel_quotes(manager_id)")
    await connection.execute("""CREATE TRIGGER channel_quote_manager_identity AFTER INSERT ON channel_quotes
        WHEN NEW.manager_id IS NULL BEGIN
        UPDATE channel_quotes SET manager_id = lower(hex(randomblob(16)))
        WHERE broadcaster_id = NEW.broadcaster_id AND number = NEW.number; END""")
