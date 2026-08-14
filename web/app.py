from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config.settings import settings
from config.version import APP_NAME, APP_VERSION
from web.routers import admin_users_router, auth_router, channel_user_router, channels_router, dashboard_router, health_router, logs_router, oauth_router, performance_router, runtime_logs_router
WEB_DIRECTORY = Path(__file__).resolve().parent
STATIC_DIRECTORY = WEB_DIRECTORY / "static"


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

    application.include_router(auth_router)
    application.include_router(dashboard_router)
    application.include_router(oauth_router)
    application.include_router(channels_router)
    application.include_router(channel_user_router)
    application.include_router(logs_router)
    application.include_router(performance_router)
    application.include_router(runtime_logs_router)
    application.include_router(health_router)
    application.include_router(admin_users_router)

    return application


app = create_app()
