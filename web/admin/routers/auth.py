from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from storage.admin_repository import set_administrator_password
from web.admin.auth import authenticate_administrator, get_current_administrator, is_admin_authenticated, logout_admin, require_admin, validate_csrf_token
from web.shared.common import build_admin_context, templates
from web.shared.passwords import hash_password, verify_password
from web.state import get_db


router = APIRouter()
MINIMUM_PASSWORD_LENGTH = 12


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    if await is_admin_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={"error": error}
    )


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    administrator = await authenticate_administrator(request, username, password)

    if administrator is None:
        return RedirectResponse(url="/admin/login?error=invalid_credentials", status_code=303)

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/account/password", response_class=HTMLResponse)
async def change_password_page(request: Request, result: str | None = None):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    return templates.TemplateResponse(
        request=request,
        name="admin/change_password.html",
        context=build_admin_context(
            request,
            active_page="account",
            result=result
        )
    )


@router.post("/account/password")
async def change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...), csrf_token: str = Form(...)):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    validate_csrf_token(request, csrf_token)

    administrator = await get_current_administrator(request)
    db = get_db()

    if administrator is None or db is None:
        return RedirectResponse(url="/admin/account/password?result=runtime_unavailable", status_code=303)

    if not verify_password(administrator.password_hash, current_password):
        return RedirectResponse(url="/admin/account/password?result=incorrect_password", status_code=303)

    if new_password != confirm_password:
        return RedirectResponse(url="/admin/account/password?result=password_mismatch", status_code=303)

    if len(new_password) < MINIMUM_PASSWORD_LENGTH:
        return RedirectResponse(url="/admin/account/password?result=password_too_short", status_code=303)

    if verify_password(administrator.password_hash, new_password):
        return RedirectResponse(url="/admin/account/password?result=same_password", status_code=303)

    password_hash = hash_password(new_password)
    await set_administrator_password(db, administrator.id, password_hash)

    return RedirectResponse(url="/admin/account/password?result=changed", status_code=303)


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    if not await is_admin_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=303)

    validate_csrf_token(request, csrf_token)
    logout_admin(request)

    return RedirectResponse(url="/admin/login", status_code=303)
