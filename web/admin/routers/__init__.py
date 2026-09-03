from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web.admin.routers.administrators import router as administrators_router
from web.admin.routers.auth import router as auth_router
from web.admin.routers.channels import router as channels_router
from web.admin.routers.dashboard import dashboard, router as dashboard_router
from web.admin.routers.logs import router as logs_router
from web.admin.routers.oauth import router as oauth_router
from web.admin.routers.performance import router as performance_router
from web.admin.routers.runtime_logs import router as runtime_logs_router
from web.admin.routers.patch_notes import router as patch_notes_router

router = APIRouter(prefix="/admin")
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(oauth_router)
router.include_router(channels_router)
router.include_router(logs_router)
router.include_router(performance_router)
router.include_router(runtime_logs_router)
router.include_router(administrators_router)
router.include_router(patch_notes_router)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_without_trailing_slash(request: Request):
    return await dashboard(request)

__all__ = (
    "router",
    "administrators_router",
    "auth_router",
    "channels_router",
    "dashboard_router",
    "logs_router",
    "oauth_router",
    "performance_router",
    "runtime_logs_router"
)
