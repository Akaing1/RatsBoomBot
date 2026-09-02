from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from storage.database import delete_token, save_token
from web.admin.auth import validate_csrf_token
from web.channel.auth import (
    CHANNEL_USER_ID_KEY,
    consume_custom_bot_oauth_state,
    create_channel_oauth_state,
    create_custom_bot_oauth_state,
    has_custom_bot_oauth_state,
    login_channel_user,
    validate_channel_oauth_state
)
from web.shared.common import render_error, templates
from web.shared.oauth import build_public_channel_oauth_url, build_public_custom_bot_oauth_url, exchange_code_for_token, fetch_twitch_user
from web.state import get_bot, get_db

router = APIRouter()


def customization_redirect(result: str, message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/channel/customization?identity_result={result}&identity_message={quote_plus(message)}", status_code=303)


@router.get("/connect", response_class=HTMLResponse)
async def public_connect_page(request: Request):
    return templates.TemplateResponse(request=request, name="channel/connect.html", context={})


@router.get("/connect/twitch")
async def public_connect_twitch(request: Request):
    state = create_channel_oauth_state(request)
    return RedirectResponse(build_public_channel_oauth_url(state=state))


@router.get("/channel/custom-bot/connect")
async def connect_channel_custom_bot(request: Request):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return customization_redirect("error", "The bot runtime is unavailable.")

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    identity = services.chat_identity.get_state(broadcaster_id)

    if broadcaster is None:
        return RedirectResponse(url="/connect", status_code=303)

    if not identity.premium_enabled:
        return customization_redirect("error", "Premium custom bot access is not enabled for this channel.")

    state = create_custom_bot_oauth_state(request, broadcaster_id)
    return RedirectResponse(build_public_custom_bot_oauth_url(state=state))


@router.post("/channel/custom-bot/disconnect")
async def disconnect_channel_custom_bot(request: Request, csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    runtime_db = get_db()

    if runtime_bot is None or runtime_bot.services is None or runtime_db is None:
        return customization_redirect("error", "The bot runtime is unavailable.")

    services = runtime_bot.services

    if services.broadcasters.get_broadcasters().get(str(broadcaster_id)) is None:
        return RedirectResponse(url="/connect", status_code=303)

    previous_user_id = await services.chat_identity.disconnect(broadcaster_id)

    if previous_user_id and not services.chat_identity.is_custom_bot(previous_user_id):
        await delete_token(runtime_db, previous_user_id)

    return customization_redirect("success", "The custom bot account was disconnected. RatsBoomBot is active for this channel again.")


@router.get("/oauth/channel/connect", response_class=HTMLResponse)
async def public_channel_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if has_custom_bot_oauth_state(request):
        return await custom_bot_callback(request, code, state, error)

    if not validate_channel_oauth_state(request, state):
        return await render_error(request, title="Channel authorization failed", message="The Twitch authorization request could not be verified.", status_code=400)

    if error:
        return await render_error(request, title="Channel authorization failed", message=error, status_code=400)

    if not code:
        return await render_error(request, title="Channel authorization failed", message="No authorization code was provided.", status_code=400)

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.PUBLIC_CHANNEL_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
        runtime_bot = get_bot()
        runtime_db = get_db()

        if runtime_bot is not None:
            await runtime_bot.onboard_broadcaster(user_id=twitch_user.user_id, token=token_response.access_token, refresh=token_response.refresh_token)
        elif runtime_db is not None:
            await save_token(db=runtime_db, user_id=twitch_user.user_id, token=token_response.access_token, refresh=token_response.refresh_token)
        else:
            return await render_error(request, title="Runtime unavailable", message="The RatsBoomBot runtime is not available.", status_code=503)

        login_channel_user(request, twitch_user.user_id, twitch_user.login, twitch_user.display_name)
    except Exception as error:
        return await render_error(request, title="Channel connection failed", message=repr(error), status_code=500)

    return RedirectResponse(url="/channel", status_code=303)


async def custom_bot_callback(request: Request, code: str | None, state: str | None, error: str | None):
    broadcaster_id = consume_custom_bot_oauth_state(request, state)
    session_broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if broadcaster_id is None or str(session_broadcaster_id or "") != broadcaster_id:
        return await render_error(request, title="Custom bot authorization failed", message="The custom bot authorization session was invalid or expired.", status_code=400)

    if error:
        return customization_redirect("error", f"Twitch authorization failed: {error}")

    if not code:
        return customization_redirect("error", "No authorization code was provided.")

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.PUBLIC_CHANNEL_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
        runtime_bot = get_bot()

        if runtime_bot is None or runtime_bot.services is None:
            return customization_redirect("error", "The bot runtime is unavailable.")

        identity = runtime_bot.services.chat_identity.get_state(broadcaster_id)

        if not identity.premium_enabled:
            return customization_redirect("error", "Premium custom bot access is no longer enabled for this channel.")

        await runtime_bot.onboard_custom_bot_account(
            broadcaster_id=broadcaster_id,
            user_id=twitch_user.user_id,
            token=token_response.access_token,
            refresh=token_response.refresh_token,
            login=twitch_user.login,
            display_name=twitch_user.display_name
        )
    except ValueError as error:
        return customization_redirect("error", str(error))
    except Exception:
        return customization_redirect("error", "The custom bot account could not be connected. Please try again.")

    return customization_redirect("success", f"{twitch_user.display_name} is now the custom bot identity for this channel.")
