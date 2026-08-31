import secrets

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from storage.database import save_token
from web.admin.auth import require_admin, require_owner
from web.shared.common import build_admin_context, render_error, templates
from web.shared.oauth import build_bot_oauth_url, build_channel_oauth_url, exchange_code_for_token, fetch_twitch_user
from web.state import get_bot, get_db

router = APIRouter()
CUSTOM_BOT_OAUTH_STATE_KEY = "custom_bot_oauth_state"
CUSTOM_BOT_BROADCASTER_KEY = "custom_bot_broadcaster_id"


def clear_custom_bot_oauth(request: Request) -> None:
    request.session.pop(CUSTOM_BOT_OAUTH_STATE_KEY, None)
    request.session.pop(CUSTOM_BOT_BROADCASTER_KEY, None)


@router.get("/connect/channel")
async def connect_channel(request: Request):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    return RedirectResponse(build_channel_oauth_url())


@router.get("/connect/bot")
async def connect_bot(request: Request):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    return RedirectResponse(build_bot_oauth_url())


@router.get("/channels/{broadcaster_id}/custom-bot/connect")
async def connect_custom_bot(request: Request, broadcaster_id: str):
    owner_redirect = await require_owner(request)

    if owner_redirect:
        return owner_redirect

    runtime_bot = get_bot()

    if runtime_bot is None or runtime_bot.services is None:
        return await render_error(request, active_page="channels", title="Runtime unavailable", message="The RatsBoomBot runtime is not available.", status_code=503)

    state = runtime_bot.services.chat_identity.get_state(broadcaster_id)

    if not state.premium_enabled:
        return await render_error(request, active_page="channels", title="Premium identity unavailable", message="Enable premium custom identity access for this channel first.", status_code=400)

    oauth_state = secrets.token_urlsafe(32)
    request.session[CUSTOM_BOT_OAUTH_STATE_KEY] = oauth_state
    request.session[CUSTOM_BOT_BROADCASTER_KEY] = str(broadcaster_id)
    return RedirectResponse(build_bot_oauth_url(state=oauth_state))


@router.get("/oauth/channel", response_class=HTMLResponse)
async def oauth_channel_callback(request: Request, code: str | None = None, error: str | None = None):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    if error:
        clear_custom_bot_oauth(request)
        return await render_error(
            request,
            title="Channel authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        clear_custom_bot_oauth(request)
        return await render_error(
            request,
            title="Channel authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.CHANNEL_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
        runtime_bot = get_bot()
        runtime_db = get_db()

        if runtime_bot is not None:
            await runtime_bot.onboard_broadcaster(
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )
        elif runtime_db is not None:
            await save_token(
                db=runtime_db,
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )
        else:
            return await render_error(
                request,
                title="Runtime unavailable",
                message="The RatsBoomBot runtime is not available.",
                status_code=503
            )
    except Exception as error:
        return await render_error(
            request,
            title="Channel connection failed",
            message=repr(error),
            status_code=500
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/auth_success.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            title="Channel connected",
            message=f"RatsBoomBot is now connected to {twitch_user.display_name}."
        )
    )


@router.get("/oauth/bot", response_class=HTMLResponse)
async def oauth_bot_callback(request: Request, code: str | None = None, error: str | None = None, state: str | None = None):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    if error:
        clear_custom_bot_oauth(request)
        return await render_error(
            request,
            title="Bot authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        clear_custom_bot_oauth(request)
        return await render_error(
            request,
            title="Bot authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    expected_custom_state = request.session.get(CUSTOM_BOT_OAUTH_STATE_KEY)
    custom_broadcaster_id = request.session.get(CUSTOM_BOT_BROADCASTER_KEY)
    custom_connection = bool(expected_custom_state or custom_broadcaster_id)

    if custom_connection and (not state or not expected_custom_state or not secrets.compare_digest(state, expected_custom_state) or not custom_broadcaster_id):
        clear_custom_bot_oauth(request)
        return await render_error(request, active_page="channels", title="Custom bot authorization failed", message="The custom bot authorization session was invalid or expired.", status_code=400)

    clear_custom_bot_oauth(request)

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.BOT_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
        runtime_bot = get_bot()
        runtime_db = get_db()

        if custom_connection and runtime_bot is not None and runtime_bot.services is not None:
            await runtime_bot.onboard_custom_bot_account(
                broadcaster_id=str(custom_broadcaster_id),
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token,
                login=twitch_user.login,
                display_name=twitch_user.display_name
            )
        elif custom_connection:
            return await render_error(request, active_page="channels", title="Runtime unavailable", message="The bot must be running to connect a custom identity.", status_code=503)
        elif runtime_bot is not None:
            await runtime_bot.onboard_bot_account(
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )
        elif runtime_db is not None:
            await save_token(
                db=runtime_db,
                user_id=twitch_user.user_id,
                token=token_response.access_token,
                refresh=token_response.refresh_token
            )
        else:
            return await render_error(
                request,
                title="Runtime unavailable",
                message="The RatsBoomBot runtime is not available.",
                status_code=503
            )
    except Exception as error:
        return await render_error(
            request,
            title="Bot connection failed",
            message=repr(error),
            status_code=500
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/auth_success.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            title="Custom bot connected" if custom_connection else "Bot account connected",
            message=f"{twitch_user.display_name} is now the custom chat identity for this channel." if custom_connection else f"The bot account {twitch_user.display_name} was connected successfully."
        )
    )
