from web.routers.auth import router as auth_router
from web.routers.channels import router as channels_router
from web.routers.dashboard import router as dashboard_router
from web.routers.logs import router as logs_router
from web.routers.oauth import router as oauth_router

__all__ = [
    "auth_router",
    "channels_router",
    "dashboard_router",
    "logs_router",
    "oauth_router"
]
