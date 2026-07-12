from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from storage.database import save_token
from web.admin_auth import require_admin
from web.common import (
    build_admin_context,
    render_error,
    templates
)
from web.oauth import (
    build_bot_oauth_url,
    build_channel_oauth_url,
    exchange_code_for_token,
    fetch_twitch_user
)
from web.state import get_bot, get_db

router = APIRouter()


@router.get("/connect/channel")
async def connect_channel(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    return RedirectResponse(
        build_channel_oauth_url()
    )


@router.get("/connect/bot")
async def connect_bot(request: Request):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    return RedirectResponse(
        build_bot_oauth_url()
    )


@router.get("/oauth/channel", response_class=HTMLResponse)
async def oauth_channel_callback(request: Request,code: str | None = None,error: str | None = None):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    if error:
        return render_error(
            request,
            title="Channel authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        return render_error(
            request,
            title="Channel authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    try:
        token_response = await exchange_code_for_token(
            code=code,
            redirect_uri=settings.CHANNEL_REDIRECT_URI
        )

        twitch_user = await fetch_twitch_user(
            token_response.access_token
        )

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
            return render_error(
                request,
                title="Runtime unavailable",
                message="The RatsBoomBot runtime is not available.",
                status_code=503
            )

    except Exception as exc:
        return render_error(
            request,
            title="Channel connection failed",
            message=repr(exc),
            status_code=500
        )

    return templates.TemplateResponse(
        request=request,
        name="auth_success.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            title="Channel connected",
            message=(
                f"RatsBoomBot is now connected to "
                f"{twitch_user.display_name}."
            )
        )
    )


@router.get("/oauth/bot",response_class=HTMLResponse)
async def oauth_bot_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None
):
    admin_redirect = require_admin(request)

    if admin_redirect:
        return admin_redirect

    if error:
        return render_error(
            request,
            title="Bot authorization failed",
            message=error,
            status_code=400
        )

    if not code:
        return render_error(
            request,
            title="Bot authorization failed",
            message="No authorization code was provided.",
            status_code=400
        )

    try:
        token_response = await exchange_code_for_token(
            code=code,
            redirect_uri=settings.BOT_REDIRECT_URI
        )

        twitch_user = await fetch_twitch_user(
            token_response.access_token
        )

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
            return render_error(
                request,
                title="Runtime unavailable",
                message="The RatsBoomBot runtime is not available.",
                status_code=503
            )

    except Exception as exc:
        return render_error(
            request,
            title="Bot connection failed",
            message=repr(exc),
            status_code=500
        )

    return templates.TemplateResponse(
        request=request,
        name="auth_success.html",
        context=build_admin_context(
            request,
            active_page="dashboard",
            title="Bot account connected",
            message=(
                f"The bot account {twitch_user.display_name} "
                f"was connected successfully."
            )
        )
    )
