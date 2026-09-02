from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot.profiles import FeatureName, get_active_profile
from config.settings import settings
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.command_help import build_enabled_command_help_groups
from web.shared.common import templates
from web.state import get_bot

router = APIRouter()


@router.get("/chatters", response_class=HTMLResponse)
async def public_chatter_search(request: Request, q: str = ""):
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(request=request, name="public/chatter_not_found.html", context={"query": q, "unavailable": True}, status_code=503)

    identity = await runtime_bot.services.chatter_stats.resolve_identity(q)

    if identity is None:
        return templates.TemplateResponse(request=request, name="public/chatter_not_found.html", context={"query": q}, status_code=404)

    return RedirectResponse(url=f"/chatters/{identity['login']}", status_code=303)


@router.get("/chatters/{chatter_name}", response_class=HTMLResponse)
async def public_chatter_profile(request: Request, chatter_name: str):
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(request=request, name="public/chatter_not_found.html", context={"query": chatter_name, "unavailable": True}, status_code=503)

    profile = await runtime_bot.services.chatter_stats.get_global_profile(chatter_name)

    if profile is None:
        return templates.TemplateResponse(request=request, name="public/chatter_not_found.html", context={"query": chatter_name}, status_code=404)

    return templates.TemplateResponse(request=request, name="public/chatter_profile.html", context={"profile": profile, "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/")})


@router.get("/chatters/{chatter_name}/channels/{channel_name}", response_class=HTMLResponse)
async def public_chatter_channel_profile(request: Request, chatter_name: str, channel_name: str):
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(request=request, name="public/chatter_not_found.html", context={"query": chatter_name, "unavailable": True}, status_code=503)

    profile = await runtime_bot.services.chatter_stats.get_channel_profile(chatter_name, channel_name)

    if profile is None:
        return templates.TemplateResponse(request=request, name="public/chatter_not_found.html", context={"query": chatter_name, "channel_name": channel_name}, status_code=404)

    return templates.TemplateResponse(request=request, name="public/chatter_channel_profile.html", context={"profile": profile, "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/")})


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


@router.get("/commands/{channel_name}", include_in_schema=False)
async def legacy_public_channel_commands(channel_name: str):
    return RedirectResponse(url=f"/help/{channel_name}", status_code=308)


@router.get("/help/{channel_name}", response_class=HTMLResponse)
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
    raid_contributors = await services.raid_bosses.get_contributors(broadcaster.id) if raid_metrics and raid_metrics["status"] == "active" else []

    return templates.TemplateResponse(
        request=request,
        name="public/channel_commands.html",
        context={
            "broadcaster": broadcaster,
            "command_groups": command_groups,
            "command_count": sum(len(group.commands) for group in command_groups),
            "raid_metrics": raid_metrics,
            "raid_contributors": raid_contributors,
            "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/")
        }
    )



def find_public_broadcaster(services, channel_name: str):
    return next((item for item in services.broadcasters.get_broadcasters().values() if channel_name.lower() in {str(item.login or "").lower(), str(item.display_name or "").lower()}), None)


async def get_public_raid_state(services, broadcaster_id: str) -> dict[str, object]:
    metrics = await services.raid_bosses.get_dashboard_metrics(broadcaster_id)
    contributors = await services.raid_bosses.get_contributors(broadcaster_id) if metrics and metrics["status"] == "active" else []
    return {
        "metrics": metrics,
        "contributors": [
            {"rank": rank, "username": username, "damage": damage}
            for rank, (username, damage) in enumerate(contributors, start=1)
        ]
    }


@router.get("/api/raid/{channel_name}", response_class=JSONResponse)
async def public_raid_state(channel_name: str):
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)

    services = runtime_bot.services
    broadcaster = find_public_broadcaster(services, channel_name)

    if broadcaster is None:
        return JSONResponse({"detail": "Channel not found."}, status_code=404)

    profile = get_active_profile(broadcaster.id)

    if profile is None or not services.features.is_enabled(broadcaster.id, FeatureName.RAID_BOSSES):
        return JSONResponse({"detail": "Raid bosses are not enabled for this channel."}, status_code=404)

    return JSONResponse(await get_public_raid_state(services, broadcaster.id))


@router.get("/raid/{channel_name}", response_class=HTMLResponse)
async def public_channel_raid_page(request: Request, channel_name: str):
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return templates.TemplateResponse(request=request, name="public/channel_commands_unavailable.html", context={"channel_name": channel_name}, status_code=503)

    services = runtime_bot.services
    broadcaster = find_public_broadcaster(services, channel_name)

    if broadcaster is None:
        return templates.TemplateResponse(request=request, name="public/channel_commands_unavailable.html", context={"channel_name": channel_name, "not_found": True}, status_code=404)

    profile = get_active_profile(broadcaster.id)

    if profile is None or not services.features.is_enabled(broadcaster.id, FeatureName.RAID_BOSSES):
        return templates.TemplateResponse(request=request, name="public/channel_commands_unavailable.html", context={"channel_name": channel_name, "not_found": True}, status_code=404)

    config = profile.raid_bosses
    raid_state = await get_public_raid_state(services, broadcaster.id)
    recent_events = await services.raid_bosses.get_recent_events(broadcaster.id)
    shop_items = (
        {"name": "Basic Sword", "item_id": "basic sword", "type": "Melee", "cost": config.weapon_cost},
        {"name": "Basic Bow", "item_id": "basic bow", "type": "Ranged", "cost": config.weapon_cost},
        {"name": "Apprentice Tome", "item_id": "apprentice tome", "type": "Magic", "cost": config.weapon_cost}
    )
    raid_commands = (
        {"syntax": "!raid", "description": "Show the current encounter status."},
        {"syntax": "!raid attack", "description": "Attack once during the current stream."},
        {"syntax": "!raid shop", "description": "Open this raid guide and shop."},
        {"syntax": "!raid buy <item>", "description": "Purchase a weapon or consumable with loyalty points."},
        {"syntax": "!raid craft <weapon>", "description": "Combine two matching weapons from the previous tier and pay the crafting fee."},
        {"syntax": "!raid inventory", "description": "View your weapons, equipped item, durability, and potion attacks."},
        {"syntax": "!raid equip <weapon>", "description": "Equip an owned weapon."},
        {"syntax": "!raid repair <weapon>", "description": "Restore an owned weapon to full durability."},
        {"syntax": "!raid leaderboard", "description": "Show the leading contributors in chat."},
        {"syntax": "!loot", "description": "Show your rewards from the most recently completed raid."}
    )

    return templates.TemplateResponse(
        request=request,
        name="public/channel_raid.html",
        context={
            "broadcaster": broadcaster,
            "config": config,
            "raid_metrics": raid_state["metrics"],
            "raid_contributors": raid_state["contributors"],
            "recent_events": recent_events,
            "shop_items": shop_items,
            "raid_commands": raid_commands,
            "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/")
        }
    )
