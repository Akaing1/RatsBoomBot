from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName
from web.admin_auth import get_csrf_token, validate_csrf_token
from web.channel_auth import CHANNEL_USER_ID_KEY, logout_channel_user
from web.common import templates
from web.state import get_bot

router = APIRouter()


@router.get("/channel", response_class=HTMLResponse)
async def channel_dashboard(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(
            request=request,
            name="channel_dashboard.html",
            context={
                "broadcaster": None,
                "runtime_unavailable": True,
                "csrf_token": get_csrf_token(request)
            },
            status_code=503
        )

    services = runtime_bot.services
    broadcaster_service = services.broadcasters
    broadcaster = broadcaster_service.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    await broadcaster_service.refresh_live_statuses()

    channel_settings = await services.broadcaster_settings.get_settings(broadcaster_id)
    viewer_queue = services.viewer_queue

    return templates.TemplateResponse(
        request=request,
        name="channel_dashboard.html",
        context={
            "broadcaster": broadcaster,
            "runtime_unavailable": False,
            "channel_settings": channel_settings,
            "queue_open": viewer_queue.is_queue_open(broadcaster_id),
            "queue_users": viewer_queue.list_queue(broadcaster_id),
            "queue_size": viewer_queue.size(broadcaster_id),
            "queue_result": request.query_params.get("queue_result"),
            "queue_message": request.query_params.get("queue_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.get("/channel/features", response_class=HTMLResponse)
async def channel_features_page(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="channel_features.html",
        context={
            "active_page": "features",
            "broadcaster": broadcaster,
            "channel_features": services.features.get_channel_features(broadcaster_id),
            "global_groups": services.features.get_global_groups(broadcaster_id),
            "global_commands": services.features.get_global_commands(broadcaster_id),
            "toggle_result": request.query_params.get("toggle_result"),
            "toggle_message": request.query_params.get("toggle_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.post("/channel/features/toggles")
async def update_channel_feature(request: Request, toggle_type: str = Form(...), toggle_name: str = Form(...),
                                 action: str = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Runtime+unavailable.",
                                status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    if action not in {"enable", "disable", "reset"}:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle+action.",
                                status_code=303)

    enabled = action == "enable"
    updated_by = f"streamer:{broadcaster_id}"

    try:
        if toggle_type == "feature":
            toggle = FeatureName(toggle_name)

            if action == "reset":
                state = await services.features.clear_override(broadcaster_id, toggle, updated_by)
            else:
                state = await services.features.set_enabled(broadcaster_id, toggle, enabled, updated_by)

            display_name = toggle.value.replace("_", " ").title()

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
            return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle+type.",
                                    status_code=303)

    except ValueError:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle.",
                                status_code=303)
    except Exception:
        return RedirectResponse(
            url="/channel/features?toggle_result=error&toggle_message=The+toggle+could+not+be+updated.",
            status_code=303)

    if action == "reset":
        message = f"{display_name} was reset to its profile default."
    else:
        effective_state = "enabled" if state.effective_enabled else "disabled"
        message = f"{display_name} is now {effective_state}."

    return RedirectResponse(
        url=f"/channel/features?toggle_result=success&toggle_message={quote_plus(message)}", status_code=303)


@router.post("/channel/viewer-queue/remove")
async def remove_viewer_from_channel_queue(request: Request, position: int = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(
            url="/channel?queue_result=remove_failed&queue_message=The+bot+runtime+is+unavailable.", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    removed, _, message = services.viewer_queue.remove_position(broadcaster_id, position)

    result = "removed" if removed else "remove_failed"

    return RedirectResponse(
        url=f"/channel?queue_result={result}&queue_message={quote_plus(message)}", status_code=303)


@router.post("/channel/logout")
async def channel_logout(request: Request, csrf_token: str = Form(...)):
    validate_csrf_token(request, csrf_token)
    logout_channel_user(request)

    return RedirectResponse(url="/connect", status_code=303)
