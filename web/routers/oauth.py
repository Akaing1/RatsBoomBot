from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from storage.database import save_token
from web.admin_auth import require_admin
from web.channel_auth import create_channel_oauth_state, login_channel_user, validate_channel_oauth_state
from web.common import build_admin_context, render_error, templates
from web.oauth import build_bot_oauth_url, build_channel_oauth_url, build_public_channel_oauth_url, exchange_code_for_token, fetch_twitch_user
from web.state import get_bot, get_db

router = APIRouter()


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


@router.get("/oauth/channel", response_class=HTMLResponse)
async def oauth_channel_callback(request: Request, code: str | None = None, error: str | None = None):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    if error:
        return await render_error(
            request,
            title="Channel authorization failed",
            message=error,
            status_code=400
        )

    if not code:
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
        name="auth_success.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            title="Channel connected",
            message=f"RatsBoomBot is now connected to {twitch_user.display_name}."
        )
    )


@router.get("/oauth/bot", response_class=HTMLResponse)
async def oauth_bot_callback(request: Request, code: str | None = None, error: str | None = None):
    admin_redirect = await require_admin(request)

    if admin_redirect:
        return admin_redirect

    if error:
        return await render_error(
            request,
            title="Bot authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        return await render_error(
            request,
            title="Bot authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.BOT_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
        runtime_bot = get_bot()
        runtime_db = get_db()

        if runtime_bot is not None:
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
        name="auth_success.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            title="Bot account connected",
            message=f"The bot account {twitch_user.display_name} was connected successfully."
        )
    )


@router.get("/connect", response_class=HTMLResponse)
async def public_connect_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="connect.html",
        context={}
    )


@router.get("/connect/twitch")
async def public_connect_twitch(request: Request):
    state = create_channel_oauth_state(request)
    return RedirectResponse(build_public_channel_oauth_url(state=state))


@router.get("/oauth/channel/connect", response_class=HTMLResponse)
async def public_channel_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if not validate_channel_oauth_state(request, state):
        return await render_error(
            request,
            title="Channel authorization failed",
            message="The Twitch authorization request could not be verified.",
            status_code=400
        )

    if error:
        return await render_error(
            request,
            title="Channel authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        return await render_error(
            request,
            title="Channel authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.PUBLIC_CHANNEL_REDIRECT_URI)
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

        login_channel_user(
            request,
            twitch_user.user_id,
            twitch_user.login,
            twitch_user.display_name
        )

    except Exception as error:
        return await render_error(
            request,
            title="Channel connection failed",
            message=repr(error),
            status_code=500
        )

    return RedirectResponse(url="/channel", status_code=303)
