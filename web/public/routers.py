from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from config.settings import settings
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.shared.common import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request):
    is_authenticated = bool(request.session.get(CHANNEL_USER_ID_KEY))
    destination = "/channel" if is_authenticated else "/connect/twitch"
    dashboard_url = f"{settings.DASHBOARD_BASE_URL.rstrip('/')}{destination}"

    return templates.TemplateResponse(
        request=request,
        name="public/home.html",
        context={
            "dashboard_url": dashboard_url,
            "is_authenticated": is_authenticated,
            "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/")
        }
    )
