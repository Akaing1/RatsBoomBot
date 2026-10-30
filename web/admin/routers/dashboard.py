import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web.admin.auth import require_admin
from web.shared.common import build_admin_context, templates
from web.state import get_bot, get_db

router = APIRouter()
LOGGER = logging.getLogger("RatBoomBot")


def twitch_connection_status(bot):
    if bot is None:
        return "Unavailable", 0, 0

    info = bot.conduit_info
    expected = info.shard_count or 0
    connected = sum(bool(socket.connected) for socket in info.websockets.values())
    if expected > 0 and connected >= expected:
        return "Connected", connected, expected
    if connected:
        return "Degraded", connected, expected
    return "Disconnected" if expected else "Starting", connected, expected


async def database_is_responsive(database):
    if database is None:
        return False
    try:
        # Bound acquisition as well as the query when the pool is busy or closed.
        async with asyncio.timeout(2):
            async with database.acquire() as connection:
                row = await connection.fetchone("SELECT 1")
                return row is not None and row[0] == 1
    except Exception:
        LOGGER.warning("[Admin] Database health check failed.", exc_info=True)
        return False


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin_redirect = await require_admin(request)
    if admin_redirect:
        return admin_redirect

    runtime_bot = get_bot()
    twitch_status, connected_shards, expected_shards = twitch_connection_status(runtime_bot)
    database_connected = await database_is_responsive(get_db())
    broadcasters = []
    services = runtime_bot.services if runtime_bot is not None else None
    if services is not None:
        # Use the runtime's existing stream state; opening Overview must not fan
        # out into one Helix request per broadcaster or alter shared live state.
        broadcasters = list(services.broadcasters.get_broadcasters().values())
        broadcasters.sort(key=lambda broadcaster: (
            not broadcaster.is_live, (broadcaster.name or broadcaster.id).casefold()
        ))

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            twitch_status=twitch_status,
            connected_shards=connected_shards,
            expected_shards=expected_shards,
            database_connected=database_connected,
            runtime_available=services is not None,
            broadcasters=broadcasters,
            broadcaster_count=len(broadcasters),
            live_count=sum(broadcaster.is_live for broadcaster in broadcasters),
        ),
    )
