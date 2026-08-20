from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse

from app.runtime_control import restart_runtime
from web.admin.auth import require_owner, validate_csrf_token
from web.shared.common import build_admin_context, templates

router = APIRouter(prefix="/runtime")


@router.post("/restart", response_class=HTMLResponse)
async def restart_bot(request: Request, background_tasks: BackgroundTasks, csrf_token: str = Form(...)):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    validate_csrf_token(request, csrf_token)
    background_tasks.add_task(restart_runtime)

    return templates.TemplateResponse(
        request=request,
        name="admin/restarting.html",
        context=build_admin_context(request, active_page="dashboard")
    )
