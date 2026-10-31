import re
import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from config.version import APP_VERSION
from config.settings import settings
from storage.patch_notes_repository import get_note
from storage.patch_notes_repository import list_notes, create_note, publish_note, update_note, delete_note
from web.admin.auth import require_admin, validate_csrf_token
from web.shared.common import build_admin_context, templates
from web.state import get_db

router=APIRouter(prefix="/patch-notes")
def database():
    db = get_db()
    if db is None:
        raise HTTPException(503, "Patch note storage is unavailable.")
    return db


def fields(title, synopsis, body):
    values = tuple(value.strip() for value in (title, synopsis, body))
    if not all(values):
        raise HTTPException(422, "Title, synopsis and body must not be blank.")
    return values


@router.get("", response_class=HTMLResponse)
async def page(request: Request, edit: str | None = None):
    if redirect := await require_admin(request):
        return redirect
    db = database()
    editing_note = await get_note(db, edit) if edit else None
    if edit and editing_note is None:
        raise HTTPException(404, "Patch note not found.")
    return templates.TemplateResponse(
        request=request, name="admin/patch_notes.html",
        context=build_admin_context(request, active_page="patch_notes",
                                    notes=await list_notes(db), editing_note=editing_note),
    )


@router.post("/save")
async def save(request: Request, csrf_token: str = Form(), title: str = Form(),
               synopsis: str = Form(), body: str = Form()):
    if redirect := await require_admin(request):
        return redirect
    validate_csrf_token(request, csrf_token)
    title, synopsis, body = fields(title, synopsis, body)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        raise HTTPException(422, "Title must include letters or numbers for its URL.")
    db = database()
    if not await create_note(db, slug, title, synopsis, body):
        raise HTTPException(409, "A note with this URL already exists. Use Edit to change it.")
    return RedirectResponse("/admin/patch-notes", 303)


@router.post("/{slug}/edit")
async def edit_note(request: Request, slug: str, csrf_token: str = Form(),
                    title: str = Form(), synopsis: str = Form(), body: str = Form()):
    if redirect := await require_admin(request):
        return redirect
    validate_csrf_token(request, csrf_token)
    values = fields(title, synopsis, body)
    if not await update_note(database(), slug, *values):
        raise HTTPException(404, "Patch note not found.")
    return RedirectResponse("/admin/patch-notes", 303)


@router.post("/{slug}/delete")
async def remove_note(request: Request, slug: str, csrf_token: str = Form()):
    if redirect := await require_admin(request):
        return redirect
    validate_csrf_token(request, csrf_token)
    if not await delete_note(database(), slug):
        raise HTTPException(404, "Patch note not found.")
    return RedirectResponse("/admin/patch-notes", 303)


@router.post("/{slug}/publish")
async def publish(request:Request,slug:str,csrf_token:str=Form()):
    if r:=await require_admin(request): return r
    validate_csrf_token(request,csrf_token); db=get_db(); note=await get_note(db,slug); await publish_note(db,slug,APP_VERSION)
    if settings.DISCORD_PATCH_NOTES_WEBHOOK_URL and note:
        url=f"{settings.PUBLIC_BASE_URL.rstrip('/')}/patch-notes/{slug}"
        async with httpx.AsyncClient() as client: await client.post(settings.DISCORD_PATCH_NOTES_WEBHOOK_URL,json={"username":"RatsBoomBot","content":f"**{note['title']}**\n{note['synopsis']}\n\nRead the complete patch notes: <{url}>"},timeout=10)
    return RedirectResponse("/admin/patch-notes",303)
