async def migrate(connection):
    await connection.execute('''CREATE TABLE custom_commands (
        broadcaster_id TEXT NOT NULL, name TEXT NOT NULL,
        definition TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (broadcaster_id, name)
    )''')
