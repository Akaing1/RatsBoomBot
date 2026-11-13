import json

from bot.command_blocks import validate_command
from storage.transactions import immediate_transaction


async def list_commands(db, channel):
    async with db.acquire() as connection:
        rows = await connection.fetchall('SELECT definition, revision FROM custom_commands WHERE broadcaster_id = ? ORDER BY name', (str(channel),))
    return [{'command': json.loads(row['definition']), 'revision': row['revision']} for row in rows]


async def change_command(db, channel, command, revision, delete=False, original_name=None):
    validate_command(command, check_random_order=not delete)
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


async def run_command(db, channel, command, *, preview=False, **context):
    """Serialize counter reads and writes; previews run on a disposable snapshot."""
    from bot.command_blocks import execute
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            rows = await connection.fetchall('SELECT name, value FROM custom_command_counters WHERE broadcaster_id = ?', (str(channel),))
            counters = {row['name']: row['value'] for row in rows}
            context['channel'] = context.pop('channel_name')
            result = execute(command, counters=counters, **context)
            if not preview:
                for name, value in result['counters'].items():
                    if counters.get(name) == value:
                        continue
                    await connection.execute("""INSERT INTO custom_command_counters (broadcaster_id, name, value) VALUES (?, ?, ?)
                        ON CONFLICT(broadcaster_id, name) DO UPDATE SET value = excluded.value""", (str(channel), name, value))
    return result


async def list_counters(db, channel):
    async with db.acquire() as connection:
        rows = await connection.fetchall('SELECT name, value FROM custom_command_counters WHERE broadcaster_id = ? ORDER BY name', (str(channel),))
    return {row['name']: row['value'] for row in rows}


async def set_counter(db, channel, name, value):
    """Change one channel's saved counter without affecting command definitions."""
    import re
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', name):
        raise ValueError('Invalid counter name.')
    if type(value) is not int or not -1_000_000_000_000 <= value <= 1_000_000_000_000:
        raise ValueError('Counter value must be an integer between -1 trillion and 1 trillion.')
    async with db.acquire() as connection:
        async with immediate_transaction(connection):
            exists = await connection.fetchone(
                'SELECT 1 FROM custom_command_counters WHERE broadcaster_id = ? AND name = ?',
                (str(channel), name))
            if exists is None:
                count = await connection.fetchone(
                    'SELECT COUNT(*) AS n FROM custom_command_counters WHERE broadcaster_id = ?',
                    (str(channel),))
                if count['n'] >= 100:
                    raise ValueError('A channel can have at most 100 counters.')
            await connection.execute("""INSERT INTO custom_command_counters (broadcaster_id, name, value)
                VALUES (?, ?, ?) ON CONFLICT(broadcaster_id, name) DO UPDATE SET value = excluded.value""",
                (str(channel), name, value))
