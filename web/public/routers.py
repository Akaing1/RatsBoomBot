from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from bot.profiles import FeatureName, get_active_profile
from config.settings import settings
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.command_help import build_enabled_command_help_groups
from web.shared.common import templates
from web.state import get_bot

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request):
    is_authenticated = bool(request.session.get(CHANNEL_USER_ID_KEY))
    destination = "/channel" if is_authenticated else "/connect/twitch"
    dashboard_url = f"{settings.DASHBOARD_BASE_URL.rstrip('/')}{destination}"

    return templates.TemplateResponse(
        request=request,
        name="public/home.html",
        context={
            "dashboard_url": dashboard_url,
            "is_authenticated": is_authenticated,
            "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/")
        }
    )


@router.get("/commands/{channel_name}", response_class=HTMLResponse)
async def public_channel_commands(request: Request, channel_name: str):
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(request=request, name="public/channel_commands_unavailable.html", context={"channel_name": channel_name}, status_code=503)

    services = runtime_bot.services
    broadcaster = next((item for item in services.broadcasters.get_broadcasters().values() if channel_name.lower() in {str(item.login or "").lower(), str(item.display_name or "").lower()}), None)

    if broadcaster is None:
        return templates.TemplateResponse(request=request, name="public/channel_commands_unavailable.html", context={"channel_name": channel_name, "not_found": True}, status_code=404)

    profile = get_active_profile(broadcaster.id)

    if profile is None:
        return templates.TemplateResponse(request=request, name="public/channel_commands_unavailable.html", context={"channel_name": channel_name, "not_found": True}, status_code=404)

    command_groups = build_enabled_command_help_groups(services.features, broadcaster.id, profile)
    raid_enabled = services.features.is_enabled(broadcaster.id, FeatureName.RAID_BOSSES)
    raid_metrics = await services.raid_bosses.get_dashboard_metrics(broadcaster.id) if raid_enabled else None

    return templates.TemplateResponse(
        request=request,
        name="public/channel_commands.html",
        context={
            "broadcaster": broadcaster,
            "command_groups": command_groups,
            "command_count": sum(len(group.commands) for group in command_groups),
            "raid_metrics": raid_metrics,
            "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/")
        }
    )
