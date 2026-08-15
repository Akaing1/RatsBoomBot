from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web.admin.auth import require_admin
from web.shared.common import build_admin_context, templates
from web.state import get_bot, get_db

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    runtime_bot = get_bot()
    runtime_db = get_db()
    bot_running = runtime_bot is not None
    database_connected = runtime_db is not None
    bot_account_id = None
    broadcasters = []

    if runtime_bot is not None:
        bot_account_id = runtime_bot.bot_id
        services = runtime_bot.services

        if services is not None:
            broadcasters = list(services.broadcasters.get_broadcasters().values())

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            bot_running=bot_running,
            database_connected=database_connected,
            bot_account_id=bot_account_id,
            broadcasters=broadcasters,
            broadcaster_count=len(broadcasters)
        )
    )
