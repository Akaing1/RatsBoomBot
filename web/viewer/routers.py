from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.shared.common import templates
from web.shared.oauth import build_viewer_oauth_url, exchange_code_for_token, fetch_twitch_user
from web.state import get_bot
from web.viewer.auth import (
    VIEWER_USER_DISPLAY_NAME_KEY,
    VIEWER_USER_ID_KEY,
    VIEWER_USER_LOGIN_KEY,
    consume_viewer_oauth_state,
    logout_viewer,
    start_viewer_oauth,
    viewer_user_id,
)

router = APIRouter()
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


@router.get("/me/connect")
async def connect_viewer(request: Request):
    state = start_viewer_oauth(request)
    return RedirectResponse(build_viewer_oauth_url(state), headers=PRIVATE_HEADERS)


@router.get("/oauth/viewer/connect")
async def viewer_oauth_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if not consume_viewer_oauth_state(request, state):
        return HTMLResponse("Viewer sign-in could not be verified. Please try again.", status_code=400, headers=PRIVATE_HEADERS)

    if error or not code:
        return RedirectResponse("/", status_code=303, headers=PRIVATE_HEADERS)

    try:
        token = await exchange_code_for_token(code=code, redirect_uri=settings.VIEWER_REDIRECT_URI)
        user = await fetch_twitch_user(token.access_token)
    except Exception:
        return HTMLResponse("Twitch sign-in is temporarily unavailable. Please try again.", status_code=503, headers=PRIVATE_HEADERS)

    # The identity token is used only for this lookup. It is never saved to the bot's broadcaster token table.
    logout_viewer(request)
    request.session[VIEWER_USER_ID_KEY] = user.user_id
    request.session[VIEWER_USER_LOGIN_KEY] = user.login
    request.session[VIEWER_USER_DISPLAY_NAME_KEY] = user.display_name
    return RedirectResponse("/me", status_code=303, headers=PRIVATE_HEADERS)


@router.get("/me", response_class=HTMLResponse)
async def my_account(request: Request):
    user_id = viewer_user_id(request)
    if user_id is None:
        return RedirectResponse("/me/connect", status_code=303, headers=PRIVATE_HEADERS)

    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        return HTMLResponse("Chatter profiles are temporarily unavailable.", status_code=503, headers=PRIVATE_HEADERS)

    profile = await runtime_bot.services.chatter_stats.get_global_profile(user_id)
    if profile is not None and str(profile["identity"]["user_id"]) == user_id:
        pets = getattr(runtime_bot.services, "pets", None)
        profile["pet"] = await pets.get_equipped_pet(user_id) if pets is not None else None
        return templates.TemplateResponse(
            request=request,
            name="public/chatter_profile.html",
            context={
                "profile": profile,
                "public_base_url": settings.PUBLIC_BASE_URL.rstrip("/"),
                "account_mode": True,
                "viewer_user_id": user_id,
                "csrf_token": get_csrf_token(request),
            },
            headers=PRIVATE_HEADERS,
        )

    return templates.TemplateResponse(
        request=request,
        name="viewer/empty.html",
        context={
            "display_name": request.session.get(VIEWER_USER_DISPLAY_NAME_KEY, "Chatter"),
            "csrf_token": get_csrf_token(request),
        },
        headers=PRIVATE_HEADERS,
    )


@router.post("/me/logout")
async def sign_out_viewer(request: Request, csrf_token: str = Form(...)):
    validate_csrf_token(request, csrf_token)
    logout_viewer(request)
    return RedirectResponse("/", status_code=303, headers=PRIVATE_HEADERS)
