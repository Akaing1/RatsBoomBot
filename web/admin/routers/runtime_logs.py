from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.runtime_logs import runtime_log_buffer
from web.admin.auth import is_admin_authenticated, require_admin
from web.shared.common import build_admin_context, templates

router = APIRouter(prefix="/runtime-logs")


@router.get("", response_class=HTMLResponse)
async def runtime_logs_page(request: Request):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    return templates.TemplateResponse(
        request=request,
        name="admin/runtime_logs.html",
        context=build_admin_context(request, active_page="runtime_logs")
    )


@router.get("/data")
async def runtime_logs_data(request: Request, after: int = Query(default=0, ge=0), limit: int = Query(default=500, ge=1, le=1000)):
    if not await is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Administrator authentication required.")

    return {"entries": runtime_log_buffer.get_entries(after_id=after, limit=limit)}
