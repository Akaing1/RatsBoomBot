from web.admin.routers.administrators import router as administrators_router
from web.admin.routers.auth import router as auth_router
from web.admin.routers.channels import router as channels_router
from web.admin.routers.dashboard import router as dashboard_router
from web.admin.routers.logs import router as logs_router
from web.admin.routers.oauth import router as oauth_router
from web.admin.routers.performance import router as performance_router
from web.admin.routers.runtime_logs import router as runtime_logs_router

__all__ = (
    "administrators_router",
    "auth_router",
    "channels_router",
    "dashboard_router",
    "logs_router",
    "oauth_router",
    "performance_router",
    "runtime_logs_router"
)
