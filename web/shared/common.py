from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config.version import APP_VERSION, get_deployment_stamp
from web.shared.markdown import render_markdown
from web.admin.auth import get_csrf_token, is_admin_authenticated

WEB_DIRECTORY = Path(__file__).resolve().parents[1]
TEMPLATES_DIRECTORY = WEB_DIRECTORY / "templates"

def channel_presentation(request):
    access = getattr(request.state, 'channel_access', None)
    return {
        'moderator_mode': bool(access),
        'channel_root': f"/me/mod/{access['broadcaster_id']}" if access else '/channel',
        'can_moderate': not access or access['permission'] in ('edit', 'super'),
        'can_customize': not access or access['permission'] == 'super',
        'moderator_channels': getattr(request.state, 'moderator_channels', []),
        'moderator_auth_required': getattr(request.state, 'moderator_auth_required', True),
        'moderator_name': request.session.get('viewer_user_display_name', 'your Twitch account'),
    }


templates = Jinja2Templates(directory=str(TEMPLATES_DIRECTORY), context_processors=[channel_presentation])
templates.env.globals["deployment_stamp"] = get_deployment_stamp
templates.env.globals["app_version"] = APP_VERSION
templates.env.globals.update(channel_root="/channel", moderator_mode=False, can_moderate=True, can_customize=True)
templates.env.filters["markdown"] = render_markdown


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
        name="admin/error.html",
        context=context,
        status_code=status_code
    )
