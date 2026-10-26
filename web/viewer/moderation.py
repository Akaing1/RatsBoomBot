"""Delegation never changes the signed-in owner's channel identity."""
import asyncio
import re

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from storage.channel_access import channels_for_user, delegated_notes, grants_for_owner, save_delegated_note, set_grant
from storage.viewer_sessions import valid_viewer_session
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY, CHANNEL_USER_DISPLAY_NAME_KEY
from web.shared.common import templates
from web.state import get_db, get_bot
from web.viewer.auth import viewer_user_id, VIEWER_SERVER_TOKEN_KEY

router = APIRouter()
PRIVATE = {"Cache-Control": "no-store"}


def database():
    db = get_db()
    if db is None:
        raise HTTPException(503, 'Channel access is temporarily unavailable.')
    return db


def owner_id(request):
    owner = request.session.get(CHANNEL_USER_ID_KEY)
    if not owner:
        raise HTTPException(401, 'Sign in to your channel to manage access.')
    return str(owner)


async def moderator_id(request, db):
    actor = viewer_user_id(request)
    if not actor or not await valid_viewer_session(db, actor, request.session.get(VIEWER_SERVER_TOKEN_KEY)):
        raise HTTPException(401, 'Sign in through My account to continue.')
    return actor


async def mod_bar_channels(request):
    db = get_db()
    actor = viewer_user_id(request)
    if db is None or not actor or not await valid_viewer_session(db, actor, request.session.get(VIEWER_SERVER_TOKEN_KEY)):
        return []
    return await channels_for_user(db, actor)


@router.get('/channel/access')
async def access_page(request: Request):
    if not request.session.get(CHANNEL_USER_ID_KEY):
        return RedirectResponse('/connect', status_code=303, headers=PRIVATE)
    return templates.TemplateResponse(request=request, name='channel/access.html', context={
        'active_page': 'access', 'csrf_token': get_csrf_token(request),
        'grants': await grants_for_owner(database(), owner_id(request)),
    }, headers=PRIVATE)


async def resolve_access_user(*, login='', user_id=''):
    if login:
        login = login.strip().lower().lstrip('@')
        if not re.fullmatch(r'[a-z0-9_]{1,25}', login):
            raise HTTPException(400, 'Enter a valid Twitch username.', headers=PRIVATE)
        lookup = {'logins': [login]}
    else:
        if not re.fullmatch(r'[0-9]{1,32}', user_id):
            raise HTTPException(400, 'Search for a Twitch user first.', headers=PRIVATE)
        lookup = {'ids': [user_id]}
    bot = get_bot()
    if bot is None:
        raise HTTPException(503, 'Twitch lookup is temporarily unavailable.', headers=PRIVATE)
    try:
        users = await asyncio.wait_for(bot.fetch_users(**lookup), timeout=10)
    except Exception as error:
        raise HTTPException(503, 'Could not verify this Twitch user. Try again shortly.', headers=PRIVATE) from error
    if not users:
        raise HTTPException(404, 'Twitch user not found.', headers=PRIVATE)
    return users[0]


@router.get('/channel/access/search')
async def search_access_user(request: Request, query: str = Query(..., min_length=1, max_length=26)):
    owner = owner_id(request)
    user = await resolve_access_user(login=query)
    grants = await grants_for_owner(database(), owner)
    permission = next((grant['permission'] for grant in grants if grant['user_id'] == str(user.id)), None)
    return JSONResponse({'user': {'id': str(user.id), 'display_name': user.display_name,
        'permission': permission, 'is_owner': str(user.id) == owner}}, headers=PRIVATE)


@router.post('/channel/access')
async def change_access(request: Request, csrf_token: str = Form(...), login: str = Form('', max_length=25),
                        permission: str = Form(...), user_id: str = Form('', max_length=32)):
    owner = owner_id(request)
    validate_csrf_token(request, csrf_token)
    db = database()
    if permission not in ('view', 'edit', 'super', 'revoke'):
        raise HTTPException(400, 'Choose View, Moderator, or Super moderator.')
    name = ''
    if permission == 'revoke':
        if not user_id.isdecimal():
            raise HTTPException(400, 'Invalid user.')
    else:
        user = await resolve_access_user(login=login, user_id=user_id)
        user_id, name = str(user.id), user.display_name
    if owner == user_id:
        raise HTTPException(400, 'You already own this channel.')
    await set_grant(db, owner, user_id, request.session.get(CHANNEL_USER_DISPLAY_NAME_KEY, owner), name, permission)
    return RedirectResponse('/channel/access', status_code=303, headers=PRIVATE)


@router.get('/me/mod/{channel}/notes')
async def mod_page(request: Request, channel: str, offset: int = Query(0, ge=0, le=1000000)):
    db = database()
    if not viewer_user_id(request):
        return RedirectResponse('/me/connect', status_code=303, headers=PRIVATE)
    actor = await moderator_id(request, db)
    try:
        grant, notes, more = await delegated_notes(db, channel, actor, offset)
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    from web.viewer.dashboard import authorize
    await authorize(request, channel)
    return templates.TemplateResponse(request=request, name='viewer/mod_dashboard.html', context={
        'active_page': 'notes',
        'grant': grant, 'notes': notes, 'more': more, 'offset': offset,
        'mod_channels': await channels_for_user(db, actor), 'csrf_token': get_csrf_token(request),
    }, headers=PRIVATE)


@router.post('/me/mod/{channel}/notes/{identity}')
async def save_note(request: Request, channel: str, identity: str, csrf_token: str = Form(...),
                    revision: int = Form(..., ge=0), title: str = Form('', max_length=120), notes: str = Form('', max_length=20000)):
    db = database()
    actor = await moderator_id(request, db)
    validate_csrf_token(request, csrf_token)
    try:
        await save_delegated_note(db, channel, actor, identity, revision, title, notes)
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except ValueError as error:
        # Preserve submitted text when another editor won the revision race.
        return templates.TemplateResponse(request=request, name='viewer/mod_conflict.html', context={
            'channel': channel, 'title': title, 'notes': notes, 'message': str(error),
        }, status_code=409, headers=PRIVATE)
    return RedirectResponse(f'/me/mod/{channel}/notes', status_code=303, headers=PRIVATE)
