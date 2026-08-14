from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from web.admin_auth import is_admin_authenticated, require_admin
from web.common import build_admin_context, templates
from web.system_metrics import system_metrics

router = APIRouter(prefix="/performance")


@router.get("", response_class=HTMLResponse)
async def performance_page(request: Request):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    return templates.TemplateResponse(
        request=request,
        name="performance.html",
        context=build_admin_context(request, active_page="performance")
    )


@router.get("/data")
async def performance_data(request: Request):
    if not await is_admin_authenticated(request):
        raise HTTPException(status_code=401, detail="Administrator authentication required.")

    return system_metrics.collect()
