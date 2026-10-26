"""User-authorized moderator actions. Tokens never join the bot's broadcaster token store."""
import asyncio
import json
import secrets
import weakref
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from config.settings import settings
from storage.viewer_sessions import valid_viewer_session
from web.shared.oauth import exchange_code_for_token, fetch_twitch_user, TWITCH_AUTHORIZE_URL
from web.viewer.auth import viewer_user_id, VIEWER_SERVER_TOKEN_KEY
from web.state import get_db

PRIVATE = {'Cache-Control': 'no-store'}
MOD_STATE = 'moderator_twitch_oauth'
# Bump only when a release requires renewed consent beyond scope changes.
AUTHORIZATION_REVISION = 1
CHAT_SCOPES = {'user:write:chat', 'user:read:emotes'}
MOD_SCOPES = CHAT_SCOPES | {'moderator:manage:chat_messages', 'moderator:manage:banned_users',
    'moderator:manage:announcements', 'moderator:manage:chat_settings', 'moderator:manage:automod',
    'moderator:manage:warnings', 'moderator:manage:shoutouts'}
_LOCKS = weakref.WeakValueDictionary()


def token_lock(actor):
    lock = _LOCKS.get(actor)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[actor] = lock
    return lock


def required_scopes(permission):
    return MOD_SCOPES


async def authorization_required(db, actor, permission):
    async with db.acquire() as connection:
        row = await connection.fetchone('SELECT * FROM moderator_twitch_tokens WHERE user_id = ?', (actor,))
    if row is None or row['authorization_revision'] < AUTHORIZATION_REVISION:
        return True
    try:
        return not required_scopes(permission).issubset(json.loads(row['scopes']))
    except (ValueError, TypeError):
        return True


async def invalidate_credentials(db, actor):
    async with db.acquire() as connection:
        await connection.execute('UPDATE moderator_twitch_tokens SET authorization_revision=0 WHERE user_id=?', (actor,))


async def save_credentials(db, actor, token):
    async with db.acquire() as connection:
        await connection.execute('''INSERT INTO moderator_twitch_tokens
            (user_id, access_token, refresh_token, scopes, authorization_revision) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET access_token=excluded.access_token,
            refresh_token=excluded.refresh_token, scopes=excluded.scopes,
            authorization_revision=excluded.authorization_revision''',
            (actor, token.access_token, token.refresh_token, json.dumps(token.scope), AUTHORIZATION_REVISION))


def start_authorization(request, access):
    state = secrets.token_urlsafe(32)
    request.session[MOD_STATE] = {'state': state, 'actor': access['user_id'], 'channel': access['broadcaster_id']}
    scopes = required_scopes(access['permission'])
    params = {'client_id': settings.CLIENT_ID, 'redirect_uri': settings.VIEWER_REDIRECT_URI,
        'response_type': 'code', 'scope': ' '.join(sorted(scopes)), 'state': state, 'force_verify': 'true'}
    return RedirectResponse(TWITCH_AUTHORIZE_URL + '?' + urlencode(params), headers=PRIVATE)


async def finish_authorization(request, *, state, code, error):
    saved = request.session.pop(MOD_STATE, None)
    if not saved or not state or not secrets.compare_digest(saved['state'], state):
        return HTMLResponse('Moderator authorization could not be verified. Return to My account and try again.', status_code=400, headers=PRIVATE)
    db = get_db()
    actor = viewer_user_id(request)
    if db is None or actor != saved['actor'] or not await valid_viewer_session(db, actor, request.session.get(VIEWER_SERVER_TOKEN_KEY)):
        return HTMLResponse('Sign in through My account before connecting moderator actions.', status_code=401, headers=PRIVATE)
    from storage.channel_access import require_grant
    try:
        async with db.acquire() as connection:
            access = await require_grant(connection, saved['channel'], actor)
    except PermissionError:
        return HTMLResponse('Channel access was revoked.', status_code=403, headers=PRIVATE)
    destination = f"/me/mod/{saved['channel']}"
    if error or not code:
        return RedirectResponse(destination, status_code=303, headers=PRIVATE)
    try:
        token = await exchange_code_for_token(code=code, redirect_uri=settings.VIEWER_REDIRECT_URI)
        user = await fetch_twitch_user(token.access_token)
        if user.user_id != actor:
            return HTMLResponse('Use the same Twitch account you used to sign in. No account was changed.', status_code=400, headers=PRIVATE)
        if not required_scopes(access['permission']).issubset(token.scope):
            return HTMLResponse('Twitch chat permission was not granted. Please try again.', status_code=400, headers=PRIVATE)
        lock = token_lock(actor)
        async with lock:
            await save_credentials(db, actor, token)
    except Exception:
        return HTMLResponse('Twitch authorization is temporarily unavailable. Return to My account and try again.', status_code=503, headers=PRIVATE)
    return RedirectResponse(destination + '?auth_message=Your+Twitch+account+is+connected.', status_code=303, headers=PRIVATE)


async def user_request(db, actor, method, path, *, params=None, body=None):
    lock = token_lock(actor)
    async with lock:
        async with db.acquire() as connection:
            row = await connection.fetchone('SELECT * FROM moderator_twitch_tokens WHERE user_id = ?', (actor,))
        if row is None or row['authorization_revision'] < AUTHORIZATION_REVISION:
            raise HTTPException(403, 'Authorize your Twitch account using the chat authorization button first.', headers=PRIVATE)
        # A 401 is the only retried write: Twitch rejected it before performing the action.
        async with httpx.AsyncClient(timeout=15) as client:
            for attempt in range(2):
                try:
                    response = await client.request(method, 'https://api.twitch.tv/helix/' + path,
                        params=params, json=body, headers={'Client-Id': settings.CLIENT_ID, 'Authorization': 'Bearer ' + row['access_token']})
                    if response.status_code == 401 and attempt == 0:
                        refresh = await client.post('https://id.twitch.tv/oauth2/token', data={
                            'grant_type': 'refresh_token', 'refresh_token': row['refresh_token'],
                            'client_id': settings.CLIENT_ID, 'client_secret': settings.CLIENT_SECRET})
                        if refresh.status_code != 200:
                            if refresh.status_code in (400, 401):
                                await invalidate_credentials(db, actor)
                            raise HTTPException(403, 'Reconnect your Twitch account to restore chat permissions.', headers=PRIVATE)
                        payload = refresh.json()
                        row = {**dict(row), 'access_token': payload['access_token'], 'refresh_token': payload.get('refresh_token', row['refresh_token'])}
                        async with db.acquire() as connection:
                            await connection.execute('UPDATE moderator_twitch_tokens SET access_token=?, refresh_token=? WHERE user_id=?', (row['access_token'], row['refresh_token'], actor))
                        continue
                    if response.status_code >= 400:
                        if response.status_code == 401:
                            await invalidate_credentials(db, actor)
                        message = {401: 'Reconnect your Twitch account to grant the required permission.',
                            403: 'Twitch denied this action. Your account must have the required moderator role and scopes in this channel.',
                            429: 'Twitch rate limit reached. Wait before trying again.'}.get(response.status_code, 'Twitch rejected the action. Check the input and current channel state.')
                        raise HTTPException(response.status_code if response.status_code < 500 else 502, message, headers=PRIVATE)
                    return response.json() if response.content else {}
                except httpx.RequestError as error:
                    raise HTTPException(504, 'Twitch did not confirm the action. Check the channel before retrying.', headers=PRIVATE) from error
