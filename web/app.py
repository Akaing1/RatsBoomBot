from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config.settings import settings
from config.version import APP_NAME, APP_VERSION
from web.admin.routers import (
    administrators_router,
    auth_router as admin_auth_router,
    channels_router,
    dashboard_router as admin_dashboard_router,
    logs_router,
    oauth_router as admin_oauth_router,
    performance_router,
    runtime_logs_router
)
from web.channel.routers import dashboard_router as channel_dashboard_router
from web.channel.routers import oauth_router as channel_oauth_router
from web.shared.routers import health_router
WEB_DIRECTORY = Path(__file__).resolve().parent
STATIC_DIRECTORY = WEB_DIRECTORY / "static"
ASSETS_DIRECTORY = WEB_DIRECTORY.parent / "assets"


def create_app() -> FastAPI:
    application = FastAPI(title=f"{APP_NAME} Admin", version=APP_VERSION, docs_url=None, redoc_url=None)

    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET,
        session_cookie="ratsboombot_admin",
        max_age=60 * 60 * 8,
        same_site="lax",
        https_only=settings.SESSION_HTTPS_ONLY
    )

    application.mount("/static", StaticFiles(directory=str(STATIC_DIRECTORY)), name="static")
    application.mount("/assets", StaticFiles(directory=str(ASSETS_DIRECTORY)), name="assets")

    application.include_router(admin_auth_router)
    application.include_router(admin_dashboard_router)
    application.include_router(admin_oauth_router)
    application.include_router(channels_router)
    application.include_router(channel_dashboard_router)
    application.include_router(channel_oauth_router)
    application.include_router(logs_router)
    application.include_router(performance_router)
    application.include_router(runtime_logs_router)
    application.include_router(health_router)
    application.include_router(administrators_router)

    return application


app = create_app()
