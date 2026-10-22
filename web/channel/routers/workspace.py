"""Authenticated personal dashboard tools, scoped only by the signed-in channel."""
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from storage.streamer_workspace import get_workspace, update_workspace
from web.admin.auth import validate_csrf_token, get_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.state import get_db, get_bot
from web.shared.common import templates
from storage.for_you import notes_page, quotes_page, change_quote
from bot.services.channels.quotes import QuoteService

router = APIRouter()


def workspace_context(request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        raise HTTPException(status_code=401, detail="Channel authentication required.")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable. Please try again shortly.")
    return db, str(broadcaster_id)


@router.get("/channel/api/for-you")
async def workspace(request: Request):
    db, broadcaster_id = workspace_context(request)
    return JSONResponse(await get_workspace(db, broadcaster_id, current_note_key(broadcaster_id)), headers={"Cache-Control": "no-store"})


@router.post("/channel/api/for-you")
async def save_workspace(
    request: Request,
    csrf_token: str = Form(...),
    action: str = Form(...),
    notes: str = Form("", max_length=20000),
    revision: int = Form(0, ge=0),
    label: str = Form("", max_length=200),
    minutes: int = Form(0, ge=0, le=10080),
    seconds: int = Form(0, ge=0, le=59),
    timer_id: str = Form("", max_length=32),
):
    db, broadcaster_id = workspace_context(request)
    validate_csrf_token(request, csrf_token)
    if action not in {"notes", "start", "clear"}:
        raise HTTPException(status_code=400, detail="Unknown workspace action.")
    if action == "start" and not 1 <= minutes * 60 + seconds <= 604800:
        raise HTTPException(status_code=400, detail="Set a timer between 1 second and 7 days.")
    try:
        state = await update_workspace(
            db, broadcaster_id, action, notes=notes, revision=revision,
            note_key=current_note_key(broadcaster_id), label=label.strip() or "Timer", minutes=minutes, seconds=seconds, timer_id=timer_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return JSONResponse(state, headers={"Cache-Control": "no-store"})


def current_note_key(channel):
    bot = get_bot()
    services = getattr(bot, 'services', None)
    logs = getattr(services, 'stream_logs', None)
    session = logs.get_active_session(channel) if logs else None
    if session:
        return 'stream:' + str(session.stream_id)
    broadcasters = getattr(services, 'broadcasters', None)
    broadcaster = broadcasters.get_broadcasters().get(channel) if broadcasters else None
    if broadcaster and broadcaster.is_live:
        raise HTTPException(status_code=503, detail="Stream is starting. Please try saving again shortly.")
    return None  # Offline notes are grouped by UTC date.


@router.get('/channel/for-you')
async def for_you_page(request: Request):
    if not request.session.get(CHANNEL_USER_ID_KEY):
        return RedirectResponse('/connect', status_code=303)
    return templates.TemplateResponse(request=request, name='channel/workspace.html', context={
        'active_page': 'for-you', 'csrf_token': get_csrf_token(request),
    }, headers={'Cache-Control': 'no-store'})


@router.get('/channel/api/for-you/notes')
async def archive(request: Request, offset: int = 0):
    db, channel = workspace_context(request)
    return JSONResponse(await notes_page(db, channel, max(0, offset)), headers={'Cache-Control': 'no-store'})


@router.get('/channel/api/for-you/quotes')
async def quotes(request: Request, search: str = '', offset: int = 0):
    db, channel = workspace_context(request)
    return JSONResponse(await quotes_page(db, channel, search[:500], max(0, offset)), headers={'Cache-Control': 'no-store'})


@router.post('/channel/api/for-you/quotes')
async def save_quote(request: Request, csrf_token: str = Form(...), action: str = Form(...),
                     identity: str = Form('', max_length=32), original: str = Form('', max_length=500),
                     message: str = Form('', max_length=350)):
    db, channel = workspace_context(request)
    validate_csrf_token(request, csrf_token)
    if action not in ('add', 'edit', 'delete'):
        raise HTTPException(status_code=400, detail='Unknown quote action.')
    message = message.strip()
    if action != 'delete' and not message:
        raise HTTPException(status_code=400, detail='Enter a quote first.')
    try:
        if action == 'add':
            await QuoteService(db).add(channel, message, 'streamer:' + channel)
        else:
            await change_quote(db, channel, identity, original, message if action == 'edit' else None)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return JSONResponse({'saved': True}, headers={'Cache-Control': 'no-store'})
