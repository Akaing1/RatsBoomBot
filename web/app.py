from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config.settings import settings
from config.version import APP_NAME, APP_VERSION
from web.admin.routers import router as admin_router
from web.channel.routers import dashboard_router as channel_dashboard_router
from web.channel.routers import oauth_router as channel_oauth_router
from web.public.routers import router as public_router
from web.shared.routers import health_router
WEB_DIRECTORY = Path(__file__).resolve().parent
STATIC_DIRECTORY = WEB_DIRECTORY / "static"
ASSETS_DIRECTORY = WEB_DIRECTORY.parent / "assets"


def create_app() -> FastAPI:
    application = FastAPI(title=f"{APP_NAME} Admin", version=APP_VERSION, docs_url=None, redoc_url=None)

    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET,
        session_cookie="ratsboombot_session",
        max_age=max(
            settings.ADMIN_SESSION_MAX_AGE_SECONDS,
            settings.CHANNEL_SESSION_MAX_AGE_SECONDS
        ),
        same_site="lax",
        https_only=settings.SESSION_HTTPS_ONLY,
        domain=settings.SESSION_COOKIE_DOMAIN
    )

    application.mount("/static", StaticFiles(directory=str(STATIC_DIRECTORY)), name="static")
    application.mount("/assets", StaticFiles(directory=str(ASSETS_DIRECTORY)), name="assets")

    application.include_router(admin_router)
    application.include_router(channel_dashboard_router)
    application.include_router(channel_oauth_router)
    application.include_router(public_router)
    application.include_router(health_router)

    return application


app = create_app()
