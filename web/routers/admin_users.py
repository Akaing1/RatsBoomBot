from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from storage.admin_repository import create_administrator, get_administrator_by_username, list_administrators, set_administrator_enabled, get_administrator_by_id, set_administrator_password
from web.admin_auth import require_owner, validate_csrf_token
from web.common import build_admin_context, templates
from web.passwords import hash_password
from web.state import get_db


router = APIRouter(prefix="/admin/users")

MINIMUM_PASSWORD_LENGTH = 12


@router.get("", response_class=HTMLResponse)
async def admin_users_page(request: Request, result: str | None = None):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    db = get_db()

    if db is None:
        return RedirectResponse(url="/", status_code=303)

    administrators = await list_administrators(db)

    return templates.TemplateResponse(
        request=request,
        name="admin_users.html",
        context=build_admin_context(
            request,
            active_page="users",
            administrators=administrators,
            result=result
        )
    )


@router.post("")
async def create_admin_user(request: Request, username: str = Form(...), password: str = Form(...), confirm_password: str = Form(...), csrf_token: str = Form(...)):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    validate_csrf_token(request, csrf_token)

    db = get_db()

    if db is None:
        return RedirectResponse(url="/admin/users?result=runtime_unavailable", status_code=303)

    username = username.strip().lower()

    if not username:
        return RedirectResponse(url="/admin/users?result=invalid_username", status_code=303)

    if password != confirm_password:
        return RedirectResponse(url="/admin/users?result=password_mismatch", status_code=303)

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        return RedirectResponse(url="/admin/users?result=password_too_short", status_code=303)

    existing_administrator = await get_administrator_by_username(db, username)

    if existing_administrator is not None:
        return RedirectResponse(url="/admin/users?result=username_exists", status_code=303)

    password_hash = hash_password(password)
    await create_administrator(db, username, password_hash)

    return RedirectResponse(url="/admin/users?result=created", status_code=303)


@router.post("/{administrator_id}/password")
async def reset_admin_password(request: Request, administrator_id: int, password: str = Form(...), confirm_password: str = Form(...), csrf_token: str = Form(...)):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    validate_csrf_token(request, csrf_token)

    db = get_db()

    if db is None:
        return RedirectResponse(url="/admin/users?result=runtime_unavailable", status_code=303)

    administrator = await get_administrator_by_id(db, administrator_id)

    if administrator is None:
        return RedirectResponse(url="/admin/users?result=user_not_found", status_code=303)

    if administrator.role == "owner":
        return RedirectResponse(url="/admin/users?result=owner_protected", status_code=303)

    if password != confirm_password:
        return RedirectResponse(url="/admin/users?result=password_mismatch", status_code=303)

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        return RedirectResponse(url="/admin/users?result=password_too_short", status_code=303)

    password_hash = hash_password(password)
    await set_administrator_password(db, administrator_id, password_hash)

    return RedirectResponse(url="/admin/users?result=password_reset", status_code=303)


@router.post("/{administrator_id}/enabled")
async def update_admin_enabled(request: Request, administrator_id: int, action: str = Form(...), csrf_token: str = Form(...)):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    validate_csrf_token(request, csrf_token)

    db = get_db()

    if db is None:
        return RedirectResponse(url="/admin/users?result=runtime_unavailable", status_code=303)

    administrator = await get_administrator_by_id(db, administrator_id)

    if administrator is None:
        return RedirectResponse(url="/admin/users?result=user_not_found", status_code=303)

    if administrator.role == "owner":
        return RedirectResponse(url="/admin/users?result=owner_protected", status_code=303)

    if action not in {"enable", "disable"}:
        return RedirectResponse(url="/admin/users?result=invalid_action", status_code=303)

    await set_administrator_enabled(db, administrator_id, action == "enable")

    result = "enabled" if action == "enable" else "disabled"
    return RedirectResponse(url=f"/admin/users?result={result}", status_code=303)
