import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.command_blocks import execute, validate_command
from bot.services.channels.custom_commands import CustomCommandService
from tests.test_streamer_workspace import workspace_client


def command(**changes):
    return dict(name='welcome', enabled=False, permission='everyone', cooldown=30,
                blocks=[{'type': 'if', 'condition': 'has_argument', 'value': '',
                         'then': [{'type': 'reply', 'message': 'Welcome {arg1}, from {user}!'}],
                         'else': [{'type': 'reply', 'message': 'Hello {user} in {channel}'}]}], **changes)


def test_same_interpreter_previews_both_branches_and_does_not_interpret_arguments():
    c = command()
    assert execute(c, user='Rat', channel='Mei', args='Guest extra')['messages'] == ['Welcome Guest, from Rat!']
    result = execute(c, user='Rat', channel='Mei')
    assert result['messages'] == ['Hello Rat in Mei']
    assert result['trace'][0] == 'has_argument: False'
    assert execute(c, user='{args}', channel='Mei', args='{user}')['messages'] == ['Welcome {user}, from {args}!']


@pytest.mark.parametrize('blocks', [
    [{'type': 'js', 'code': 'while(true){}'}],
    [{'type': 'reply', 'message': '{user.__class__}'}],
    [{'type': 'repeat', 'count': 100000, 'blocks': [{'type': 'reply', 'message': 'Spam'}]}],
    [{'type': 'repeat', 'count': 2, 'blocks': [{'type': 'repeat', 'count': 2, 'blocks': [{'type':'reply','message':'Spam'}]}]}],
    [{'type':'reply','message':'Hi'}] * 41,
])
def test_untrusted_blocks_and_total_nested_output_are_rejected(blocks):
    c = command(); c['blocks'] = blocks
    with pytest.raises(ValueError): validate_command(c)


def test_permissions_and_random_repeat():
    c = command(); c['permission'] = 'moderator'
    assert execute(c, user='Rat', channel='Mei')['messages'] == []
    c['blocks'] = [{'type':'repeat', 'count':3, 'blocks':[{'type':'random','choices':['A','B']}]}]
    assert execute(c, user='Rat', channel='Mei', role='broadcaster', choose=lambda choices:choices[-1])['messages'] == ['B'] * 3


@pytest.mark.asyncio
async def test_api_auth_csrf_preview_isolation_and_stale_writes(workspace_client):
    client, session, db = workspace_client
    url = '/channel/api/for-you/commands'
    async def post(c, **extra):
        return await client.post(url, data={'csrf_token':'secret','action':'save','definition':json.dumps(c), **extra})
    c = command()
    assert (await post(c, csrf_token='wrong')).status_code == 403
    preview = await post(c, action='test', args='Guest')
    assert preview.json()['messages'] == ['Welcome Guest, from TestViewer!']
    assert (await client.get(url)).json()['items'] == []
    assert (await post(c)).json()['revision'] == 1
    assert (await post(c)).status_code == 409
    assert (await post(c, revision=1)).json()['revision'] == 2
    session['channel_user_id'] = 'bob'
    assert (await client.get(url)).json()['items'] == []
    assert (await post(c, action='delete', revision=2)).status_code == 409
    session['channel_user_id'] = 'alice'
    assert (await post(c, action='delete', revision=2)).status_code == 200
    assert (await client.get(url)).json()['items'] == []
    for definition in ['{"name":[]}', '[]', 'not json']:
        assert (await client.post(url, data={'csrf_token':'secret','action':'test','definition':definition})).status_code == 400
    session.clear()
    assert (await client.get(url)).status_code == 401


@pytest.mark.asyncio
async def test_live_commands_respect_roles_channel_cooldown_and_slowmode(workspace_client):
    _, _, db = workspace_client
    service = CustomCommandService(db)
    c = command(); c['enabled'] = True
    service.commands = {'1': {'welcome':c}, '2': {'welcome':copy.deepcopy(c)}}
    identity = SimpleNamespace(is_custom_bot=lambda _:False)
    slowmode = SimpleNamespace(allow=lambda _:True)
    ctx = SimpleNamespace(prefix='!', invoked_with='welcome', broadcaster=SimpleNamespace(id='1',name='Mei'),
        chatter=SimpleNamespace(id='viewer',name='Rat',moderator=False), message=SimpleNamespace(text='!welcome Guest'),
        send=AsyncMock(), bot=SimpleNamespace(services=SimpleNamespace(chat_identity=identity,command_slowmode=slowmode)))
    c['permission'] = 'moderator'
    await service.handle(ctx); ctx.send.assert_not_awaited()
    c['permission'] = 'everyone'
    slowmode.allow=lambda _:False
    await service.handle(ctx); ctx.send.assert_not_awaited()
    slowmode.allow=lambda _:True
    await service.handle(ctx); ctx.send.assert_awaited_once_with('Welcome Guest, from Rat!')
    await service.handle(ctx); assert ctx.send.await_count == 1
    ctx.broadcaster.id='2'
    await service.handle(ctx); assert ctx.send.await_count == 2
    ctx.broadcaster.id='3'
    await service.handle(ctx); assert ctx.send.await_count == 2


@pytest.mark.asyncio
async def test_unknown_command_hook_reaches_custom_runtime_and_other_errors_do_not():
    from bot.bot import TwitchBot
    from bot.services.channels.command_slowmode import SlowmodeBlocked
    from twitchio.ext.commands.exceptions import CommandNotFound
    service = SimpleNamespace(handle=AsyncMock())
    bot = SimpleNamespace(services=SimpleNamespace(custom_commands=service))
    ctx = object()
    await TwitchBot.event_command_error(bot, SimpleNamespace(exception=CommandNotFound('welcome'), context=ctx))
    service.handle.assert_awaited_once_with(ctx)
    await TwitchBot.event_command_error(bot, SimpleNamespace(exception=SlowmodeBlocked('cooldown'), context=ctx))
    assert service.handle.await_count == 1


@pytest.mark.asyncio
async def test_storage_reloads_after_startup_and_custom_bot_messages_are_ignored(workspace_client):
    _, _, db = workspace_client
    from storage.custom_commands import change_command
    c = command(); c['enabled'] = True
    await change_command(db, '1', c, 0)
    service = CustomCommandService(db)
    await service.setup()
    assert service.commands['1']['welcome'] == c
    ctx = SimpleNamespace(prefix='!', invoked_with='welcome', broadcaster=SimpleNamespace(id='1'),
                          chatter=SimpleNamespace(id='bot'), message=SimpleNamespace(text='!welcome'),
                          bot=SimpleNamespace(services=SimpleNamespace(chat_identity=SimpleNamespace(is_custom_bot=lambda _:True))), send=AsyncMock())
    await service.handle(ctx); ctx.send.assert_not_awaited()
    await change_command(db, '1', c, 1, delete=True)
    await service.reload('1')
    assert service.commands['1'] == {}


def test_deep_nesting_and_execution_budget_are_rejected_even_without_many_messages():
    c = command()
    nested = [{'type':'reply', 'message':'Hello'}]
    for _ in range(7): nested = [{'type':'repeat', 'count':1, 'blocks':nested}]
    c['blocks'] = nested
    with pytest.raises(ValueError): validate_command(c)
    no_output = {'type':'if','condition':'has_argument','value':'','then':[],'else':[]}
    c['blocks'] = [{'type':'repeat','count':5,'blocks':[{'type':'repeat','count':5,'blocks':[no_output] * 3}]}, {'type':'reply','message':'Hello'}]
    with pytest.raises(ValueError, match='64 steps'): validate_command(c)


def test_structured_placeholders_and_legacy_names_share_safe_values():
    c = command()
    c['cooldown'] = 0
    c['blocks'] = [{'type': 'reply', 'message': '{user.name}|{user.mention}|{user.channel}|{arg.name}|{arg.mention}|{arg.channel}|{channel.name}|{channel.url}|{user}|{channel}|{args}|{arg1}'}]
    assert execute(c, user='Rat', channel='Mei', args='@Guest extra')['messages'] == [
        'Rat|@rat|https://www.twitch.tv/rat|guest|@guest|https://www.twitch.tv/guest|Mei|https://www.twitch.tv/mei|Rat|Mei|@Guest extra|@Guest']
    c['blocks'][0]['message'] = 'Link: {arg.channel}; mention: {arg.mention}; raw: {arg1}'
    for arg in ['', 'https://evil.example', '{user.name}', '../escape']:
        assert execute(c, user='Rat', channel='Mei', args=arg)['messages'] == [f'Link: ; mention: ; raw: {arg}']


@pytest.mark.parametrize('position', [{'x': -1, 'y': 0}, {'x': True, 'y': 0}, {'x': 0, 'y': 20001},
                                     {'x': float('nan'), 'y': 0}, {'x': float('inf'), 'y': 0},
                                     {'x': 0}, {'x': 0, 'y': 0, 'code': 'oops'}, []])
def test_canvas_positions_are_bounded_and_strict(position):
    c = command()
    c['blocks'][0]['position'] = position
    with pytest.raises(ValueError, match='position'):
        validate_command(c)


def test_layout_is_optional_and_cannot_change_execution_order_or_limits():
    c = command()
    c['blocks'] = [{'type': 'reply', 'message': 'first', 'position': {'x': 20000, 'y': 20000}},
                   {'type': 'reply', 'message': 'second', 'position': {'x': 0, 'y': 0}}]
    assert execute(c, user='Rat', channel='Mei')['messages'] == ['first', 'second']
    c['blocks'] *= 2
    with pytest.raises(ValueError, match='three messages'):
        validate_command(c)


@pytest.mark.asyncio
async def test_rename_is_atomic_scoped_and_revision_checked(workspace_client):
    client, session, db = workspace_client
    url = '/channel/api/for-you/commands'
    async def save(c, revision=0, original_name=''):
        return await client.post(url, data={'csrf_token': 'secret', 'action': 'save',
            'definition': json.dumps(c), 'revision': revision, 'original_name': original_name})
    c = command(); c['cooldown'] = 0
    assert (await save(c)).status_code == 200
    other = copy.deepcopy(c); other['name'] = 'taken'
    assert (await save(other)).status_code == 200
    assert (await save(other, 1, 'welcome')).status_code == 409
    renamed = copy.deepcopy(c); renamed['name'] = 'greetings'
    renamed['blocks'][0]['position'] = {'x': 500, 'y': 150.5}
    assert (await save(renamed, 0, 'welcome')).status_code == 409
    session['channel_user_id'] = 'bob'
    assert (await save(renamed, 1, 'welcome')).status_code == 409
    session['channel_user_id'] = 'alice'
    response = await save(renamed, 1, 'welcome')
    assert response.status_code == 200
    assert response.json()['revision'] == 2
    entries = (await client.get(url)).json()['items']
    assert {entry['command']['name'] for entry in entries} == {'greetings', 'taken'}
    assert next(entry['command'] for entry in entries if entry['command']['name'] == 'greetings') == renamed
    assert (await save(c, 1)).status_code == 409
    service = CustomCommandService(db)
    await service.reload('alice')
    assert 'welcome' not in service.commands['alice']
    assert service.commands['alice']['greetings'] == renamed


@pytest.mark.asyncio
async def test_zero_cooldown_allows_successive_invocations(workspace_client):
    _, _, db = workspace_client
    service = CustomCommandService(db)
    c = command(); c.update(enabled=True, cooldown=0)
    service.commands = {'1': {'welcome': c}}
    ctx = SimpleNamespace(prefix='!', invoked_with='welcome', broadcaster=SimpleNamespace(id='1', name='Mei'),
        chatter=SimpleNamespace(id='viewer', name='Rat', moderator=False), message=SimpleNamespace(text='!welcome'),
        send=AsyncMock(), bot=SimpleNamespace(services=SimpleNamespace(
            chat_identity=SimpleNamespace(is_custom_bot=lambda _: False), command_slowmode=SimpleNamespace(allow=lambda _: True))))
    await service.handle(ctx)
    await service.handle(ctx)
    assert ctx.send.await_count == 2
