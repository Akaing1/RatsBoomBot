from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from bot.profiles import FeatureName, get_active_profile
from bot.services.engagement.raid_boss import BASIC_WEAPON_TYPES, CRAFTING_RECIPES, OVERCLOCKED_WEAPON_TYPES, SELLABLE_WEAPON_TYPES
from storage.viewer_sessions import claim_viewer_action, create_viewer_session, revoke_viewer_session, valid_viewer_session
from web.admin.auth import get_csrf_token, validate_csrf_token
from web.shared.common import templates
from web.shared.oauth import build_viewer_oauth_url, exchange_code_for_token, fetch_twitch_user
from web.state import get_bot, get_db
from web.viewer.auth import (
    VIEWER_USER_DISPLAY_NAME_KEY,
    VIEWER_OAUTH_NEXT_KEY,
    VIEWER_SERVER_TOKEN_KEY,
    VIEWER_USER_ID_KEY,
    VIEWER_USER_LOGIN_KEY,
    consume_viewer_oauth_state,
    logout_viewer,
    start_viewer_oauth,
    viewer_user_id,
)

router = APIRouter()
PRIVATE_HEADERS = {"Cache-Control": "no-store"}
SHOP_WEAPONS = (*BASIC_WEAPON_TYPES, *OVERCLOCKED_WEAPON_TYPES)
SHOP_RESULTS = {
    "bought": "Weapon purchased. Your inventory and balance are updated.",
    "crafted": "Weapon crafted. Your inventory and balance are updated.",
    "sold": "Weapon sold. Your inventory and balance are updated.",
    "insufficient": "You do not have enough points for that action.",
    "materials": "You need two copies of the previous weapon tier to craft that item.",
    "not_owned": "You do not own that weapon in this channel.",
    "equipped": "Your last copy is equipped. Unequip it in chat before selling.",
    "invalid": "That item is not available for this action.",
    "unsellable": "That weapon cannot be sold.",
}


@router.get("/me/connect")
async def connect_viewer(request: Request, next: str = ""):
    state = start_viewer_oauth(request, next)
    return RedirectResponse(build_viewer_oauth_url(state), headers=PRIVATE_HEADERS)


@router.get("/oauth/viewer/connect")
async def viewer_oauth_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if not consume_viewer_oauth_state(request, state):
        return HTMLResponse("Viewer sign-in could not be verified. Please try again.", status_code=400, headers=PRIVATE_HEADERS)

    destination = request.session.pop(VIEWER_OAUTH_NEXT_KEY, "/me")
    if error or not code:
        return RedirectResponse("/", status_code=303, headers=PRIVATE_HEADERS)

    try:
        token = await exchange_code_for_token(code=code, redirect_uri=settings.VIEWER_REDIRECT_URI)
        user = await fetch_twitch_user(token.access_token)
    except Exception:
        return HTMLResponse("Twitch sign-in is temporarily unavailable. Please try again.", status_code=503, headers=PRIVATE_HEADERS)

    runtime_db = get_db()
    if runtime_db is None:
        return HTMLResponse("Chatter sign-in is temporarily unavailable.", status_code=503, headers=PRIVATE_HEADERS)
    try:
        server_token = await create_viewer_session(runtime_db, user.user_id)
        await revoke_viewer_session(runtime_db, request.session.get(VIEWER_SERVER_TOKEN_KEY))
    except Exception:
        return HTMLResponse("Chatter sign-in is temporarily unavailable.", status_code=503, headers=PRIVATE_HEADERS)

    # Twitch tokens are used only for identity lookup, then discarded.
    logout_viewer(request)
    request.session[VIEWER_USER_ID_KEY] = user.user_id
    request.session[VIEWER_USER_LOGIN_KEY] = user.login
    request.session[VIEWER_USER_DISPLAY_NAME_KEY] = user.display_name
    request.session[VIEWER_SERVER_TOKEN_KEY] = server_token
    return RedirectResponse(destination, status_code=303, headers=PRIVATE_HEADERS)


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


async def shop_context(request: Request, channel_name: str):
    user_id = viewer_user_id(request)
    if user_id is None:
        return RedirectResponse(f"/me/connect?next=/me/channels/{channel_name}/shop", status_code=303, headers=PRIVATE_HEADERS)

    runtime_db = get_db()
    token = request.session.get(VIEWER_SERVER_TOKEN_KEY)
    if runtime_db is None:
        raise HTTPException(503, "Chatter shop is temporarily unavailable.")
    if not await valid_viewer_session(runtime_db, user_id, token):
        return RedirectResponse(f"/me/connect?next=/me/channels/{channel_name}/shop", status_code=303, headers=PRIVATE_HEADERS)

    runtime_bot = get_bot()
    if runtime_bot is None or runtime_bot.services is None:
        raise HTTPException(503, "Chatter shop is temporarily unavailable.")

    services = runtime_bot.services
    profile = await services.chatter_stats.get_channel_profile(user_id, channel_name)
    if profile is None or str(profile["identity"]["user_id"]) != user_id:
        raise HTTPException(404, "No channel activity found for this account.")

    broadcaster_id = str(profile["channel"]["id"])
    channel_profile = get_active_profile(broadcaster_id)
    if (channel_profile is None or not channel_profile.raid_bosses.enabled
            or not services.features.is_enabled(broadcaster_id, FeatureName.RAID_BOSSES)
            or not services.features.is_enabled(broadcaster_id, FeatureName.POINTS)):
        raise HTTPException(404, "Raid shop is unavailable for this channel.")

    return runtime_db, services, profile, channel_profile.raid_bosses, token


@router.get("/me/channels/{channel_name}/shop")
async def viewer_raid_shop(request: Request, channel_name: str):
    context = await shop_context(request, channel_name)
    if isinstance(context, RedirectResponse):
        return context

    _, _, profile, _, _ = context
    return RedirectResponse(f"/chatters/{profile['identity']['login']}/channels/{profile['channel']['login']}?tab=shop", status_code=303, headers=PRIVATE_HEADERS)


@router.post("/me/channels/{channel_name}/shop/{action}")
async def viewer_raid_action(request: Request, channel_name: str, action: str, item_id: str = Form(...), csrf_token: str = Form(...)):
    validate_csrf_token(request, csrf_token)
    context = await shop_context(request, channel_name)
    if isinstance(context, RedirectResponse):
        return context

    runtime_db, services, profile, config, token = context
    allowed = {"buy": SHOP_WEAPONS, "craft": CRAFTING_RECIPES, "sell": SELLABLE_WEAPON_TYPES}
    if action not in allowed or item_id not in allowed[action]:
        raise HTTPException(400, "That item is not available for this action.")
    user_id = str(profile["identity"]["user_id"])
    if not await claim_viewer_action(runtime_db, user_id, token):
        raise HTTPException(429, "Please wait before making another shop request.")

    broadcaster_id = str(profile["channel"]["id"])
    username = str(profile["identity"]["login"])
    raid_bosses = services.raid_bosses
    if action == "buy":
        outcome = await raid_bosses.buy(broadcaster_id, user_id, username, item_id, config)
        result = "bought" if outcome == "purchased" else outcome or "invalid"
    elif action == "craft":
        outcome = await raid_bosses.craft(broadcaster_id, user_id, username, item_id, config)
        result = "crafted" if outcome.startswith("crafted:") else outcome
    else:
        outcome = await raid_bosses.sell(broadcaster_id, user_id, username, item_id, config)
        result = "sold" if outcome.startswith("sold:") else outcome

    if result not in SHOP_RESULTS:
        result = "invalid"
    return RedirectResponse(f"/chatters/{profile['identity']['login']}/channels/{profile['channel']['login']}?tab=shop&result={result}", status_code=303, headers=PRIVATE_HEADERS)


@router.post("/me/logout")
async def sign_out_viewer(request: Request, csrf_token: str = Form(...)):
    validate_csrf_token(request, csrf_token)
    try:
        if (runtime_db := get_db()) is not None:
            await revoke_viewer_session(runtime_db, request.session.get(VIEWER_SERVER_TOKEN_KEY))
    finally:
        logout_viewer(request)
    return RedirectResponse("/", status_code=303, headers=PRIVATE_HEADERS)
