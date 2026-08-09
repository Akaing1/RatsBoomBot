from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.admin_auth import authenticate_administrator, is_admin_authenticated, logout_admin, validate_csrf_token
from web.common import templates


router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    if await is_admin_authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    administrator = await authenticate_administrator(request, username, password)

    if administrator is None:
        return RedirectResponse(url="/login?error=invalid_credentials", status_code=303)

    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    if not await is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    validate_csrf_token(request, csrf_token)
    logout_admin(request)

    return RedirectResponse(url="/login", status_code=303)
