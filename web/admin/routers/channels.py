from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName, ProfileFeatureName
from config.settings import settings
from storage.database import delete_token
from web.admin.auth import require_admin, require_owner, validate_csrf_token
from web.shared.common import build_admin_context, render_error, templates
from web.state import get_bot, get_db

router = APIRouter(prefix="/channels")


async def get_runtime_error(request: Request):
    return await render_error(
        request,
        active_page="channels",
        title="Runtime unavailable",
        message="The RatsBoomBot runtime is not available.",
        status_code=503
    )


async def get_channel_error(request: Request):
    return await render_error(
        request,
        active_page="channels",
        title="Channel not found",
        message="That Twitch channel is not connected to RatsBoomBot.",
        status_code=404
    )


def get_broadcaster(runtime_bot, broadcaster_id: str):
    return runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))


def redirect_to_channel(broadcaster_id: str, **query_values) -> RedirectResponse:
    query = urlencode({key: value for key, value in query_values.items() if value is not None})
    url = f"/admin/channels/{broadcaster_id}"

    if query:
        url = f"{url}?{query}"

    return RedirectResponse(url=url, status_code=303)


async def get_redemption_dashboard_data(services, broadcaster_id: str) -> dict[str, object]:
    active_session = services.stream_logs.get_active_session(broadcaster_id)
    stream_id = active_session.stream_id if active_session is not None else None
    using_previous_stream = False

    if stream_id is None:
        stream_id = await services.redeems.get_latest_stream_id(broadcaster_id)
        using_previous_stream = stream_id is not None

    activity = await services.redeems.get_dashboard_activity(
        broadcaster_id=broadcaster_id,
        stream_id=stream_id
    )
    activity["using_previous_stream"] = using_previous_stream

    return activity


@router.get("", response_class=HTMLResponse)
async def channels_page(request: Request):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    runtime_bot = get_bot()
    broadcasters = []

    if runtime_bot is not None and runtime_bot.services is not None:
        broadcaster_service = runtime_bot.services.broadcasters

        await broadcaster_service.refresh_live_statuses()

        broadcasters = list(broadcaster_service.get_broadcasters().values())

    broadcasters.sort(key=lambda broadcaster: (not broadcaster.is_live, (broadcaster.name or broadcaster.id).lower()))

    return templates.TemplateResponse(
        request=request,
        name="admin/channels.html",
        context=build_admin_context(
            request,
            active_page="channels",
            broadcasters=broadcasters,
            broadcaster_count=len(broadcasters)
        )
    )


@router.get("/{broadcaster_id}", response_class=HTMLResponse)
async def channel_details_page(request: Request, broadcaster_id: str):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return await get_runtime_error(request)

    services = runtime_bot.services
    broadcaster_service = services.broadcasters
    broadcaster = get_broadcaster(runtime_bot, broadcaster_id)

    if broadcaster is None:
        return get_channel_error(request)

    await broadcaster_service.refresh_live_statuses()

    channel_settings = await services.broadcaster_settings.get_settings(broadcaster_id)
    viewer_queue = services.viewer_queue
    redemption_activity = await get_redemption_dashboard_data(services, broadcaster_id)
    channel_features = services.features.get_channel_features(broadcaster_id)
    profile_features = services.features.get_admin_profile_features(broadcaster_id)
    raid_configured = FeatureName.RAID_BOSSES in channel_features
    raid_metrics = await services.raid_bosses.get_dashboard_metrics(broadcaster_id) if raid_configured else None
    global_groups = services.features.get_global_groups(broadcaster_id)
    global_commands = services.features.get_global_commands(broadcaster_id)
    chat_identity = services.chat_identity.get_state(broadcaster_id)

    return templates.TemplateResponse(
        request=request,
        name="admin/channel_details.html",
        context=build_admin_context(
            request,
            active_page="channels",
            broadcaster=broadcaster,
            channel_settings=channel_settings,
            queue_open=viewer_queue.is_queue_open(broadcaster_id),
            queue_users=viewer_queue.list_queue(broadcaster_id),
            queue_size=viewer_queue.size(broadcaster_id),
            redemption_activity=redemption_activity,
            raid_configured=raid_configured,
            raid_metrics=raid_metrics,
            channel_features=channel_features,
            profile_features=profile_features,
            global_groups=global_groups,
            global_commands=global_commands,
            chat_identity=chat_identity,
            queue_result=request.query_params.get("queue_result"),
            queue_message=request.query_params.get("queue_message"),
            toggle_result=request.query_params.get("toggle_result"),
            toggle_message=request.query_params.get("toggle_message"),
            identity_result=request.query_params.get("identity_result"),
            identity_message=request.query_params.get("identity_message")
        )
    )


@router.post("/{broadcaster_id}/custom-bot/premium")
async def update_custom_bot_premium(request: Request, broadcaster_id: str, action: str = Form(...), csrf_token: str = Form(...)):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return await get_runtime_error(request)

    if get_broadcaster(runtime_bot, broadcaster_id) is None:
        return get_channel_error(request)

    if action not in {"enable", "disable"}:
        return redirect_to_channel(broadcaster_id, identity_result="error", identity_message="Unknown premium identity action.")

    await runtime_bot.services.chat_identity.set_premium_enabled(broadcaster_id, action == "enable")
    message = "Premium custom identity access enabled." if action == "enable" else "Premium custom identity access disabled. RatsBoomBot will send messages for this channel."
    return redirect_to_channel(broadcaster_id, identity_result="success", identity_message=message)


@router.post("/{broadcaster_id}/custom-bot/disconnect")
async def disconnect_custom_bot(request: Request, broadcaster_id: str, csrf_token: str = Form(...)):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    runtime_db = get_db()

    if runtime_bot is None or runtime_bot.services is None or runtime_db is None:
        return await get_runtime_error(request)

    if get_broadcaster(runtime_bot, broadcaster_id) is None:
        return get_channel_error(request)

    previous_user_id = await runtime_bot.services.chat_identity.disconnect(broadcaster_id)

    if previous_user_id and not runtime_bot.services.chat_identity.is_custom_bot(previous_user_id):
        await delete_token(runtime_db, previous_user_id)

    return redirect_to_channel(broadcaster_id, identity_result="success", identity_message="Custom bot disconnected. RatsBoomBot is active for this channel again.")


@router.get("/{broadcaster_id}/api/activity", response_class=JSONResponse)
async def channel_activity_state(request: Request, broadcaster_id: str):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return JSONResponse({"detail": "Administrator authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = get_broadcaster(runtime_bot, broadcaster_id)

    if broadcaster is None:
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    viewer_queue = services.viewer_queue
    queue_users = viewer_queue.list_queue(broadcaster_id)

    channel_features = services.features.get_channel_features(broadcaster_id)
    raid_configured = FeatureName.RAID_BOSSES in channel_features
    return JSONResponse({
        "queue": {
            "open": viewer_queue.is_queue_open(broadcaster_id),
            "size": len(queue_users),
            "users": queue_users
        },
        "redemptions": await get_redemption_dashboard_data(services, broadcaster_id),
        "raid": await services.raid_bosses.get_dashboard_metrics(broadcaster_id) if raid_configured else None
    })


@router.post("/{broadcaster_id}/toggles")
async def update_channel_toggle(
    request: Request,
    broadcaster_id: str,
    toggle_type: str = Form(...),
    toggle_name: str = Form(...),
    action: str = Form(...),
    csrf_token: str = Form(...)
):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    validate_csrf_token(request, csrf_token)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return await get_runtime_error(request)

    broadcaster = get_broadcaster(runtime_bot, broadcaster_id)

    if broadcaster is None:
        return get_channel_error(request)

    services = runtime_bot.services
    updated_by = "dashboard"

    if action not in {"enable", "disable", "reset"}:
        return redirect_to_channel(
            broadcaster_id,
            toggle_result="error",
            toggle_message="Unknown toggle action."
        )

    enabled = action == "enable"

    try:
        if toggle_type == "feature":
            toggle = FeatureName(toggle_name)

            if action == "reset":
                state = await services.features.clear_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = toggle.value.replace("_", " ").title()

        elif toggle_type == "capability":
            toggle = ProfileFeatureName(toggle_name)

            if action == "reset":
                state = await services.features.clear_profile_feature_availability(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_profile_feature_available(broadcaster_id, toggle, action == "enable", updated_by)

            display_name = "League of Legends access" if toggle is ProfileFeatureName.LEAGUE else "Overwatch access"

        elif toggle_type == "profile_feature":
            toggle = ProfileFeatureName(toggle_name)

            if action == "reset":
                state = await services.features.clear_profile_feature_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_profile_feature_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = "League of Legends" if toggle is ProfileFeatureName.LEAGUE else "Overwatch"

        elif toggle_type == "global_group":
            toggle = GlobalCommandGroup(toggle_name)

            if action == "reset":
                state = await services.features.clear_global_group_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_global_group_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = toggle.value.replace("_", " ").title()

        elif toggle_type == "global_command":
            toggle = GlobalCommandName(toggle_name)

            if action == "reset":
                state = await services.features.clear_global_command_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_global_command_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = f"!{toggle.value}"

        else:
            return redirect_to_channel(
                broadcaster_id,
                toggle_result="error",
                toggle_message="Unknown toggle type."
            )

    except ValueError:
        return redirect_to_channel(
            broadcaster_id,
            toggle_result="error",
            toggle_message="Unknown toggle name."
        )
    except Exception:
        return redirect_to_channel(
            broadcaster_id,
            toggle_result="error",
            toggle_message="The toggle could not be updated."
        )

    if toggle_type == "capability" and action == "reset":
        message = f"{display_name} was reset to its code-defined availability."
    elif toggle_type == "capability":
        message = f"{display_name} was {'granted' if state.available else 'revoked'}."
    elif action == "reset":
        message = f"{display_name} was reset to its profile default."
    else:
        effective_state = "enabled" if state.effective_enabled else "disabled"
        message = f"{display_name} is now {effective_state}."

    return redirect_to_channel(
        broadcaster_id,
        toggle_result="success",
        toggle_message=message
    )


@router.post("/{broadcaster_id}/delete")
async def delete_broadcaster(request: Request, broadcaster_id: str, csrf_token: str = Form(...)):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    validate_csrf_token(request, csrf_token)

    if str(broadcaster_id) == str(settings.BOT_ID):
        return await render_error(
            request,
            active_page="channels",
            title="Cannot remove bot account",
            message="The bot account cannot be removed as a broadcaster.",
            status_code=400
        )

    runtime_bot = get_bot()
    runtime_db = get_db()

    if runtime_bot is None or runtime_bot.services is None or runtime_db is None:
        return await get_runtime_error(request)

    services = runtime_bot.services
    broadcaster = get_broadcaster(runtime_bot, broadcaster_id)

    if broadcaster is None:
        return get_channel_error(request)

    if services.stream_logs.is_active(broadcaster_id):
        await services.stream_logs.end_session(broadcaster_id)

    custom_bot_user_id = await services.chat_identity.remove_channel(broadcaster_id)

    if custom_bot_user_id and not services.chat_identity.is_custom_bot(custom_bot_user_id):
        await delete_token(runtime_db, custom_bot_user_id)

    await delete_token(runtime_db, broadcaster_id)

    services.broadcasters.remove_broadcaster(broadcaster_id)
    await services.viewer_queue.remove_queue(broadcaster_id)

    return RedirectResponse(url="/admin/channels?removed=1", status_code=303)


@router.post("/{broadcaster_id}/viewer-queue/remove")
async def remove_viewer_from_queue(
    request: Request,
    broadcaster_id: str,
    position: int = Form(...),
    csrf_token: str = Form(...)
):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    validate_csrf_token(request, csrf_token)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return await get_runtime_error(request)

    broadcaster = get_broadcaster(runtime_bot, broadcaster_id)

    if broadcaster is None:
        return get_channel_error(request)

    removed, _, message = await runtime_bot.services.viewer_queue.remove_position(broadcaster_id, position)
    result = "removed" if removed else "remove_failed"

    return redirect_to_channel(
        broadcaster_id,
        queue_result=result,
        queue_message=message
    )
