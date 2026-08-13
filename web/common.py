from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config.version import get_deployment_stamp
from web.admin_auth import get_csrf_token, is_admin_authenticated

WEB_DIRECTORY = Path(__file__).resolve().parent
TEMPLATES_DIRECTORY = WEB_DIRECTORY / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIRECTORY))
templates.env.globals["deployment_stamp"] = get_deployment_stamp


def build_admin_context(request: Request, *, active_page: str, **values: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "active_page": active_page,
        "csrf_token": get_csrf_token(request),
        "administrator": getattr(request.state, "administrator", None)
    }

    context.update(values)

    return context


async def render_error(request: Request, *, title: str, message: str, status_code: int, active_page: str = "dashboard") -> HTMLResponse:
    context: dict[str, Any] = {
        "active_page": active_page,
        "title": title,
        "message": message
    }

    if await is_admin_authenticated(request):
        context["csrf_token"] = get_csrf_token(request)

    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context=context,
        status_code=status_code
    )
