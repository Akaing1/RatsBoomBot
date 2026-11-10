import json

from bot.command_blocks import validate_command
from storage.transactions import immediate_transaction


async def list_commands(db, channel):
    async with db.acquire() as connection:
        rows = await connection.fetchall('SELECT definition, revision FROM custom_commands WHERE broadcaster_id = ? ORDER BY name', (str(channel),))
    return [{'command': json.loads(row['definition']), 'revision': row['revision']} for row in rows]


async def change_command(db, channel, command, revision, delete=False):
    validate_command(command)
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            row = await connection.fetchone('SELECT revision FROM custom_commands WHERE broadcaster_id = ? AND name = ?', (str(channel), command['name']))
            if (row['revision'] if row else 0) != revision:
                raise ValueError('This command changed in another tab. Reload before saving.')
            if delete:
                await connection.execute('DELETE FROM custom_commands WHERE broadcaster_id = ? AND name = ?', (str(channel), command['name']))
                return
            if row is None:
                count = await connection.fetchone('SELECT COUNT(*) AS n FROM custom_commands WHERE broadcaster_id = ?', (str(channel),))
                if count['n'] >= 50: raise ValueError('A channel can have at most 50 custom commands.')
            await connection.execute('''INSERT INTO custom_commands (broadcaster_id, name, definition, revision) VALUES (?, ?, ?, ?)
                ON CONFLICT(broadcaster_id, name) DO UPDATE SET definition = excluded.definition, revision = excluded.revision''',
                (str(channel), command['name'], json.dumps(command), revision + 1))
