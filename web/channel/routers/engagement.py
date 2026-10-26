"""Dashboard poll/prediction creation and recent Twitch history."""

import json
import logging
import re
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from twitchio.http import Route

from web.admin.auth import validate_csrf_token
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.state import get_bot

router = APIRouter()
LOGGER = logging.getLogger("RatBoomBot")
LIMITS = {"polls": (60, 5, 15), "predictions": (45, 10, 30)}


def connected_channel(request):
    user_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not user_id:
        return None, None, JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    bot = get_bot()
    if bot is None or bot.services is None:
        return None, None, JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    user_id = str(user_id)
    if user_id not in bot.services.broadcasters.get_broadcasters():
        return None, None, JSONResponse({"detail": "Connected channel not found."}, status_code=404)
    return bot, user_id, None


def twitch_error(error, kind, *, creating=False, managing=False):
    status = getattr(error, "status", None)
    if status in {401, 403}:
        detail = f"Reconnect Twitch to grant permission to manage {kind}. Twitch also requires an eligible channel."
    elif status == 429:
        detail = "Twitch's request limit was reached. Try again shortly."
    elif status in {400, 409}:
        detail = "Twitch rejected this change. Refresh the summary to check its current state." if managing else f"Twitch rejected this request. Check whether a {kind[:-1]} is already active."
    elif managing:
        detail = "Could not confirm the change. Refresh the summary or check Twitch before retrying."
    elif creating:
        detail = "Could not confirm creation. Check Twitch before trying again to avoid a duplicate."
    else:
        detail = f"Recent {kind} could not be loaded."
    LOGGER.warning("[Dashboard] %s request failed (status %s).", kind, status)
    return JSONResponse({"detail": detail}, status_code=status if status in {400, 401, 403, 409, 429} else 502)


@router.get("/channel/api/engagement/{kind}")
async def recent_engagement(request: Request, kind: str):
    bot, user_id, error = connected_channel(request)
    if error is not None:
        return error
    if kind not in LIMITS:
        return JSONResponse({"detail": "Unknown type."}, status_code=400)
    try:
        payload = await bot._http.request_json(Route("GET", kind, token_for=user_id,
            params={"broadcaster_id": user_id, "first": 20}))
        items = []
        for item in payload.get("data", []):
            options = item.get("choices" if kind == "polls" else "outcomes", [])
            items.append({"id": item["id"], "title": item["title"],
                "choices": [option["title"] for option in options],
                "duration": item.get("duration" if kind == "polls" else "prediction_window", 120),
                "status": item.get("status", ""), "created_at": item.get("created_at", item.get("started_at", ""))})
            if kind == "polls":
                items[-1].update(channel_points_voting_enabled=bool(item.get("channel_points_voting_enabled", False)),
                    channel_points_per_vote=item.get("channel_points_per_vote", 0))
        return JSONResponse({"items": items})
    except Exception as error:
        return twitch_error(error, kind)


@router.post("/channel/api/engagement/{kind}")
async def create_engagement(request: Request, kind: str, title: str = Form(...),
                            choices: str = Form(...), duration: int = Form(...), csrf_token: str = Form(...),
                            channel_points_voting_enabled: Annotated[bool, Form()] = False,
                            channel_points_per_vote: Annotated[int | None, Form()] = None):
    bot, user_id, error = connected_channel(request)
    if error is not None:
        return error
    validate_csrf_token(request, csrf_token)
    if kind not in LIMITS:
        return JSONResponse({"detail": "Unknown type."}, status_code=400)
    title_limit, choice_limit, minimum_duration = LIMITS[kind]
    try:
        if len(choices) > 5000:
            raise ValueError
        options = json.loads(choices)
        if not isinstance(options, list) or not 2 <= len(options) <= choice_limit:
            raise ValueError
        if any(not isinstance(option, str) or not 1 <= len(option.strip()) <= 25 for option in options):
            raise ValueError
        options = [option.strip() for option in options]
        if len(set(option.casefold() for option in options)) != len(options):
            raise ValueError
        if not 1 <= len(title.strip()) <= title_limit or not minimum_duration <= duration <= 1800:
            raise ValueError
    except (ValueError, TypeError):
        return JSONResponse({"detail": f"Use a title up to {title_limit} characters, 2–{choice_limit} distinct choices up to 25 characters, and {minimum_duration}–1800 seconds."}, status_code=400)
    body = {"broadcaster_id": user_id, "title": title.strip(),
        "choices" if kind == "polls" else "outcomes": [{"title": option} for option in options],
        "duration" if kind == "polls" else "prediction_window": duration}
    if channel_points_voting_enabled:
        if kind != "polls" or not isinstance(channel_points_per_vote, int) or isinstance(channel_points_per_vote, bool) or not 1 <= channel_points_per_vote <= 1_000_000:
            return JSONResponse({"detail": "Additional votes are only available for polls. Set a cost of 1–1,000,000 Channel Points per additional vote."}, status_code=400)
        body["channel_points_per_vote"] = channel_points_per_vote
    if kind == "polls":
        body["channel_points_voting_enabled"] = channel_points_voting_enabled
    try:
        payload = await bot._http.request_json(Route("POST", kind, token_for=user_id, json=body))
        return JSONResponse({"item": engagement_summary(payload["data"][0], kind)}, status_code=201)
    except Exception as error:
        return twitch_error(error, kind, creating=True)


def engagement_summary(item, kind):
    """Expose aggregate results only, never prediction participants or identities."""
    def count(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

    return {"id": str(item["id"]), "kind": kind, "title": str(item.get("title", "")),
        "status": str(item.get("status", "ACTIVE")),
        "duration": item.get("duration" if kind == "polls" else "prediction_window", 120),
        "created_at": item.get("created_at", item.get("started_at", "")),
        "ended_at": item.get("ended_at"), "locked_at": item.get("locked_at"),
        "winning_outcome_id": item.get("winning_outcome_id"),
        "options": [{"id": str(option.get("id", "")), "title": str(option.get("title", "")),
            "votes": count(option.get("votes" if kind == "polls" else "users")),
            "points": count(option.get("channel_points"))}
            for option in item.get("choices" if kind == "polls" else "outcomes", [])]}


def valid_engagement_id(value):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value))


async def fetch_engagement(bot, user_id, kind, item_id):
    payload = await bot._http.request_json(Route("GET", kind, token_for=user_id,
        params={"broadcaster_id": user_id, "id": item_id}))
    return next((item for item in payload.get("data", []) if str(item.get("id")) == item_id), None)


@router.get("/channel/api/engagement/{kind}/{item_id}")
async def get_engagement(request: Request, kind: str, item_id: str):
    bot, user_id, error = connected_channel(request)
    if error is not None:
        return error
    if kind not in LIMITS or not valid_engagement_id(item_id):
        return JSONResponse({"detail": "Invalid poll or prediction."}, status_code=400)
    try:
        item = await fetch_engagement(bot, user_id, kind, item_id)
        if item is None:
            return JSONResponse({"detail": "Poll or prediction not found for this channel."}, status_code=404)
        return JSONResponse({"item": engagement_summary(item, kind)})
    except Exception as error:
        return twitch_error(error, kind, managing=True)


@router.post("/channel/api/engagement/{kind}/{item_id}/action")
async def manage_engagement(request: Request, kind: str, item_id: str, action: str = Form(...),
                            csrf_token: str = Form(...), winning_outcome_id: Annotated[str, Form()] = ""):
    bot, user_id, error = connected_channel(request)
    if error is not None:
        return error
    validate_csrf_token(request, csrf_token)
    if kind not in LIMITS or not valid_engagement_id(item_id) or action not in {"close", "resolve", "delete"}:
        return JSONResponse({"detail": "Invalid action."}, status_code=400)
    if action == "resolve" and (kind != "predictions" or not valid_engagement_id(winning_outcome_id)):
        return JSONResponse({"detail": "Select a prediction outcome."}, status_code=400)
    try:
        item = await fetch_engagement(bot, user_id, kind, item_id)
        if item is None:
            return JSONResponse({"detail": "Poll or prediction not found for this channel."}, status_code=404)
        active = item.get("status") == "ACTIVE"
        unsettled = active or (kind == "predictions" and item.get("status") == "LOCKED")
        if action == "delete" and not unsettled:
            # Twitch has no hard-delete endpoint for completed history.
            return JSONResponse({"item": engagement_summary(item, kind), "dismissed": True})
        if (action == "close" and not active) or not unsettled:
            return JSONResponse({"detail": "This item has already changed. Refresh its summary."}, status_code=409)
        body = {"broadcaster_id": user_id, "id": item_id}
        if action == "resolve":
            if not any(str(option.get("id")) == winning_outcome_id for option in item.get("outcomes", [])):
                return JSONResponse({"detail": "This outcome does not belong to the prediction."}, status_code=400)
            body.update(status="RESOLVED", winning_outcome_id=winning_outcome_id)
        elif action == "delete":
            body["status"] = "ARCHIVED" if kind == "polls" else "CANCELED"
        else:
            body["status"] = "TERMINATED" if kind == "polls" else "LOCKED"
        payload = await bot._http.request_json(Route("PATCH", kind, token_for=user_id, json=body))
        return JSONResponse({"item": engagement_summary(payload["data"][0], kind), "dismissed": action == "delete"})
    except Exception as error:
        return twitch_error(error, kind, managing=True)
