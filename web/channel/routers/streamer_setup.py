import asyncio
import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from bot.profiles import FeatureName, get_active_profile
from storage.streamer_setup import get_setup, initialize_setup, save_setup
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY, CHANNEL_USER_LOGIN_KEY
from web.shared.common import templates
from web.state import get_bot, get_db

router = APIRouter()
LOGGER = logging.getLogger("RatBoomBot")
SETUP_URL = "/channel/setup"
STEPS = ("Welcome", "Connect the bot", "Choose features", "Make it yours", "Try a command", "Review setup")


def setup_context(request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id or getattr(request.state, "channel_access", None):
        raise HTTPException(status_code=403, detail="Sign in as the channel owner to use guided setup.")
    db, bot = get_db(), get_bot()
    if db is None or getattr(bot, "services", None) is None:
        raise HTTPException(status_code=503, detail="Guided setup is temporarily unavailable.")
    return str(broadcaster_id), db, bot


@router.get(SETUP_URL)
async def streamer_setup(request: Request):
    if not request.session.get(CHANNEL_USER_ID_KEY):
        return RedirectResponse("/connect", status_code=303)
    broadcaster_id, db, bot = setup_context(request)
    progress = await get_setup(db, broadcaster_id)
    step = progress["step"] if progress else 0
    identity = bot.services.chat_identity.get_state(broadcaster_id)
    bot_user = getattr(bot, "user", None)
    bot_login = identity.bot_login if identity.connected else getattr(bot_user, "name", None)
    profile = get_active_profile(broadcaster_id)
    points_enabled = bot.services.features.is_enabled(broadcaster_id, FeatureName.POINTS)
    return templates.TemplateResponse(
        request=request,
        name="channel/streamer_setup.html",
        context={
            "active_page": "setup", "broadcaster": bot.services.broadcasters.get_broadcasters().get(broadcaster_id),
            "progress": progress, "step": step, "steps": STEPS, "bot_login": bot_login,
            "channel_login": request.session.get(CHANNEL_USER_LOGIN_KEY),
            "points_enabled": points_enabled, "points_alias": profile.points.command_alias if profile else "points",
            "csrf_token": get_csrf_token(request), "moderator_result": request.query_params.get("moderator"),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post(SETUP_URL)
async def update_streamer_setup(
    request: Request, csrf_token: str = Form(...), action: str = Form(...), expected_step: int = Form(...),
):
    broadcaster_id, db, bot = setup_context(request)
    validate_csrf_token(request, csrf_token)
    await initialize_setup(db, broadcaster_id)
    progress = await get_setup(db, broadcaster_id)
    step, status = progress["step"], progress["status"]
    moderator, command = progress["moderator_confirmed"], progress["command_confirmed"]
    destination = SETUP_URL
    if action == "restart":
        step, status, moderator, command = 0, "active", 0, 0
    elif action == "resume" and status == "dismissed":
        status = "active"
    elif status != "active" or step != expected_step:
        return RedirectResponse(SETUP_URL, status_code=303)
    elif action == "dismiss":
        status, destination = "dismissed", "/channel"
    elif action == "back" and step > 0:
        step -= 1
    elif action == "next" and step < len(STEPS) - 1:
        step += 1
    elif action == "confirm-command" and step == 4:
        command, step = 1, 5
    elif action == "finish" and step == len(STEPS) - 1:
        status, destination = "finished", "/channel"
    elif action == "check-moderator" and step == 1:
        identity = bot.services.chat_identity.get_state(broadcaster_id)
        bot_id = identity.bot_user_id if identity.connected else bot.bot_id
        try:
            channel = bot.create_partialuser(broadcaster_id)
            async with asyncio.timeout(8):
                moderator = 0
                async for user in channel.fetch_moderators(user_ids=[str(bot_id)], max_results=1):
                    if str(user.id) == str(bot_id):
                        moderator = 1
                        break
            destination += "?moderator=" + ("confirmed" if moderator else "missing")
        except Exception:
            LOGGER.warning("Could not verify setup moderator role for %s", broadcaster_id, exc_info=True)
            return RedirectResponse(SETUP_URL + "?moderator=unavailable", status_code=303)
    else:
        raise HTTPException(status_code=400, detail="That action is unavailable for this setup step.")

    await save_setup(db, progress, step=step, status=status, moderator_confirmed=moderator,
                     command_confirmed=command)
    return RedirectResponse(destination, status_code=303)
