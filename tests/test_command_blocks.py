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
    bot = SimpleNamespace(services=SimpleNamespace(custom_commands=service, features=SimpleNamespace(
        get_profile_enabled=lambda _: True, get_globals_enabled=lambda _: True)))
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id="1"))
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


def counter_command(blocks=None):
    c = command(); c.update(cooldown=0, enabled=True)
    c['blocks'] = blocks if blocks is not None else [
        {'type': 'counter', 'name': 'deaths', 'operation': 'add', 'value': 1},
        {'type': 'reply', 'message': 'Deaths: {counter.deaths}'}]
    return c


def test_counter_operations_order_and_permissions():
    c = counter_command()
    source = {'deaths': 4}
    result = execute(c, user='Rat', channel='Mei', counters=source)
    assert result['messages'] == ['Deaths: 5']
    assert source == {'deaths': 4}
    c['blocks'][0].update(operation='subtract', value=2)
    assert execute(c, user='Rat', channel='Mei', counters=source)['counters']['deaths'] == 2
    c['blocks'][0].update(operation='set', value=0)
    assert execute(c, user='Rat', channel='Mei', counters=source)['messages'] == ['Deaths: 0']
    c['permission'] = 'moderator'
    assert execute(c, user='Rat', channel='Mei', counters=source)['counters'] == source
    c['permission'] = 'everyone';c['blocks'] = [{'type':'reply','message':'Missing: {counter.missing}'}]
    assert execute(c,user='Rat',channel='Mei')['messages'] == ['Missing: 0']


@pytest.mark.parametrize('changes', [{'name':'../invalid'}, {'name':'x'*33}, {'operation':'eval'}, {'value':True}, {'value':1.5}, {'value':1000000001}])
def test_invalid_counter_fields_are_rejected(changes):
    c = counter_command();c['blocks'][0].update(changes)
    with pytest.raises(ValueError):validate_command(c)


@pytest.mark.asyncio
async def test_counters_persist_are_channel_scoped_and_preview_never_writes(workspace_client):
    from storage.custom_commands import run_command, list_counters
    client, _, db = workspace_client
    c = counter_command()
    result = await run_command(db,'alice',c,user='Rat',channel_name='Mei')
    assert result['messages'] == ['Deaths: 1']
    preview = await client.post('/channel/api/for-you/commands',data={'csrf_token':'secret','action':'test','definition':json.dumps(c)})
    assert preview.json()['messages'] == ['Deaths: 2']
    assert await list_counters(db,'alice') == {'deaths':1}
    assert await list_counters(db,'bob') == {}
    service=CustomCommandService(db);await service.setup()
    assert (await run_command(db,'alice',c,user='Rat',channel_name='Mei'))['messages'] == ['Deaths: 2']
    assert (await client.get('/channel/api/for-you/commands')).json()['counters'] == {'deaths':2}


@pytest.mark.asyncio
async def test_counter_updates_are_atomic_under_concurrency_and_roll_back_failures(workspace_client):
    import asyncio
    from storage.custom_commands import run_command, list_counters
    _, _, db = workspace_client
    c = counter_command()
    await asyncio.gather(*(run_command(db,'alice',c,user='Rat',channel_name='Mei') for _ in range(12)))
    assert await list_counters(db,'alice') == {'deaths':12}
    fail = counter_command([{'type':'counter','name':'first','operation':'set','value':1},
                            {'type':'counter','name':'deaths','operation':'add','value':1}])
    async with db.acquire() as connection:
        await connection.execute('UPDATE custom_command_counters SET value = 1000000000000 WHERE broadcaster_id = ?',('alice',))
        await connection.commit()
    with pytest.raises(ValueError,match='Counter values'):
        await run_command(db,'alice',fail,user='Rat',channel_name='Mei')
    assert await list_counters(db,'alice') == {'deaths':1000000000000}
    many = {f'c{i}':0 for i in range(100)}
    with pytest.raises(ValueError,match='100 custom counters'):
        execute(c,user='Rat',channel='Mei',counters=many)


@pytest.mark.asyncio
async def test_live_counter_commands_share_values_across_command_names(workspace_client):
    from storage.custom_commands import list_counters
    _, _, db = workspace_client
    service = CustomCommandService(db)
    c = counter_command()
    show = counter_command([{'type':'reply','message':'Total {counter.deaths}'}]);show['name']='total'
    service.commands={'1': {'welcome':c,'total':show}}
    ctx=SimpleNamespace(prefix='!',invoked_with='welcome',broadcaster=SimpleNamespace(id='1',name='Mei'),
        chatter=SimpleNamespace(id='viewer',name='Rat',moderator=False),message=SimpleNamespace(text='!welcome'),
        send=AsyncMock(),bot=SimpleNamespace(services=SimpleNamespace(chat_identity=SimpleNamespace(is_custom_bot=lambda _:False),
        command_slowmode=SimpleNamespace(allow=lambda _:True))))
    await service.handle(ctx)
    ctx.invoked_with='total';ctx.message.text='!total'
    await service.handle(ctx)
    assert [call.args[0] for call in ctx.send.await_args_list] == ['Deaths: 1','Total 1']
    assert await list_counters(db,'1') == {'deaths':1}


def random_number_command():
    return counter_command([{'type':'random_number','name':'roll','min':1,'max':100},
                            {'type':'reply','message':'Roll: {random.roll}, again: {random.roll}'}])


def test_random_number_inclusive_bounds_reuse_and_fresh_invocations():
    from unittest.mock import Mock
    c=random_number_command()
    draw=Mock(side_effect=[1,100])
    assert execute(c,user='Rat',channel='Mei',draw=draw)['messages'] == ['Roll: 1, again: 1']
    result=execute(c,user='Rat',channel='Mei',draw=draw)
    assert result['messages'] == ['Roll: 100, again: 100']
    assert result['random'] == {'roll':100}
    assert draw.call_count == 2
    draw.assert_called_with(1,100)
    c['blocks'][0].update(min=-3,max=-3)
    assert execute(c,user='Rat',channel='Mei')['random'] == {'roll':-3}


@pytest.mark.parametrize('changes',[{'name':'bad.name'},{'name':'x'*33},{'min':True},{'min':1.5},
                                     {'min':101},{'min':-1000000001},{'max':1000000001},{'extra':'code'}])
def test_invalid_random_number_blocks_are_rejected(changes):
    c=random_number_command();c['blocks'][0].update(changes)
    with pytest.raises(ValueError):validate_command(c)


def test_random_results_follow_branch_order_and_permissions():
    c=random_number_command()
    c['blocks'].insert(1,{'type':'random_number','name':'roll','min':5,'max':5})
    assert execute(c,user='Rat',channel='Mei')['messages'] == ['Roll: 5, again: 5']
    c['blocks'][0]={'type':'if','condition':'has_argument','value':'','then':[c['blocks'][0]],'else':[]}
    del c['blocks'][1]
    with pytest.raises(ValueError,match='has not been generated'):
        execute(c,user='Rat',channel='Mei')
    c['blocks'][0]['else']=[{'type':'random_number','name':'roll','min':5,'max':5}]
    assert execute(c,user='Rat',channel='Mei',args='yes',draw=lambda low,high:5)['random'] == {'roll':5}
    c['permission']='moderator'
    assert execute(c,user='Rat',channel='Mei')['random'] == {}


@pytest.mark.asyncio
async def test_random_preview_and_live_runtime_and_failed_result_rollback(workspace_client):
    from storage.custom_commands import run_command,list_counters
    client,_,db=workspace_client
    c=random_number_command();c['blocks'][0].update(min=6,max=6)
    preview=await client.post('/channel/api/for-you/commands',data={'csrf_token':'secret','action':'test','definition':json.dumps(c)})
    assert preview.json()['random'] == {'roll':6}
    result=await run_command(db,'alice',c,user='Rat',channel_name='Mei')
    assert result['messages']==['Roll: 6, again: 6']
    assert await list_counters(db,'alice')=={}
    c['blocks']=[{'type':'counter','name':'wins','operation':'add','value':1},
                 {'type':'reply','message':'{random.missing}'}]
    with pytest.raises(ValueError,match='has not been generated'):
        await run_command(db,'alice',c,user='Rat',channel_name='Mei')
    assert await list_counters(db,'alice')=={}


@pytest.mark.asyncio
async def test_random_forward_references_are_rejected_on_save_and_preview(workspace_client):
    client,_,_=workspace_client
    c=random_number_command();c['blocks'].reverse()
    for action in ('save','test'):
        response=await client.post('/channel/api/for-you/commands',data={'csrf_token':'secret','action':action,'definition':json.dumps(c)})
        assert response.status_code==400
        assert 'before this message' in response.json()['detail']
    assert (await client.get('/channel/api/for-you/commands')).json()['items']==[]


def test_random_flow_checks_all_choices_branches_and_legacy_repeats():
    roll={'type':'random_number','name':'roll','min':1,'max':6}
    message={'type':'reply','message':'{random.roll}'}
    condition={'type':'if','condition':'has_argument','value':'','then':[roll],'else':[]}
    c=counter_command([condition,message])
    with pytest.raises(ValueError,match='every path'):validate_command(c)
    condition['else']=[copy.deepcopy(roll)];validate_command(c)
    condition['else']=[];c['blocks']=[roll,condition,message];validate_command(c)
    c['blocks']=[{'type':'random','choices':['hello','{random.roll}']},roll]
    with pytest.raises(ValueError,match='before this message'):validate_command(c)
    c['blocks']=[{'type':'repeat','count':2,'blocks':[message,roll]}]
    with pytest.raises(ValueError):validate_command(c)
    c['blocks']=[{'type':'repeat','count':1,'blocks':[roll]},message];validate_command(c)


@pytest.mark.asyncio
async def test_old_invalid_random_commands_can_still_be_deleted(workspace_client):
    client,_,db=workspace_client
    c=random_number_command();c['blocks'].reverse()
    async with db.acquire() as connection:
        await connection.execute('INSERT INTO custom_commands (broadcaster_id,name,definition,revision) VALUES (?,?,?,1)',('alice',c['name'],json.dumps(c)))
        await connection.commit()
    response=await client.post('/channel/api/for-you/commands',data={'csrf_token':'secret','action':'delete','definition':json.dumps(c),'revision':1})
    assert response.status_code==200
    assert (await client.get('/channel/api/for-you/commands')).json()['items']==[]


@pytest.fixture
def delivery_clock(monkeypatch):
    import bot.services.channels.custom_commands as module
    clock=SimpleNamespace(now=100.,waits=[])
    async def sleep(delay):
        clock.waits.append(delay);clock.now+=delay
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock.now))
    monkeypatch.setattr(module,'asyncio',SimpleNamespace(sleep=sleep))
    return clock


def rejected_reply(code='msg_duplicate'):
    from twitchio.exceptions import MessageRejectedError
    return MessageRejectedError('Rejected',message=SimpleNamespace(dropped_code=code,dropped_message='Rejected'),channel=SimpleNamespace(id='1'),content='Hello')


@pytest.mark.asyncio
async def test_duplicate_reply_does_not_abort_remaining_messages(delivery_clock):
    service=CustomCommandService(None)
    ctx=SimpleNamespace(send=AsyncMock(side_effect=[rejected_reply(),None,None]))
    await service._deliver(ctx,'1',['Hello','Rolled 9','Taco 1'])
    assert [c.args[0] for c in ctx.send.await_args_list]==['Hello','Rolled 9','Taco 1']
    assert delivery_clock.waits==pytest.approx([1.1,1.1])


@pytest.mark.asyncio
async def test_rate_limit_retries_delivery_without_rerunning_counters(workspace_client,delivery_clock):
    from twitchio.exceptions import HTTPException
    from storage.custom_commands import list_counters
    _,_,db=workspace_client
    service=CustomCommandService(db);service.commands={'1':{'welcome':counter_command()}}
    ctx=SimpleNamespace(prefix='!',invoked_with='welcome',broadcaster=SimpleNamespace(id='1',name='Mei'),
        chatter=SimpleNamespace(id='viewer',name='Rat',moderator=False),message=SimpleNamespace(text='!welcome'),
        send=AsyncMock(side_effect=[HTTPException(status=429,extra='too fast'),None]),
        bot=SimpleNamespace(services=SimpleNamespace(chat_identity=SimpleNamespace(is_custom_bot=lambda _:False),command_slowmode=SimpleNamespace(allow=lambda _:True))))
    await service.handle(ctx)
    assert [c.args[0] for c in ctx.send.await_args_list]==['Deaths: 1','Deaths: 1']
    assert await list_counters(db,'1')=={'deaths':1}
    assert delivery_clock.waits==[30]
    assert service.delivering==set()


@pytest.mark.asyncio
async def test_persistent_rate_limit_stops_after_one_retry_and_skips_busy_channels(delivery_clock):
    from twitchio.exceptions import HTTPException
    service=CustomCommandService(None)
    ctx=SimpleNamespace(send=AsyncMock(side_effect=HTTPException(status=429,extra='too fast')))
    await service._deliver(ctx,'1',['a','b','c'])
    assert ctx.send.await_count==2
    assert delivery_clock.waits==[30]
    assert service.backoff['1']>delivery_clock.now
    c=counter_command();service.commands={'1':{'welcome':c}}
    ctx.prefix='!';ctx.invoked_with='welcome';ctx.message=SimpleNamespace(text='!welcome')
    ctx.broadcaster=SimpleNamespace(id='1');ctx.chatter=SimpleNamespace(id='v',moderator=False)
    ctx.bot=SimpleNamespace(services=SimpleNamespace(chat_identity=SimpleNamespace(is_custom_bot=lambda _:False)))
    await service.handle(ctx)  # backoff exits before executing counters or sending
    service.backoff.clear();service.delivering.add('1')
    await service.handle(ctx)
    assert ctx.send.await_count==2


@pytest.mark.asyncio
async def test_counter_panel_endpoint_is_private_current_and_preserves_orphaned_counters(workspace_client):
    from storage.custom_commands import run_command,change_command
    client,session,db=workspace_client
    c=counter_command()
    await change_command(db,'alice',c,0)
    await run_command(db,'alice',c,user='Rat',channel_name='Mei')
    await change_command(db,'alice',c,1,delete=True)
    url='/channel/api/for-you/commands/counters'
    response=await client.get(url)
    assert response.json()=={'counters':{'deaths':1}}
    assert response.headers['cache-control']=='no-store'
    await run_command(db,'alice',c,user='Rat',channel_name='Mei')
    assert (await client.get(url)).json()['counters']=={'deaths':2}
    session['channel_user_id']='bob'
    assert (await client.get(url)).json()=={'counters':{}}
    session.clear()
    assert (await client.get(url)).status_code==401
