"""Small declarative command language. Never evaluates code or arbitrary expressions."""
import re

FIELDS = {'user', 'channel', 'args', 'arg1', 'user.name', 'user.mention', 'user.channel', 'arg.name', 'arg.mention', 'arg.channel', 'channel.name', 'channel.url'}
ROLES = {'everyone', 'moderator', 'broadcaster'}


def validate_command(value):
    if not isinstance(value, dict) or set(value) != {'name', 'enabled', 'permission', 'cooldown', 'blocks'}:
        raise ValueError('Invalid command fields.')
    name = value['name']
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', name):
        raise ValueError('Use a command name with 1–32 lowercase letters, numbers or underscores, starting with a letter.')
    if type(value['enabled']) is not bool or value['permission'] not in ROLES:
        raise ValueError('Invalid command permissions or enabled state.')
    if type(value['cooldown']) is not int or not 0 <= value['cooldown'] <= 3600:
        raise ValueError('Cooldown must be between 0 and 3600 seconds.')
    nodes = 0

    def text(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 450 or any(c in value for c in '\r\n'):
            raise ValueError('Messages must contain 1–450 characters on one line.')
        for field in re.findall(r'\{([^{}]*)\}', value):
            if field not in FIELDS:
                raise ValueError('Unknown placeholder. Choose a supported value from the editor.')

    def walk(blocks, depth=0):
        nonlocal nodes
        if not isinstance(blocks, list) or depth > 6:
            raise ValueError('Limit branches to six levels.')
        steps = sends = 0
        for block in blocks:
            nodes += 1
            if nodes > 40 or not isinstance(block, dict):
                raise ValueError('Use at most 40 blocks.')
            position = block.get('position')
            if position is not None and (not isinstance(position, dict) or set(position) != {'x', 'y'} or any(type(v) not in (int, float) or not 0 <= v <= 20000 for v in position.values())):
                raise ValueError('Invalid block position.')
            block = {k: v for k, v in block.items() if k != 'position'}
            kind = block.get('type')
            if kind == 'reply' and set(block) == {'type', 'message'}:
                text(block['message']); cost, output = 1, 1
            elif kind == 'random' and set(block) == {'type', 'choices'}:
                if not isinstance(block['choices'], list) or not 1 <= len(block['choices']) <= 5:
                    raise ValueError('Add between one and five random messages.')
                for choice in block['choices']: text(choice)
                cost, output = 1, 1
            elif kind == 'if' and set(block) == {'type', 'condition', 'value', 'then', 'else'}:
                if block['condition'] not in {'has_argument', 'argument_equals', 'is_moderator', 'is_broadcaster'}:
                    raise ValueError('Unknown condition.')
                if not isinstance(block['value'], str) or len(block['value']) > 100:
                    raise ValueError('Condition values must be at most 100 characters.')
                a, b = walk(block['then'], depth + 1), walk(block['else'], depth + 1)
                cost, output = 1 + max(a[0], b[0]), max(a[1], b[1])
            elif kind == 'repeat' and set(block) == {'type', 'count', 'blocks'}:
                if type(block['count']) is not int or not 1 <= block['count'] <= 5:
                    raise ValueError('Repeat between one and five times.')
                a = walk(block['blocks'], depth + 1)
                cost, output = 1 + block['count'] * a[0], block['count'] * a[1]
            else:
                raise ValueError('Unknown block or unsupported block fields.')
            steps += cost; sends += output
        return steps, sends

    steps, sends = walk(value['blocks'])
    if steps > 64 or sends > 3:
        raise ValueError('A command may run at most 64 steps and send at most three messages, including repeats.')
    if not nodes or not sends:
        raise ValueError('Add at least one message block.')
    return value


def execute(command, *, user, channel, args='', role='everyone', choose=None):
    """Collect bounded output before any external effects; also used by the test panel."""
    import random
    validate_command(command)
    choose = choose or random.choice
    args = args[:500]
    values = {'user': user[:50], 'channel': channel[:50], 'args': args, 'arg1': args.split()[0] if args.split() else ''}
    # Channel URLs derive only from Twitch-style login names, never arbitrary input.
    def login(value):
        value = value.lstrip('@')
        return value.lower() if re.fullmatch(r'[A-Za-z0-9_]{1,25}', value) else ''
    user_login, arg_login, channel_login = login(user), login(values['arg1']), login(channel)
    values.update({'user.name': values['user'], 'user.mention': '@' + user_login if user_login else '',
                   'user.channel': 'https://www.twitch.tv/' + user_login if user_login else '',
                   'arg.name': arg_login, 'arg.mention': '@' + arg_login if arg_login else '',
                   'arg.channel': 'https://www.twitch.tv/' + arg_login if arg_login else '',
                   'channel.name': values['channel'], 'channel.url': 'https://www.twitch.tv/' + channel_login if channel_login else ''})
    output, trace = [], []
    def render(message):
        return re.sub(r'\{([^{}]+)\}', lambda m: values[m[1]], message)[:450]
    def walk(blocks):
        for block in blocks:
            kind = block['type']
            if kind == 'reply': output.append(render(block['message'])); trace.append('Send message')
            elif kind == 'random': output.append(render(choose(block['choices']))); trace.append('Choose random message')
            elif kind == 'repeat':
                trace.append(f"Repeat {block['count']} times")
                for _ in range(block['count']): walk(block['blocks'])
            else:
                match = {'has_argument': bool(args.strip()), 'argument_equals': args.strip().casefold() == block['value'].casefold(),
                         'is_moderator': role in {'moderator', 'broadcaster'}, 'is_broadcaster': role == 'broadcaster'}[block['condition']]
                trace.append(f"{block['condition']}: {'True' if match else 'False'}")
                walk(block['then'] if match else block['else'])
    allowed = command['permission'] == 'everyone' or role == 'broadcaster' or role == command['permission']
    if allowed: walk(command['blocks'])
    else: trace.append('Permission denied')
    return {'messages': output, 'trace': trace}
