"""Authenticated personal dashboard tools, scoped only by the signed-in channel."""
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse

from storage.streamer_workspace import get_workspace, update_workspace
from web.admin.auth import validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.state import get_db

router = APIRouter(prefix="/channel/api/for-you")


def workspace_context(request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        raise HTTPException(status_code=401, detail="Channel authentication required.")
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable. Please try again shortly.")
    return db, str(broadcaster_id)


@router.get("")
async def workspace(request: Request):
    db, broadcaster_id = workspace_context(request)
    return JSONResponse(await get_workspace(db, broadcaster_id), headers={"Cache-Control": "no-store"})


@router.post("")
async def save_workspace(
    request: Request,
    csrf_token: str = Form(...),
    action: str = Form(...),
    notes: str = Form("", max_length=20000),
    revision: int = Form(0, ge=0),
    label: str = Form("", max_length=200),
    minutes: int = Form(0, ge=0, le=10080),
    timer_id: str = Form("", max_length=32),
):
    db, broadcaster_id = workspace_context(request)
    validate_csrf_token(request, csrf_token)
    if action not in {"notes", "start", "clear"}:
        raise HTTPException(status_code=400, detail="Unknown workspace action.")
    if action == "start" and (minutes < 1 or not label.strip()):
        raise HTTPException(status_code=400, detail="Enter a reminder and a duration from 1 minute to 7 days.")
    try:
        state = await update_workspace(
            db, broadcaster_id, action, notes=notes, revision=revision,
            label=label.strip(), minutes=minutes, timer_id=timer_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return JSONResponse(state, headers={"Cache-Control": "no-store"})
