from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from bot.services.support.moderation_shadow import ModerationShadow
from web.admin.auth import require_admin
from web.shared.common import build_admin_context, templates
from web.state import get_db

router = APIRouter(prefix='/bot-detection')


@router.get('', response_class=HTMLResponse)
async def bot_detection(request: Request):
    redirect = await require_admin(request)
    if redirect:
        return redirect
    data = await ModerationShadow(get_db()).dashboard()
    return templates.TemplateResponse(request=request, name='admin/bot_detection.html',
        context=build_admin_context(request, active_page='bot_detection', **data))
