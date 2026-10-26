"""Explicit, fail-closed route delegation for the shared channel Overview."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, RedirectResponse
from twitchio.http import Route
from storage.channel_access import require_grant, audit
from storage.viewer_sessions import valid_viewer_session
from web.admin.auth import validate_csrf_token
from web.channel.routers import dashboard as owner
from web.viewer.auth import viewer_user_id, VIEWER_SERVER_TOKEN_KEY
from web.viewer.twitch_actions import user_request, start_authorization
from web.state import get_db, get_bot

PRIVATE = {'Cache-Control': 'no-store'}


async def authorize(request: Request, channel: str, capability='view'):
    db = get_db()
    actor = viewer_user_id(request)
    if db is None:
        raise HTTPException(503, 'Channel access is temporarily unavailable.', headers=PRIVATE)
    if not actor or not await valid_viewer_session(db, actor, request.session.get(VIEWER_SERVER_TOKEN_KEY)):
        raise HTTPException(401, 'Sign in through My account to continue.', headers=PRIVATE)
    try:
        async with db.acquire() as connection:
            access = await require_grant(connection, channel, actor)
    except PermissionError as error:
        raise HTTPException(403, str(error), headers=PRIVATE) from error
    if capability == 'settings' and access['permission'] != 'super':
        raise HTTPException(403, 'Super moderator access is required.', headers=PRIVATE)
    if capability == 'moderate' and access['permission'] not in ('edit', 'super'):
        raise HTTPException(403, 'Moderator access is required.', headers=PRIVATE)
    request.state.channel_access = access
    return access


async def still_authorized(request):
    import time
    now = time.monotonic()
    if now - getattr(request.state, "access_checked_at", 0) < 5:
        return
    request.state.access_checked_at = now
    access = request.state.channel_access
    await authorize(request, access['broadcaster_id'])


class DelegatedRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handle(request):
            response = await original(request)
            response.headers['Cache-Control'] = 'no-store'
            location = response.headers.get('location', '')
            if location == '/connect':
                return JSONResponse({'detail': 'This channel is unavailable.'}, status_code=404, headers=PRIVATE)
            if location.startswith('/channel'):
                response.headers['location'] = f"/me/mod/{request.path_params['channel']}" + location[len('/channel'):]
            if request.method == 'POST' and response.status_code < 400:
                access = request.state.channel_access
                db = get_db()
                async with db.acquire() as connection:
                    await audit(connection, access['broadcaster_id'], access['user_id'], 'dashboard:' + self.name, '')
            return response
        return handle


router = APIRouter(route_class=DelegatedRoute)


def permission_dependency(capability):
    async def check(request: Request, channel: str):
        await authorize(request, channel, capability)
        request.state.check_channel_access = lambda: still_authorized(request)
    return check


# Nothing outside this allowlist can be reached under a moderator URL.
READS = {'/channel', '/channel/api/dashboard-stats', '/channel/api/redemptions',
    '/channel/api/viewer-queue', '/channel/api/chat/stream',
    '/channel/api/chat/users', '/channel/api/chat/pinned', '/channel/api/ad-status', '/channel/api/raid-contributors'}
MODERATE = {'/channel/api/viewer-queue/action', '/channel/viewer-queue/remove', '/channel/api/ads/action'}
SETTINGS = {'/channel/settings', '/channel/customization', '/channel/features/toggles',
    '/channel/protected-users/search', '/channel/protected-users/add', '/channel/protected-users/remove',
    '/channel/viewer-queue/blacklist', '/channel/api/channel-metadata', '/channel/api/games'}
for route in owner.router.routes:
    if route.path not in READS | MODERATE | SETTINGS:
        continue
    capability = 'view' if route.path in READS else 'moderate' if route.path in MODERATE else 'settings'
    router.add_api_route(route.path.replace('/channel', '/me/mod/{channel}', 1), route.endpoint,
        methods=list(route.methods), dependencies=[Depends(permission_dependency(capability))], name='mod_' + route.name,
        response_class=route.response_class)


async def action_context(request, channel, csrf_token, capability='moderate'):
    access = await authorize(request, channel, capability)
    validate_csrf_token(request, csrf_token)
    return access, get_db()


@router.get('/me/mod/{channel}/connect')
async def connect_actions(request: Request, channel: str):
    return start_authorization(request, await authorize(request, channel))


@router.post('/me/mod/{channel}/api/chat/send')
async def send_chat(request: Request, channel: str, message: str = Form(..., max_length=500), target: str = Form('twitch'),
                    csrf_token: str = Form(...), reply_parent_message_id: str = Form('')):
    access, db = await action_context(request, channel, csrf_token, 'view')
    message = message.strip()
    if not message or target != 'twitch':
        raise HTTPException(400, 'Enter a Twitch message. Moderator messages are sent only as your Twitch account.')
    if message.startswith('/'):
        await authorize(request, channel, 'moderate')
        if reply_parent_message_id:
            raise HTTPException(400, 'Slash commands cannot be sent as replies.')
        await slash_command(db, access, message)
        return JSONResponse({'sent': ['twitch'], 'errors': {}, 'message': 'Command completed.'}, headers=PRIVATE)
    body = {'broadcaster_id': channel, 'sender_id': access['user_id'], 'message': message}
    if reply_parent_message_id:
        if not reply_parent_message_id.startswith('twitch:'):
            raise HTTPException(400, 'Choose a Twitch message to reply to.')
        body['reply_parent_message_id'] = reply_parent_message_id[7:]
    payload = await user_request(db, access['user_id'], 'POST', 'chat/messages', body=body)
    result = (payload.get('data') or [{}])[0]
    if not result.get('is_sent'):
        raise HTTPException(400, 'Twitch did not send this message. Check channel chat restrictions.')
    return JSONResponse({'sent': ['twitch'], 'errors': {}, 'message_ids': {'twitch': 'twitch:' + result['message_id']}}, headers=PRIVATE)


async def slash_command(db, access, message):
    command, _, args = message[1:].partition(' ')
    command, args = command.lower(), args.strip()
    channel, actor = access['broadcaster_id'], access['user_id']
    params = {'broadcaster_id': channel, 'moderator_id': actor}
    async def call(method, path, *, body=None, query=None):
        return await user_request(db, actor, method, path, params=query or params, body=body)
    bot = get_bot()
    if bot is None:
        raise HTTPException(503, 'Bot runtime unavailable.')
    async def resolve(login):
        users = await bot.fetch_users(logins=[login.lstrip('@')])
        if not users:
            raise HTTPException(404, 'Twitch user not found.')
        return str(users[0].id)
    if command in {'ban', 'timeout', 'unban', 'warn'}:
        values = args.split()
        if not values:
            raise HTTPException(400, 'Enter a Twitch username.')
        user = await resolve(values.pop(0))
        if command == 'unban':
            await call('DELETE', 'moderation/bans', query={**params, 'user_id': user})
        elif command == 'warn':
            if not values:
                raise HTTPException(400, 'Enter a warning reason.')
            await call('POST', 'moderation/warnings', body={'data': {'user_id': user, 'reason': ' '.join(values)}})
        else:
            data = {'user_id': user}
            if command == 'timeout':
                duration = int(values.pop(0)) if values and values[0].isdigit() else 600
                if not 1 <= duration <= 1209600:
                    raise HTTPException(400, 'Timeout duration is out of range.')
                data['duration'] = duration
            if values:
                data['reason'] = ' '.join(values)
            await call('POST', 'moderation/bans', body={'data': data})
    elif command == 'clear':
        await call('DELETE', 'moderation/chat')
        bot.services.live_chat.clear_chat(channel)
    elif command.startswith('announce') and command in {'announce', 'announceblue', 'announcegreen', 'announceorange', 'announcepurple'}:
        if not args:
            raise HTTPException(400, 'Enter an announcement message.')
        await call('POST', 'chat/announcements', body={'message': args, 'color': command[8:] or 'primary'})
    elif command in {'slow', 'slowoff', 'followers', 'followersoff', 'subscribers', 'subscribersoff', 'emoteonly', 'emoteonlyoff', 'uniquechat', 'uniquechatoff'}:
        base = command.removesuffix('off')
        key = {'slow':'slow_mode', 'followers':'follower_mode', 'subscribers':'subscriber_mode', 'emoteonly':'emote_mode', 'uniquechat':'unique_chat_mode'}[base]
        body = {key: not command.endswith('off')}
        if args and base in {'slow', 'followers'}:
            if not args.isdigit():
                raise HTTPException(400, 'Enter a valid duration.')
            body['slow_mode_wait_time' if base == 'slow' else 'follower_mode_duration'] = int(args)
        await call('PATCH', 'chat/settings', body=body)
    elif command == 'shoutout':
        if not args:
            raise HTTPException(400, 'Enter a channel username.')
        await call('POST', 'chat/shoutouts', query={'from_broadcaster_id': channel, 'to_broadcaster_id': await resolve(args), 'moderator_id': actor})
    else:
        raise HTTPException(400, 'That command is not available in the moderator dashboard.')
    async with db.acquire() as connection:
        await audit(connection, channel, actor, 'twitch:' + command, '')


@router.post('/me/mod/{channel}/api/chat/moderate')
async def moderate_message(request: Request, channel: str, action: str = Form(...), message_id: str = Form(...),
                          duration_minutes: str = Form(''), csrf_token: str = Form(...)):
    access, db = await action_context(request, channel, csrf_token)
    if not message_id.startswith('twitch:'):
        raise HTTPException(400, 'Only Twitch messages can be moderated here.')
    bot = get_bot()
    if bot is None or bot.services is None:
        raise HTTPException(503, 'Bot runtime unavailable.')
    live = bot.services.live_chat
    params = {'broadcaster_id': channel, 'moderator_id': access['user_id'], 'message_id': message_id[7:]}
    pinned = live.get_pinned_message(channel)
    if action == 'delete':
        await user_request(db, access['user_id'], 'DELETE', 'moderation/chat', params=params)
        await live.remove_message(channel, message_id)
        return JSONResponse({'action': 'deleted', 'message_id': message_id, 'pinned': None})
    if action not in {'pin', 'pin-duration'}:
        raise HTTPException(400, 'Unknown moderation action.')
    if action == 'pin-duration':
        if pinned is None or pinned.get('id') != message_id:
            raise HTTPException(409, 'That message is no longer pinned.')
        if duration_minutes and duration_minutes not in {str(v) for v in list(range(1,11)) + [15,20,25,30]}:
            raise HTTPException(400, 'Unsupported pin duration.')
        if duration_minutes:
            params['duration_seconds'] = str(int(duration_minutes) * 60)
        await user_request(db, access['user_id'], 'PATCH', 'chat/pins', params=params)
        from datetime import datetime, UTC, timedelta
        ends = (datetime.now(UTC) + timedelta(minutes=int(duration_minutes))).isoformat() if duration_minutes else None
        return JSONResponse({'action': 'duration-updated', 'message_id': message_id, 'pinned': pinned, 'duration_minutes': int(duration_minutes) if duration_minutes else None, 'ends_at': ends})
    if pinned and pinned.get('id') == message_id:
        await user_request(db, access['user_id'], 'DELETE', 'chat/pins', params=params)
        await live.clear_pinned_message(channel)
        return JSONResponse({'action': 'unpinned', 'message_id': message_id, 'pinned': None})
    message = live.find_message(channel, message_id)
    if message is None:
        raise HTTPException(404, 'Message is no longer in chat history.')
    await user_request(db, access['user_id'], 'PUT', 'chat/pins', params=params)
    await live.pin_message(channel, message)
    return JSONResponse({'action': 'pinned', 'message_id': message_id, 'pinned': message})


@router.post('/me/mod/{channel}/api/automod/action')
async def automod_action(request: Request, channel: str, action: str = Form(...), message_id: str = Form(...), csrf_token: str = Form(...)):
    access, db = await action_context(request, channel, csrf_token)
    if action not in {'approve', 'deny'}:
        raise HTTPException(400, 'Unknown AutoMod action.')
    await user_request(db, access['user_id'], 'POST', 'moderation/automod/message', body={
        'user_id': access['user_id'], 'msg_id': message_id, 'action': 'ALLOW' if action == 'approve' else 'DENY'})
    bot = get_bot()
    if bot and bot.services:
        bot.services.live_chat.resolve_automod_message(channel, message_id)
    return JSONResponse({'action': action, 'message_id': message_id})


async def prediction_request(channel, method, *, params=None, body=None):
    bot = get_bot()
    if bot is None:
        raise HTTPException(503, 'Bot runtime unavailable.')
    try:
        import asyncio
        return await asyncio.wait_for(bot._http.request_json(Route(method, 'predictions', params=params, json=body, token_for=channel)), timeout=15)
    except Exception as error:
        from twitchio import HTTPException as TwitchError
        if isinstance(error, TwitchError) and error.status in (401,403):
            raise HTTPException(403, 'The broadcaster must reconnect Twitch with prediction permissions. The channel must support Channel Points predictions.') from error
        raise HTTPException(502, 'Twitch could not complete the prediction request. Refresh before trying again.') from error


@router.get('/me/mod/{channel}/api/predictions')
async def predictions(request: Request, channel: str):
    await authorize(request, channel)
    payload = await prediction_request(channel, 'GET', params={'broadcaster_id': channel, 'first': 5})
    return JSONResponse({'data': payload.get('data', [])}, headers=PRIVATE)


@router.post('/me/mod/{channel}/api/predictions')
async def change_prediction(request: Request, channel: str, csrf_token: str = Form(...), action: str = Form(...),
                            title: str = Form('', max_length=45), outcomes: str = Form('', max_length=300),
                            window: int = Form(300, ge=30, le=1800), prediction_id: str = Form('', max_length=100),
                            winning_outcome_id: str = Form('', max_length=100)):
    await action_context(request, channel, csrf_token)
    if action == 'create':
        choices = [line.strip() for line in outcomes.splitlines() if line.strip()]
        if not title.strip() or not 2 <= len(choices) <= 10 or any(len(c) > 25 for c in choices) or len(set(choices)) != len(choices):
            raise HTTPException(400, 'Enter a title and 2–10 different outcomes (25 characters each).')
        body = {'broadcaster_id': channel, 'title': title.strip(), 'outcomes': [{'title': c} for c in choices], 'prediction_window': window}
        payload = await prediction_request(channel, 'POST', body=body)
    else:
        status = {'lock': 'LOCKED', 'cancel': 'CANCELED', 'resolve': 'RESOLVED'}.get(action)
        if not status or not prediction_id:
            raise HTTPException(400, 'Choose a prediction action.')
        current = await prediction_request(channel, 'GET', params={'broadcaster_id': channel, 'id': prediction_id})
        rows = [p for p in current.get('data', []) if p.get('id') == prediction_id and p.get('broadcaster_id') == channel]
        if not rows:
            raise HTTPException(404, 'Prediction not found in this channel.')
        if status == 'RESOLVED' and winning_outcome_id not in {v['id'] for v in rows[0]['outcomes']}:
            raise HTTPException(400, 'Choose an outcome from this prediction.')
        body = {'broadcaster_id': channel, 'id': prediction_id, 'status': status}
        if status == 'RESOLVED':
            body['winning_outcome_id'] = winning_outcome_id
        payload = await prediction_request(channel, 'PATCH', body=body)
    return JSONResponse({'data': payload.get('data', [])}, headers=PRIVATE)


@router.get('/me/mod/{channel}/api/chat/emotes')
async def own_emotes(request: Request, channel: str):
    access = await authorize(request, channel)
    bot = get_bot()
    if bot is None or bot.services is None:
        raise HTTPException(503, 'Bot runtime unavailable.')
    catalog = await bot.services.live_chat.get_emote_catalog(channel)
    # Channel/global emotes remain visible before personal Twitch authorization.
    emotes = [dict(e) for e in catalog.get('emotes', []) if e.get('provider') == '7tv' or e.get('scope') == 'global']
    try:
        payload = await user_request(get_db(), access['user_id'], 'GET', 'chat/emotes/user', params={'user_id': access['user_id'], 'broadcaster_id': channel})
        for e in payload.get('data', []):
            emotes.append({'name': e['name'], 'url': f"https://static-cdn.jtvnw.net/emoticons/v2/{e['id']}/default/dark/2.0", 'provider': 'twitch', 'scope': 'channel', 'group': 'My Twitch emotes', 'group_key': 'personal'})
        reconnect = False
    except HTTPException:
        reconnect = True
    return JSONResponse({'emotes': emotes, 'personal_group_key': 'personal', 'complete_twitch_catalog': False, 'twitch_reconnect_required': reconnect}, headers=PRIVATE)
