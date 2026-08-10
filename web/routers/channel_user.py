from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.channel_auth import CHANNEL_USER_DISPLAY_NAME_KEY, CHANNEL_USER_ID_KEY, CHANNEL_USER_LOGIN_KEY, logout_channel_user
from web.common import templates


router = APIRouter()


@router.get("/channel", response_class=HTMLResponse)
async def channel_dashboard(request: Request):
    user_id = request.session.get(CHANNEL_USER_ID_KEY)
    login = request.session.get(CHANNEL_USER_LOGIN_KEY)
    display_name = request.session.get(CHANNEL_USER_DISPLAY_NAME_KEY)

    if not user_id:
        return RedirectResponse(url="/connect", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="channel_dashboard.html",
        context={
            "user_id": user_id,
            "login": login,
            "display_name": display_name
        }
    )


@router.post("/channel/logout")
async def channel_logout(request: Request):
    logout_channel_user(request)
    return RedirectResponse(url="/connect", status_code=303)
