import logging
import secrets
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from config.settings import settings
from web.admin.auth import validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.shared.youtube_oauth import build_youtube_oauth_url, exchange_youtube_code, fetch_youtube_channel
from web.state import get_bot

router = APIRouter()
LOGGER = logging.getLogger("RatBoomBot")
YOUTUBE_OAUTH_STATE_KEY = "youtube_oauth_state"


def youtube_redirect(result: str, message: str) -> RedirectResponse:
    url = f"/channel/customization?youtube_result={result}&youtube_message={quote_plus(message)}&social_tab=youtube#youtube-integration"
    return RedirectResponse(url=url, status_code=303)


@router.get("/channel/youtube/connect")
async def connect_youtube(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    if not settings.YOUTUBE_CONFIGURED:
        return youtube_redirect("error", "YouTube integration has not been configured on this deployment.")

    state = secrets.token_urlsafe(32)
    request.session[YOUTUBE_OAUTH_STATE_KEY] = state
    return RedirectResponse(build_youtube_oauth_url(state))


@router.get("/oauth/youtube/connect")
async def youtube_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    expected_state = request.session.pop(YOUTUBE_OAUTH_STATE_KEY, None)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        return youtube_redirect("error", "The YouTube authorization request could not be verified.")

    if error:
        return youtube_redirect("error", f"YouTube authorization was cancelled: {error}")

    if not code:
        return youtube_redirect("error", "Google did not provide an authorization code.")

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return youtube_redirect("error", "The bot runtime is unavailable.")

    try:
        token = await exchange_youtube_code(code)
        channel = await fetch_youtube_channel(token.access_token)
        await runtime_bot.services.live_chat.connect_youtube(str(broadcaster_id), channel, token)
    except ValueError as authorization_error:
        return youtube_redirect("error", str(authorization_error))
    except Exception:
        LOGGER.exception("[YouTube OAuth] Failed to connect YouTube for broadcaster %s.", broadcaster_id)
        return youtube_redirect("error", "The YouTube channel could not be connected. Please try again.")

    return youtube_redirect("success", f"Connected YouTube channel {channel.title}.")


@router.post("/channel/youtube/disconnect")
async def disconnect_youtube(request: Request, csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return youtube_redirect("error", "The bot runtime is unavailable.")

    await runtime_bot.services.live_chat.disconnect_youtube(str(broadcaster_id))
    return youtube_redirect("success", "The YouTube channel was disconnected.")


@router.post("/channel/widgets/regenerate")
async def regenerate_widget_urls(request: Request, csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return youtube_redirect("error", "The bot runtime is unavailable.")

    await runtime_bot.services.live_chat.regenerate_widget_token(str(broadcaster_id))
    return youtube_redirect("success", "New OBS browser-source URLs were generated. The previous URLs no longer work.")
