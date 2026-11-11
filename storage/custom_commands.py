import json

from bot.command_blocks import validate_command
from storage.transactions import immediate_transaction


async def list_commands(db, channel):
    async with db.acquire() as connection:
        rows = await connection.fetchall('SELECT definition, revision FROM custom_commands WHERE broadcaster_id = ? ORDER BY name', (str(channel),))
    return [{'command': json.loads(row['definition']), 'revision': row['revision']} for row in rows]


async def change_command(db, channel, command, revision, delete=False, original_name=None):
    validate_command(command)
    original_name = original_name or command['name']
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            row = await connection.fetchone('SELECT revision FROM custom_commands WHERE broadcaster_id = ? AND name = ?', (str(channel), original_name))
            if (row['revision'] if row else 0) != revision:
                raise ValueError('This command changed in another tab. Reload before saving.')
            if original_name != command['name']:
                if row is None or revision == 0:
                    raise ValueError('The original command no longer exists. Reload before saving.')
                occupied = await connection.fetchone('SELECT 1 FROM custom_commands WHERE broadcaster_id = ? AND name = ?', (str(channel), command['name']))
                if occupied:
                    raise ValueError('That command name is already in use.')
            if delete:
                await connection.execute('DELETE FROM custom_commands WHERE broadcaster_id = ? AND name = ?', (str(channel), original_name))
                return
            if row is None:
                count = await connection.fetchone('SELECT COUNT(*) AS n FROM custom_commands WHERE broadcaster_id = ?', (str(channel),))
                if count['n'] >= 50: raise ValueError('A channel can have at most 50 custom commands.')
            if original_name != command['name']:
                await connection.execute('DELETE FROM custom_commands WHERE broadcaster_id = ? AND name = ?', (str(channel), original_name))
            await connection.execute('''INSERT INTO custom_commands (broadcaster_id, name, definition, revision) VALUES (?, ?, ?, ?)
                ON CONFLICT(broadcaster_id, name) DO UPDATE SET definition = excluded.definition, revision = excluded.revision''',
                (str(channel), command['name'], json.dumps(command), revision + 1))
