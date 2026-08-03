from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from urllib.parse import urlencode

from config.settings import settings
from storage.database import delete_token
from web.admin_auth import (
    require_admin,
    validate_csrf_token
)
from web.common import (
    build_admin_context,
    render_error,
    templates
)
from web.state import get_bot, get_db

router = APIRouter(
    prefix="/channels"
)


@router.get("",response_class=HTMLResponse)
async def channels_page(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    runtime_bot = get_bot()
    broadcasters = []

    if runtime_bot is not None and runtime_bot.services:
        broadcaster_service = runtime_bot.services.broadcasters

        await broadcaster_service.refresh_live_statuses()

        broadcaster_records = broadcaster_service.get_broadcasters()

        broadcasters = list(broadcaster_records.values())

    broadcasters.sort(
        key=lambda broadcaster: (
            not broadcaster.is_live,
            (
                    broadcaster.name
                    or broadcaster.id
            ).lower()
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="channels.html",
        context=build_admin_context(
            request,
            active_page="channels",
            broadcasters=broadcasters,
            broadcaster_count=len(broadcasters)
        )
    )


@router.get("/{broadcaster_id}", response_class=HTMLResponse)
async def channel_details_page(request: Request,broadcaster_id: str):
    queue_result = request.query_params.get("queue_result")
    queue_message = request.query_params.get("queue_message")
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

    broadcaster_service = runtime_bot.services.broadcasters
    broadcaster = broadcaster_service.get_broadcasters().get(broadcaster_id)

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

    channel_settings = await runtime_bot.services.broadcaster_settings.get_settings(broadcaster_id)

    viewer_queue = runtime_bot.services.viewer_queue
    queue_open = viewer_queue.is_queue_open(broadcaster_id)
    queue_users = viewer_queue.list_queue(broadcaster_id)
    queue_size = viewer_queue.size(broadcaster_id)

    return templates.TemplateResponse(
        request=request,
        name="channel_details.html",
        context=build_admin_context(
            request,
            active_page="channels",
            broadcaster=broadcaster,
            channel_settings=channel_settings,
            queue_open=queue_open,
            queue_users=queue_users,
            queue_size=queue_size,
            queue_result=queue_result,
            queue_message=queue_message
        )
    )


@router.post("/{broadcaster_id}/delete")
async def delete_broadcaster(request: Request, broadcaster_id: str, csrf_token: str = Form(...)):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    validate_csrf_token(
        request,
        csrf_token
    )

    if str(broadcaster_id) == str(settings.BOT_ID):
        return render_error(
            request,
            active_page="channels",
            title="Cannot remove bot account",
            message=(
                "The bot account cannot be removed "
                "as a broadcaster."
            ),
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

    broadcaster = runtime_bot.services.broadcasters.get_broadcasters().get(broadcaster_id)

    if broadcaster is None:
        return render_error(
            request,
            active_page="channels",
            title="Channel not found",
            message=(
                "That channel is not connected "
                "to RatsBoomBot."
            ),
            status_code=404
        )

    if runtime_bot.services.stream_logs.is_active(broadcaster_id):
        await runtime_bot.services.stream_logs.end_session(
            broadcaster_id
        )

    await delete_token(
        runtime_db,
        broadcaster_id
    )

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


@router.post("/{broadcaster_id}/viewer-queue/remove")
async def remove_viewer_from_queue(
    request: Request,
    broadcaster_id: str,
    position: int = Form(...),
    csrf_token: str = Form(...)
):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    validate_csrf_token(
        request,
        csrf_token
    )

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
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
        .get(str(broadcaster_id))
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

    removed, _, message = (
        runtime_bot.services
        .viewer_queue
        .remove_position(
            broadcaster_id,
            position
        )
    )

    result = "removed" if removed else "remove_failed"

    query = urlencode(
        {
            "queue_result": result,
            "queue_message": message
        }
    )

    return RedirectResponse(
        url=f"/channels/{broadcaster_id}?{query}",
        status_code=303
    )
