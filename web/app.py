from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.settings import settings
from storage.database import save_token
from web.oauth import (
    build_bot_oauth_url,
    build_channel_oauth_url,
    exchange_code_for_token,
    fetch_twitch_user
)
from web.state import get_bot, get_db

WEB_DIRECTORY = Path(__file__).resolve().parent
TEMPLATES_DIRECTORY = WEB_DIRECTORY / "templates"
STATIC_DIRECTORY = WEB_DIRECTORY / "static"

app = FastAPI(
    title="RatsBoomBot Admin",
    docs_url=None,
    redoc_url=None
)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIRECTORY)),
    name="static"
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIRECTORY)
)


def render_error(
    request: Request,
    *,
    title: str,
    message: str,
    status_code: int,
    active_page: str = "dashboard"
):
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "active_page": active_page,
            "title": title,
            "message": message
        },
        status_code=status_code
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    runtime_bot = get_bot()
    runtime_db = get_db()

    bot_running = runtime_bot is not None
    database_connected = runtime_db is not None
    bot_account_id = None
    broadcasters = []

    if runtime_bot is not None:
        bot_account_id = runtime_bot.bot_id

        if runtime_bot.services:
            broadcaster_records = (
                runtime_bot.services.broadcasters.get_broadcasters()
            )
            broadcasters = list(broadcaster_records.values())

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "bot_running": bot_running,
            "database_connected": database_connected,
            "bot_account_id": bot_account_id,
            "broadcasters": broadcasters,
            "broadcaster_count": len(broadcasters)
        }
    )


@app.get("/connect/channel")
async def connect_channel():
    return RedirectResponse(
        build_channel_oauth_url()
    )


@app.get("/connect/bot")
async def connect_bot():
    return RedirectResponse(
        build_bot_oauth_url()
    )


@app.get("/oauth/channel", response_class=HTMLResponse)
async def oauth_channel_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None
):
    if error:
        return render_error(
            request,
            title="Channel authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        return render_error(
            request,
            title="Channel authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    try:
        token_response = await exchange_code_for_token(
            code=code,
            redirect_uri=settings.CHANNEL_REDIRECT_URI
        )

        twitch_user = await fetch_twitch_user(
            token_response.access_token
        )

        runtime_bot = get_bot()
        runtime_db = get_db()

        if runtime_bot is not None:
            await runtime_bot.onboard_broadcaster(
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )

        elif runtime_db is not None:
            await save_token(
                db=runtime_db,
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )

        else:
            return render_error(
                request,
                title="Runtime unavailable",
                message="The RatsBoomBot runtime is not available.",
                status_code=503
            )

    except Exception as exc:
        return render_error(
            request,
            title="Channel connection failed",
            message=repr(exc),
            status_code=500
        )

    return templates.TemplateResponse(
        request=request,
        name="auth_success.html",
        context={
            "active_page": "dashboard",
            "title": "Channel connected",
            "message": (
                f"RatsBoomBot is now connected to "
                f"{twitch_user.display_name}."
            )
        }
    )


@app.get("/oauth/bot", response_class=HTMLResponse)
async def oauth_bot_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None
):
    if error:
        return render_error(
            request,
            title="Bot authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        return render_error(
            request,
            title="Bot authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    try:
        token_response = await exchange_code_for_token(
            code=code,
            redirect_uri=settings.BOT_REDIRECT_URI
        )

        twitch_user = await fetch_twitch_user(
            token_response.access_token
        )

        runtime_bot = get_bot()
        runtime_db = get_db()

        if runtime_bot is not None:
            await runtime_bot.onboard_bot_account(
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )

        elif runtime_db is not None:
            await save_token(
                db=runtime_db,
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )

        else:
            return render_error(
                request,
                title="Runtime unavailable",
                message="The RatsBoomBot runtime is not available.",
                status_code=503
            )

    except Exception as exc:
        return render_error(
            request,
            title="Bot connection failed",
            message=repr(exc),
            status_code=500
        )

    return templates.TemplateResponse(
        request=request,
        name="auth_success.html",
        context={
            "active_page": "dashboard",
            "title": "Bot account connected",
            "message": (
                f"The bot account {twitch_user.display_name} "
                f"was connected successfully."
            )
        }
    )


@app.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request):
    runtime_bot = get_bot()
    broadcasters = []

    if runtime_bot is not None and runtime_bot.services:
        broadcaster_service = (
            runtime_bot.services.broadcasters
        )

        await broadcaster_service.refresh_live_statuses()

        broadcaster_records = (
            broadcaster_service.get_broadcasters()
        )

        broadcasters = list(
            broadcaster_records.values()
        )

    broadcasters.sort(
        key=lambda broadcaster: (
            not broadcaster.is_live,
            (broadcaster.name or broadcaster.id).lower()
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="channels.html",
        context={
            "active_page": "channels",
            "broadcasters": broadcasters,
            "broadcaster_count": len(broadcasters)
        }
    )


@app.get(
    "/channels/{broadcaster_id}",
    response_class=HTMLResponse
)
async def channel_details_page(
    request: Request,
    broadcaster_id: str
):
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return render_error(
            request,
            active_page="channels",
            title="Runtime unavailable",
            message="The RatsBoomBot runtime is not available.",
            status_code=503
        )

    broadcaster_service = (
        runtime_bot.services.broadcasters
    )

    broadcaster_records = (
        broadcaster_service.get_broadcasters()
    )

    broadcaster = broadcaster_records.get(
        broadcaster_id
    )

    if broadcaster is None:
        return render_error(
            request,
            active_page="channels",
            title="Channel not found",
            message=(
                "That Twitch channel is not connected "
                "to RatsBoomBot."
            ),
            status_code=404
        )

    await broadcaster_service.refresh_live_statuses()

    channel_settings = (
        await runtime_bot.services
        .broadcaster_settings
        .get_settings(broadcaster_id)
    )

    viewer_queue = (
        runtime_bot.services.viewer_queue
    )

    queue_open = viewer_queue.is_queue_open(
        broadcaster_id
    )

    queue_users = viewer_queue.list_queue(
        broadcaster_id
    )

    queue_size = viewer_queue.size(
        broadcaster_id
    )

    return templates.TemplateResponse(
        request=request,
        name="channel_details.html",
        context={
            "active_page": "channels",
            "broadcaster": broadcaster,
            "channel_settings": channel_settings,
            "queue_open": queue_open,
            "queue_users": queue_users,
            "queue_size": queue_size
        }
    )
