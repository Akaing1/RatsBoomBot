import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from bot.services.channels.profile_settings import LOYALTY_GROUP
from bot.profiles import FeatureName, GlobalCommandGroup, GlobalCommandName, ProfileFeatureName, get_active_profile
from config.settings import settings
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY, logout_channel_user
from web.channel.command_help import build_command_help_groups
from web.shared.common import templates
from web.shared.live_chat import stream_chat_events
from web.state import get_bot

router = APIRouter()
LOGGER = logging.getLogger("RatBoomBot")
CHAT_SEND_TARGETS = {"twitch", "youtube", "both"}
CHAT_MESSAGE_MAX_LENGTH = 200


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


async def get_raid_contributor_data(services, broadcaster_id: str) -> dict[str, object]:
    event = await services.raid_bosses.get_active_event(broadcaster_id)

    if event is None:
        return {"active": False, "contributors": []}

    contributors = await services.raid_bosses.get_contributors(broadcaster_id)

    return {
        "active": True,
        "boss_name": event.boss_name,
        "current_hp": event.current_hp,
        "max_hp": event.max_hp,
        "contributors": [
            {"rank": rank, "username": username, "damage": damage}
            for rank, (username, damage) in enumerate(contributors, start=1)
        ]
    }


async def get_ad_status(broadcaster) -> dict[str, object]:
    if not broadcaster.is_live:
        return {"state": "offline", "label": "Stream offline", "next_ad_at": None, "ends_at": None}

    try:
        schedule = await broadcaster.fetch_ad_schedule()
    except Exception:
        LOGGER.exception("[Dashboard] Failed to fetch ad schedule for broadcaster %s.", broadcaster.id)
        return {"state": "unavailable", "label": "Ad schedule unavailable", "next_ad_at": None, "ends_at": None}

    now = datetime.now(UTC)
    last_ad_at = schedule.last_ad_at
    ends_at = last_ad_at + timedelta(seconds=schedule.duration) if last_ad_at is not None else None

    if ends_at is not None and last_ad_at <= now < ends_at:
        return {"state": "running", "label": "Ad running", "next_ad_at": None, "ends_at": ends_at.isoformat()}

    if schedule.next_ad_at is not None:
        return {"state": "scheduled", "label": "Next ad", "next_ad_at": schedule.next_ad_at.isoformat(), "ends_at": None}

    return {"state": "none", "label": "No ad scheduled", "next_ad_at": None, "ends_at": None}


@router.get("/channel/api/raid-contributors", response_class=JSONResponse)
async def channel_raid_contributors(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return JSONResponse(await get_raid_contributor_data(services, broadcaster_id))


@router.get("/channel/api/redemptions", response_class=JSONResponse)
async def channel_redemption_activity(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return JSONResponse(await get_redemption_dashboard_data(services, broadcaster_id))


@router.get("/channel/api/viewer-queue", response_class=JSONResponse)
async def channel_viewer_queue_state(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    viewer_queue = services.viewer_queue
    queue_users = viewer_queue.list_queue(broadcaster_id)

    return JSONResponse({
        "open": viewer_queue.is_queue_open(broadcaster_id),
        "size": len(queue_users),
        "users": queue_users
    })


@router.get("/channel/api/chat/stream")
async def channel_chat_stream(request: Request, view: str = "both"):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    if runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id)) is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return StreamingResponse(
        stream_chat_events(request, runtime_bot.services.live_chat, str(broadcaster_id), view),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/channel/api/ad-status", response_class=JSONResponse)
async def channel_ad_status(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    broadcaster = runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    return JSONResponse(await get_ad_status(broadcaster))


@router.post("/channel/api/chat/send", response_class=JSONResponse)
async def channel_send_chat_message(
    request: Request,
    message: str = Form(...),
    target: str = Form(...),
    csrf_token: str = Form(...)
):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)

    validate_csrf_token(request, csrf_token)
    message = message.strip()
    target = target.strip().lower()

    if not message:
        return JSONResponse({"detail": "Enter a message to send."}, status_code=400)

    if len(message) > CHAT_MESSAGE_MAX_LENGTH:
        return JSONResponse({"detail": f"Messages are limited to {CHAT_MESSAGE_MAX_LENGTH} characters."}, status_code=400)

    if target not in CHAT_SEND_TARGETS:
        return JSONResponse({"detail": "Choose Twitch, YouTube, or Both."}, status_code=400)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)

    sent = []
    errors = {}

    if target in {"twitch", "both"}:
        try:
            twitch_channel = runtime_bot.create_partialuser(str(broadcaster_id))
            result = await twitch_channel.send_message(
                sender=str(broadcaster_id), token_for=str(broadcaster_id), message=message
            )
            if getattr(result, "sent", False):
                sent.append("twitch")
            else:
                errors["twitch"] = getattr(result, "dropped_message", None) or "Twitch did not send the message."
        except Exception:
            LOGGER.exception("[Dashboard] Failed to send Twitch message for broadcaster %s.", broadcaster_id)
            errors["twitch"] = "Reconnect Twitch to enable dashboard replies."

    if target in {"youtube", "both"}:
        try:
            await services.live_chat.send_youtube_message(str(broadcaster_id), message)
            sent.append("youtube")
        except ValueError as error:
            youtube_error = str(error)

            if target == "youtube" or not sent:
                errors["youtube"] = (
                    "YouTube is offline. Start a YouTube livestream with live chat enabled before sending a message."
                    if "No active YouTube live chat" in youtube_error
                    else youtube_error
                )
        except Exception:
            LOGGER.exception("[Dashboard] Failed to send YouTube message for broadcaster %s.", broadcaster_id)

            if target == "youtube" or not sent:
                errors["youtube"] = "Reconnect YouTube to enable dashboard replies."

    if not sent:
        detail = " ".join(errors.values()) or "The message could not be sent."
        return JSONResponse({"detail": detail, "sent": sent, "errors": errors}, status_code=400)

    status_code = 207 if errors else 200
    return JSONResponse({"sent": sent, "errors": errors}, status_code=status_code)


@router.get("/channel", response_class=HTMLResponse)
async def channel_dashboard(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(
            request=request,
            name="channel/dashboard.html",
            context={
                "active_page": "overview",
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
    redemption_activity = await get_redemption_dashboard_data(services, broadcaster_id)
    gambling_loss_total = await services.points.get_gambling_loss_total(broadcaster_id)
    raid_enabled = services.features.is_enabled(broadcaster_id, FeatureName.RAID_BOSSES)
    raid_metrics = await services.raid_bosses.get_dashboard_metrics(broadcaster_id) if raid_enabled else None
    ad_status = await get_ad_status(broadcaster)

    return templates.TemplateResponse(
        request=request,
        name="channel/dashboard.html",
        context={
            "active_page": "overview",
            "broadcaster": broadcaster,
            "runtime_unavailable": False,
            "channel_settings": channel_settings,
            "queue_open": viewer_queue.is_queue_open(broadcaster_id),
            "queue_users": viewer_queue.list_queue(broadcaster_id),
            "queue_size": viewer_queue.size(broadcaster_id),
            "redemption_activity": redemption_activity,
            "gambling_loss_total": gambling_loss_total,
            "raid_enabled": raid_enabled,
            "raid_metrics": raid_metrics,
            "youtube_chat": services.live_chat.get_youtube_state(broadcaster_id),
            "ad_status": ad_status,
            "queue_result": request.query_params.get("queue_result"),
            "queue_message": request.query_params.get("queue_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.get("/channel/help", response_class=HTMLResponse)
async def channel_help_page(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    profile = get_active_profile(broadcaster_id)

    if broadcaster is None or profile is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    command_groups = build_command_help_groups(services.features, broadcaster_id, profile)
    command_count = sum(len(group.commands) for group in command_groups)
    enabled_command_count = sum(group.enabled_count for group in command_groups)
    raid_contributor_data = await get_raid_contributor_data(services, broadcaster_id)

    return templates.TemplateResponse(
        request=request,
        name="channel/help.html",
        context={
            "active_page": "help",
            "broadcaster": broadcaster,
            "command_groups": command_groups,
            "command_count": command_count,
            "enabled_command_count": enabled_command_count,
            "raid_contributor_data": raid_contributor_data,
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
        name="channel/features.html",
        context={
            "active_page": "features",
            "broadcaster": broadcaster,
            "channel_features": services.features.get_channel_features(broadcaster_id),
            "profile_features": services.features.get_profile_features(broadcaster_id),
            "global_groups": services.features.get_global_groups(broadcaster_id),
            "global_commands": services.features.get_global_commands(broadcaster_id),
            "toggle_result": request.query_params.get("toggle_result"),
            "toggle_message": request.query_params.get("toggle_message"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.get("/channel/loyalty", response_class=HTMLResponse)
@router.get("/channel/customization", response_class=HTMLResponse)
async def channel_customization_page(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None or get_active_profile(broadcaster_id) is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    loyalty_page = request.url.path == "/channel/loyalty"
    groups = services.profile_settings.get_setting_groups(broadcaster_id, {feature.value for feature in services.features.get_profile_features(broadcaster_id)})
    widget_urls = {}

    if not loyalty_page:
        widget_token = await services.live_chat.get_or_create_widget_token(broadcaster_id)
        widget_base_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/widgets/chat/{widget_token}"
        widget_urls = {view: f"{widget_base_url}?view={view}" for view in ("chat", "commands", "both")}

    return templates.TemplateResponse(
        request=request,
        name="channel/loyalty.html" if loyalty_page else "channel/customization.html",
        context={
            "active_page": "loyalty" if loyalty_page else "customization",
            "customization_action": "/channel/loyalty" if loyalty_page else "/channel/customization",
            "show_social_links": not loyalty_page,
            "loyalty_alias": get_active_profile(broadcaster_id).points.command_alias,
            "broadcaster": broadcaster,
            "channel_settings": await services.broadcaster_settings.get_settings(broadcaster_id),
            "setting_groups": {name: entries for name, entries in groups.items() if (name == LOYALTY_GROUP) == loyalty_page},
            "chat_identity": services.chat_identity.get_state(broadcaster_id),
            "youtube_chat": services.live_chat.get_youtube_state(broadcaster_id),
            "widget_urls": widget_urls,
            "setting_result": request.query_params.get("setting_result"),
            "setting_message": request.query_params.get("setting_message"),
            "identity_result": request.query_params.get("identity_result"),
            "identity_message": request.query_params.get("identity_message"),
            "youtube_result": request.query_params.get("youtube_result"),
            "youtube_message": request.query_params.get("youtube_message"),
            "social_tab": request.query_params.get("social_tab", "links"),
            "csrf_token": get_csrf_token(request)
        }
    )


@router.post("/channel/loyalty")
@router.post("/channel/customization")
async def update_channel_customization(request: Request, setting_name: str = Form(...), value: str = Form(""), action: str = Form(...), csrf_token: str = Form(...)):
    destination = "/channel/loyalty" if request.url.path == "/channel/loyalty" else "/channel/customization"
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url=f"{destination}?setting_result=error&setting_message=Runtime+unavailable.", status_code=303)

    services = runtime_bot.services

    try:
        if destination == "/channel/loyalty" and services.profile_settings.get_definition(setting_name).group != LOYALTY_GROUP:
            raise ValueError("Only loyalty point names and responses can be edited here.")
        if setting_name == "social.discord_url":
            await services.broadcaster_settings.set_discord_url(broadcaster_id, value.strip())
            message = "Discord URL was updated."
        elif setting_name == "social.youtube_url":
            await services.broadcaster_settings.set_youtube_url(broadcaster_id, value.strip())
            message = "YouTube URL was updated."
        else:
            definition = services.profile_settings.get_definition(setting_name)

            if action == "save":
                await services.profile_settings.set_override(broadcaster_id, setting_name, value, f"streamer:{broadcaster_id}")
                message = f"{definition.label} was updated."
            elif action == "reset":
                await services.profile_settings.clear_override(broadcaster_id, setting_name, f"streamer:{broadcaster_id}")
                message = f"{definition.label} was reset to its channel default."
            else:
                raise ValueError("Unknown customization action.")
    except (TypeError, ValueError) as error:
        return RedirectResponse(url=f"{destination}?setting_result=error&setting_message={quote_plus(str(error))}", status_code=303)

    return RedirectResponse(url=f"{destination}?setting_result=success&setting_message={quote_plus(message)}", status_code=303)


@router.post("/channel/features/toggles")
async def update_channel_feature(request: Request, toggle_type: str = Form(...), toggle_name: str = Form(...), action: str = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Runtime+unavailable.", status_code=303)

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))

    if broadcaster is None:
        logout_channel_user(request)
        return RedirectResponse(url="/connect", status_code=303)

    if action not in {"enable", "disable", "reset"}:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle+action.", status_code=303)

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
            return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle+type.", status_code=303)

    except ValueError:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=Unknown+toggle.", status_code=303)
    except Exception:
        return RedirectResponse(url="/channel/features?toggle_result=error&toggle_message=The+toggle+could+not+be+updated.", status_code=303)

    if action == "reset":
        message = f"{display_name} was reset to its profile default."
    else:
        effective_state = "enabled" if state.effective_enabled else "disabled"
        message = f"{display_name} is now {effective_state}."

    return RedirectResponse(url=f"/channel/features?toggle_result=success&toggle_message={quote_plus(message)}", status_code=303)


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

    removed, _, message = await services.viewer_queue.remove_position(broadcaster_id, position)

    result = "removed" if removed else "remove_failed"

    return RedirectResponse(
        url=f"/channel?queue_result={result}&queue_message={quote_plus(message)}", status_code=303)


@router.post("/channel/logout")
async def channel_logout(request: Request, csrf_token: str = Form(...)):
    validate_csrf_token(request, csrf_token)
    logout_channel_user(request)

    return RedirectResponse(url="/connect", status_code=303)
