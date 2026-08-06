from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.admin_auth import authenticate_admin, is_admin_authenticated, logout_admin, validate_csrf_token
from web.common import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    if is_admin_authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )


@router.post("/login")
async def login(request: Request, admin_secret: str = Form(...)):
    if not authenticate_admin(request, admin_secret):
        return RedirectResponse(url="/login?error=invalid_credentials", status_code=303)

    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    validate_csrf_token(request, csrf_token)
    logout_admin(request)

    return RedirectResponse(url="/login", status_code=303)
