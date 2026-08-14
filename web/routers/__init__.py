from web.routers.auth import router as auth_router
from web.routers.channels import router as channels_router
from web.routers.dashboard import router as dashboard_router
from web.routers.health import router as health_router
from web.routers.logs import router as logs_router
from web.routers.performance import router as performance_router
from web.routers.runtime_logs import router as runtime_logs_router
from web.routers.oauth import router as oauth_router
from web.routers.admin_users import router as admin_users_router
from web.routers.channel_user import router as channel_user_router

__all__ = [
    "auth_router",
    "channels_router",
    "dashboard_router",
    "health_router",
    "logs_router",
    "performance_router",
    "runtime_logs_router",
    "oauth_router",
    "admin_users_router",
    "channel_user_router"
]