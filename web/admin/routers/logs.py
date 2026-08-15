from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse

from web.admin.auth import require_admin
from web.shared.common import build_admin_context, render_error, templates
from web.shared.log_browser import format_file_size, get_logs_directory, parse_session_directory_name, resolve_log_file
from web.state import get_bot

router = APIRouter(prefix="/logs")


def get_active_log_paths() -> set[Path]:
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return set()

    active_log_paths: set[Path] = set()

    for session in runtime_bot.services.stream_logs.active_sessions.values():
        active_log_paths.add(session.log_path.resolve())

    return active_log_paths


@router.get("", response_class=HTMLResponse)
async def logs_page(request: Request):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    logs_directory = get_logs_directory()
    active_log_paths = get_active_log_paths()
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

            started_at, stream_id = parse_session_directory_name(session_directory.name)
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

    log_sessions.sort(key=lambda session: session["modified_timestamp"], reverse=True)

    return templates.TemplateResponse(
        request=request,
        name="admin/logs.html",
        context=build_admin_context(
            request,
            active_page="logs",
            log_sessions=log_sessions,
            log_count=len(log_sessions)
        )
    )


@router.get("/{channel_name}/{session_name}", response_class=HTMLResponse)
async def log_details_page(request: Request, channel_name: str, session_name: str):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    log_file = resolve_log_file(channel_name, session_name)

    if log_file is None:
        return await render_error(
            request,
            active_page="logs",
            title="Log not found",
            message="That stream log does not exist.",
            status_code=404
        )

    try:
        log_content = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return await render_error(
            request,
            active_page="logs",
            title="Could not read log",
            message=repr(error),
            status_code=500
        )

    started_at, stream_id = parse_session_directory_name(session_name)
    is_active = log_file.resolve() in get_active_log_paths()

    return templates.TemplateResponse(
        request=request,
        name="admin/log_details.html",
        context=build_admin_context(
            request,
            active_page="logs",
            channel_name=channel_name,
            session_name=session_name,
            started_at=started_at,
            stream_id=stream_id,
            file_size=format_file_size(log_file.stat().st_size),
            is_active=is_active,
            log_content=log_content
        )
    )


@router.get("/{channel_name}/{session_name}/download")
async def download_log(request: Request, channel_name: str, session_name: str):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    log_file = resolve_log_file(channel_name, session_name)

    if log_file is None:
        return await render_error(
            request,
            active_page="logs",
            title="Log not found",
            message="That stream log does not exist.",
            status_code=404
        )

    download_name = f"{channel_name}_{session_name}_log.txt"

    return FileResponse(path=log_file, media_type="text/plain", filename=download_name)