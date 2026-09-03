import re
import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from config.version import APP_VERSION
from config.settings import settings
from storage.patch_notes_repository import get_note
from storage.patch_notes_repository import list_notes, save_note, publish_note
from web.admin.auth import require_admin, validate_csrf_token
from web.shared.common import build_admin_context, templates
from web.state import get_db

router=APIRouter(prefix="/patch-notes")
@router.get("",response_class=HTMLResponse)
async def page(request:Request):
    if r:=await require_admin(request): return r
    db=get_db(); return templates.TemplateResponse(request=request,name="admin/patch_notes.html",context=build_admin_context(request,active_page="patch_notes",notes=await list_notes(db) if db else []))
@router.post("/save")
async def save(request:Request,csrf_token:str=Form(),title:str=Form(),synopsis:str=Form(),body:str=Form()):
    if r:=await require_admin(request): return r
    validate_csrf_token(request,csrf_token); slug=re.sub(r"[^a-z0-9]+","-",title.lower()).strip("-"); await save_note(get_db(),slug,title.strip(),synopsis.strip(),body.strip()); return RedirectResponse("/admin/patch-notes",303)
@router.post("/{slug}/publish")
async def publish(request:Request,slug:str,csrf_token:str=Form()):
    if r:=await require_admin(request): return r
    validate_csrf_token(request,csrf_token); db=get_db(); note=await get_note(db,slug); await publish_note(db,slug,APP_VERSION)
    if settings.DISCORD_PATCH_NOTES_WEBHOOK_URL and note:
        url=f"{settings.PUBLIC_BASE_URL.rstrip('/')}/patch-notes/{slug}"
        async with httpx.AsyncClient() as client: await client.post(settings.DISCORD_PATCH_NOTES_WEBHOOK_URL,json={"username":"RatsBoomBot","content":f"**{note['title']}**\n{note['synopsis']}\n\nRead the complete patch notes: <{url}>"},timeout=10)
    return RedirectResponse("/admin/patch-notes",303)
