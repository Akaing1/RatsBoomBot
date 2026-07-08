from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from config.settings import settings

TWITCH_AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


@dataclass
class TwitchTokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: list[str]
    token_type: str


def build_bot_oauth_url(force_verify: bool = True) -> str:
    return _build_oauth_url(
        redirect_uri=settings.BOT_REDIRECT_URI,
        scopes=settings.BOT_SCOPES,
        force_verify=force_verify
    )


def build_channel_oauth_url(force_verify: bool = True) -> str:
    return _build_oauth_url(
        redirect_uri=settings.CHANNEL_REDIRECT_URI,
        scopes=settings.CHANNEL_SCOPES,
        force_verify=force_verify
    )


def _build_oauth_url(*, redirect_uri: str, scopes: str, force_verify: bool) -> str:
    params = {
        "client_id": settings.CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
    }

    if force_verify:
        params["force_verify"] = "true"

    return f"{TWITCH_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(*, code: str, redirect_uri: str) -> TwitchTokenResponse:
    data = {
        "client_id": settings.CLIENT_ID,
        "client_secret": settings.CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(TWITCH_TOKEN_URL, data=data)

    response.raise_for_status()
    payload = response.json()

    return TwitchTokenResponse(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
        expires_in=payload["expires_in"],
        scope=payload.get("scope", []),
        token_type=payload["token_type"]
    )
