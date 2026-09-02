import re
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from storage.custom_bot_authorization_repository import consume_custom_bot_authorization_request, create_custom_bot_authorization_request, get_custom_bot_authorization_request
from storage.database import delete_token, save_token
from web.admin.auth import validate_csrf_token
from web.channel.auth import (
    CHANNEL_USER_ID_KEY,
    create_channel_oauth_state,
    login_channel_user,
    validate_channel_oauth_state
)
from web.shared.common import render_error, templates
from web.shared.oauth import build_public_channel_oauth_url, build_public_custom_bot_oauth_url, exchange_code_for_token, fetch_twitch_user
from web.state import get_bot, get_db

router = APIRouter()


def customization_redirect(result: str, message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/channel/customization?identity_result={result}&identity_message={quote_plus(message)}", status_code=303)


def render_custom_bot_result(request: Request, title: str, message: str, *, success: bool = False, status_code: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="channel/custom_bot_result.html", context={"title": title, "message": message, "success": success}, status_code=status_code)


@router.get("/connect", response_class=HTMLResponse)
async def public_connect_page(request: Request):
    return templates.TemplateResponse(request=request, name="channel/connect.html", context={})


@router.get("/connect/twitch")
async def public_connect_twitch(request: Request):
    state = create_channel_oauth_state(request)
    return RedirectResponse(build_public_channel_oauth_url(state=state))


@router.get("/channel/custom-bot/connect")
async def connect_channel_custom_bot(request: Request):
    return RedirectResponse(url="/channel/customization", status_code=303)


@router.post("/channel/custom-bot/connect", response_class=HTMLResponse)
async def create_channel_custom_bot_link(request: Request, bot_login: str = Form(...), csrf_token: str = Form(...)):
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)

    if not broadcaster_id:
        return RedirectResponse(url="/connect", status_code=303)

    validate_csrf_token(request, csrf_token)
    runtime_bot = get_bot()
    runtime_db = get_db()

    if runtime_bot is None or runtime_bot.services is None or runtime_db is None:
        return customization_redirect("error", "The bot runtime is unavailable.")

    services = runtime_bot.services
    broadcaster = services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    identity = services.chat_identity.get_state(broadcaster_id)

    if broadcaster is None:
        return RedirectResponse(url="/connect", status_code=303)

    if not identity.premium_enabled:
        return customization_redirect("error", "Premium custom bot access is not enabled for this channel.")

    normalized_login = bot_login.strip().lstrip("@").lower()

    if not re.fullmatch(r"[a-z0-9_]{3,25}", normalized_login):
        return customization_redirect("error", "Enter a valid Twitch username for the dedicated bot account.")

    try:
        bot_user = await runtime_bot.fetch_user(login=normalized_login)
    except Exception:
        return customization_redirect("error", "Twitch could not verify that bot account. Please try again.")

    if bot_user is None:
        return customization_redirect("error", f"Twitch account @{normalized_login} was not found.")

    try:
        assigned_broadcaster_id = services.chat_identity.custom_bot_broadcaster_id(str(bot_user.id))

        if str(bot_user.id) in {str(broadcaster_id), str(runtime_bot.bot_id)}:
            raise ValueError("Choose a dedicated Twitch bot account, not the broadcaster or RatsBoomBot account.")

        if assigned_broadcaster_id is not None and assigned_broadcaster_id != str(broadcaster_id):
            raise ValueError("That Twitch account is already connected as another channel's custom bot.")
    except ValueError as error:
        return customization_redirect("error", str(error))

    state = await create_custom_bot_authorization_request(
        runtime_db,
        broadcaster_id,
        str(bot_user.id),
        str(bot_user.name),
        str(bot_user.display_name)
    )
    authorization_url = f"{settings.DASHBOARD_BASE_URL.rstrip('/')}/custom-bot/authorize/{state}"

    return templates.TemplateResponse(
        request=request,
        name="channel/custom_bot_link.html",
        context={
            "active_page": "customization",
            "authorization_url": authorization_url,
            "bot_display_name": bot_user.display_name,
            "bot_login": bot_user.name,
            "csrf_token": csrf_token
        }
    )


@router.get("/custom-bot/authorize/{state}")
async def authorize_channel_custom_bot(state: str):
    runtime_db = get_db()

    if runtime_db is None:
        return RedirectResponse(url="/connect", status_code=303)

    authorization = await get_custom_bot_authorization_request(runtime_db, state)

    if authorization is None:
        return RedirectResponse(url="/custom-bot/authorization-expired", status_code=303)

    return RedirectResponse(build_public_custom_bot_oauth_url(state=state))


@router.get("/custom-bot/authorization-expired", response_class=HTMLResponse)
async def expired_custom_bot_authorization(request: Request):
    return render_custom_bot_result(request, "Authorization link expired", "This custom bot authorization link is invalid, expired, or has already been used. Ask the broadcaster to generate a new link.", status_code=400)


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
    if state and state.startswith("custom_bot_"):
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
    runtime_db = get_db()

    if runtime_db is None:
        return render_custom_bot_result(request, "Authorization unavailable", "The RatsBoomBot runtime is unavailable. Ask the broadcaster to generate a new link later.", status_code=503)

    authorization = await consume_custom_bot_authorization_request(runtime_db, state)

    if authorization is None:
        return render_custom_bot_result(request, "Authorization link expired", "This custom bot authorization link is invalid, expired, or has already been used. Ask the broadcaster to generate a new link.", status_code=400)

    if error:
        return render_custom_bot_result(request, "Authorization cancelled", f"Twitch did not authorize the custom bot account: {error}", status_code=400)

    if not code:
        return render_custom_bot_result(request, "Authorization failed", "Twitch did not provide an authorization code. Ask the broadcaster to generate a new link.", status_code=400)

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.PUBLIC_CHANNEL_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
        runtime_bot = get_bot()

        if runtime_bot is None or runtime_bot.services is None:
            return render_custom_bot_result(request, "Authorization unavailable", "The RatsBoomBot runtime is unavailable. Ask the broadcaster to generate a new link later.", status_code=503)

        if twitch_user.user_id != authorization.expected_bot_user_id:
            return render_custom_bot_result(
                request,
                "Wrong Twitch account",
                f"This link was created for @{authorization.expected_bot_login}, but Twitch authorized @{twitch_user.login}. No account was connected. Ask the broadcaster to generate a new link and authorize the expected bot account.",
                status_code=400
            )

        identity = runtime_bot.services.chat_identity.get_state(authorization.broadcaster_id)

        if not identity.premium_enabled:
            return render_custom_bot_result(request, "Premium access unavailable", "Premium custom bot access is no longer enabled for this channel.", status_code=403)

        await runtime_bot.onboard_custom_bot_account(
            broadcaster_id=authorization.broadcaster_id,
            user_id=twitch_user.user_id,
            token=token_response.access_token,
            refresh=token_response.refresh_token,
            login=twitch_user.login,
            display_name=twitch_user.display_name
        )
    except ValueError as error:
        return render_custom_bot_result(request, "Custom bot connection failed", str(error), status_code=400)
    except Exception:
        return render_custom_bot_result(request, "Custom bot connection failed", "The custom bot account could not be connected. Ask the broadcaster to generate a new link and try again.", status_code=500)

    return render_custom_bot_result(request, "Custom bot connected", f"{twitch_user.display_name} is now connected as the custom bot identity. You may close this window.", success=True)
