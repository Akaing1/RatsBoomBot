from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config.settings import settings
from storage.database import save_token, delete_token
from web.admin_auth import (
    authenticate_admin,
    get_csrf_token,
    is_admin_authenticated,
    logout_admin,
    require_admin,
    validate_csrf_token
)
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

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie="ratsboombot_admin",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=False
)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIRECTORY)),
    name="static"
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIRECTORY)
)


def get_logs_directory() -> Path:
    logs_directory = Path(settings.STREAM_LOGS_PATH).resolve()
    logs_directory.mkdir(parents=True, exist_ok=True)
    return logs_directory


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"

    return f"{size_bytes / (1024 * 1024):.1f} MB"


def parse_session_directory_name(directory_name: str) -> tuple[str, str]:
    marker = "_stream-"

    if marker not in directory_name:
        return directory_name, "Unknown"

    timestamp_value, stream_id = directory_name.rsplit(marker, 1)

    try:
        started_at = datetime.strptime(
            timestamp_value,
            "%Y-%m-%d_%H%M%S"
        ).strftime("%B %d, %Y at %I:%M:%S %p")
    except ValueError:
        started_at = timestamp_value

    return started_at, stream_id


def resolve_log_file(channel_name: str, session_name: str) -> Path | None:
    logs_directory = get_logs_directory()

    requested_file = (
            logs_directory
            / channel_name
            / session_name
            / "log.txt"
    ).resolve()

    try:
        requested_file.relative_to(logs_directory)
    except ValueError:
        return None

    if not requested_file.is_file():
        return None

    return requested_file


def render_error(
        request: Request,
        *,
        title: str,
        message: str,
        status_code: int,
        active_page: str = "dashboard"
):
    context = {
        "active_page": active_page,
        "title": title,
        "message": message
    }

    if is_admin_authenticated(request):
        context["csrf_token"] = get_csrf_token(request)

    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context=context,
        status_code=status_code
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    if is_admin_authenticated(request):
        return RedirectResponse(
            url="/",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": error
        }
    )


@app.post("/login")
async def login(request: Request, admin_secret: str = Form(...)):
    if not authenticate_admin(request, admin_secret):
        return RedirectResponse(
            url="/login?error=invalid_credentials",
            status_code=303
        )

    return RedirectResponse(
        url="/",
        status_code=303
    )


@app.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    if not is_admin_authenticated(request):
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    validate_csrf_token(
        request,
        csrf_token
    )

    logout_admin(request)

    return RedirectResponse(
        url="/login",
        status_code=303
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

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
                runtime_bot.services
                .broadcasters
                .get_broadcasters()
            )

            broadcasters = list(
                broadcaster_records.values()
            )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "csrf_token": get_csrf_token(request),
            "bot_running": bot_running,
            "database_connected": database_connected,
            "bot_account_id": bot_account_id,
            "broadcasters": broadcasters,
            "broadcaster_count": len(broadcasters)
        }
    )


@app.get("/connect/channel")
async def connect_channel(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    return RedirectResponse(
        build_channel_oauth_url()
    )


@app.get("/connect/bot")
async def connect_bot(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    return RedirectResponse(
        build_bot_oauth_url()
    )


@app.get("/oauth/channel", response_class=HTMLResponse)
async def oauth_channel_callback(
        request: Request,
        code: str | None = None,
        error: str | None = None
):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

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
            "csrf_token": get_csrf_token(request),
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
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

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
            title="Bot connection failed",
            message=repr(exc),
            status_code=500
        )

    return templates.TemplateResponse(
        request=request,
        name="auth_success.html",
        context={
            "active_page": "dashboard",
            "csrf_token": get_csrf_token(request),
            "title": "Bot account connected",
            "message": (
                f"The bot account {twitch_user.display_name} "
                f"was connected successfully."
            )
        }
    )


@app.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

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
            "csrf_token": get_csrf_token(request),
            "broadcasters": broadcasters,
            "broadcaster_count": len(broadcasters)
        }
    )


@app.get("/channels/{broadcaster_id}", response_class=HTMLResponse)
async def channel_details_page(
        request: Request,
        broadcaster_id: str
):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

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

    channel_settings = await (
        runtime_bot.services
        .broadcaster_settings
        .get_settings(broadcaster_id)
    )

    viewer_queue = runtime_bot.services.viewer_queue

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
            "csrf_token": get_csrf_token(request),
            "broadcaster": broadcaster,
            "channel_settings": channel_settings,
            "queue_open": queue_open,
            "queue_users": queue_users,
            "queue_size": queue_size
        }
    )


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    logs_directory = get_logs_directory()
    runtime_bot = get_bot()
    active_log_paths: set[Path] = set()

    if runtime_bot is not None and runtime_bot.services is not None:
        for session in (
                runtime_bot.services
                        .stream_logs
                        .active_sessions
                        .values()
        ):
            active_log_paths.add(session.log_path.resolve())

    log_sessions = []

    for channel_directory in logs_directory.iterdir():
        if not channel_directory.is_dir():
            continue

        for session_directory in channel_directory.iterdir():
            if not session_directory.is_dir():
                continue

            log_file = session_directory / "log.txt"

            if not log_file.is_file():
                continue

            started_at, stream_id = parse_session_directory_name(
                session_directory.name
            )

            file_stats = log_file.stat()

            log_sessions.append({
                "channel_name": channel_directory.name,
                "session_name": session_directory.name,
                "started_at": started_at,
                "stream_id": stream_id,
                "file_size": format_file_size(file_stats.st_size),
                "modified_timestamp": file_stats.st_mtime,
                "is_active": log_file.resolve() in active_log_paths
            })

    log_sessions.sort(
        key=lambda session: session["modified_timestamp"],
        reverse=True
    )

    return templates.TemplateResponse(
        request=request,
        name="logs.html",
        context={
            "active_page": "logs",
            "csrf_token": get_csrf_token(request),
            "log_sessions": log_sessions,
            "log_count": len(log_sessions)
        }
    )


@app.get(
    "/logs/{channel_name}/{session_name}",
    response_class=HTMLResponse
)
async def log_details_page(
        request: Request,
        channel_name: str,
        session_name: str
):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    log_file = resolve_log_file(
        channel_name,
        session_name
    )

    if log_file is None:
        return render_error(
            request,
            active_page="logs",
            title="Log not found",
            message="That stream log does not exist.",
            status_code=404
        )

    try:
        log_content = log_file.read_text(
            encoding="utf-8",
            errors="replace"
        )
    except OSError as error:
        return render_error(
            request,
            active_page="logs",
            title="Could not read log",
            message=repr(error),
            status_code=500
        )

    started_at, stream_id = parse_session_directory_name(
        session_name
    )

    runtime_bot = get_bot()
    is_active = False

    if runtime_bot is not None and runtime_bot.services is not None:
        is_active = any(
            session.log_path.resolve() == log_file.resolve()
            for session in (
                runtime_bot.services
                .stream_logs
                .active_sessions
                .values()
            )
        )

    return templates.TemplateResponse(
        request=request,
        name="log_details.html",
        context={
            "active_page": "logs",
            "csrf_token": get_csrf_token(request),
            "channel_name": channel_name,
            "session_name": session_name,
            "started_at": started_at,
            "stream_id": stream_id,
            "file_size": format_file_size(log_file.stat().st_size),
            "is_active": is_active,
            "log_content": log_content
        }
    )


@app.get("/logs/{channel_name}/{session_name}/download")
async def download_log(request: Request, channel_name: str, session_name: str):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    log_file = resolve_log_file(
        channel_name,
        session_name
    )

    if log_file is None:
        return render_error(
            request,
            active_page="logs",
            title="Log not found",
            message="That stream log does not exist.",
            status_code=404
        )

    download_name = (
        f"{channel_name}_{session_name}_log.txt"
    )

    return FileResponse(
        path=log_file,
        media_type="text/plain",
        filename=download_name
    )


@app.post("/channels/{broadcaster_id}/delete")
async def delete_broadcaster(request: Request, broadcaster_id: str, csrf_token: str = Form(...)):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    validate_csrf_token(request, csrf_token)

    if broadcaster_id == settings.BOT_ID:
        return render_error(
            request,
            active_page="channels",
            title="Cannot remove bot account",
            message="The bot account cannot be removed as a broadcaster.",
            status_code=400
        )

    runtime_bot = get_bot()
    runtime_db = get_db()

    if runtime_bot is None or runtime_bot.services is None or runtime_db is None:
        return render_error(
            request,
            active_page="channels",
            title="Runtime unavailable",
            message="The RatsBoomBot runtime is not available.",
            status_code=503
        )

    broadcaster = (
        runtime_bot.services
        .broadcasters
        .get_broadcasters()
        .get(broadcaster_id)
    )

    if broadcaster is None:
        return render_error(
            request,
            active_page="channels",
            title="Channel not found",
            message="That channel is not connected to RatsBoomBot.",
            status_code=404
        )

    await delete_token(runtime_db, broadcaster_id)

    runtime_bot.services.broadcasters.remove_broadcaster(
        broadcaster_id
    )

    runtime_bot.services.viewer_queue.remove_queue(
        broadcaster_id
    )

    return RedirectResponse(
        url="/channels?removed=1",
        status_code=303
    )
