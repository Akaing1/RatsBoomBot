"""Track moderator consent requirements independently of routine app releases."""
async def migrate(connection):
    await connection.execute("ALTER TABLE moderator_twitch_tokens ADD COLUMN authorization_revision INTEGER NOT NULL DEFAULT 1")
