async def migrate(connection):
    await connection.execute("""CREATE TABLE custom_command_counters (
        broadcaster_id TEXT NOT NULL, name TEXT NOT NULL, value INTEGER NOT NULL,
        PRIMARY KEY (broadcaster_id, name)
    )""")
