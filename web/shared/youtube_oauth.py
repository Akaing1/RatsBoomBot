from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from config.settings import settings

YOUTUBE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


@dataclass(frozen=True)
class YouTubeTokenResponse:
    access_token: str
    refresh_token: str
    expires_at: str


@dataclass(frozen=True)
class YouTubeChannel:
    channel_id: str
    title: str


def build_youtube_oauth_url(state: str) -> str:
    query = urlencode({
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_READONLY_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state
    })
    return f"{YOUTUBE_AUTHORIZE_URL}?{query}"


async def exchange_youtube_code(code: str) -> YouTubeTokenResponse:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            YOUTUBE_TOKEN_URL,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.YOUTUBE_REDIRECT_URI
            }
        )
    response.raise_for_status()
    payload = response.json()
    refresh_token = payload.get("refresh_token")

    if not refresh_token:
        raise ValueError("Google did not provide a refresh token. Revoke the existing app connection and try again.")

    expires_at = datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600)))
    return YouTubeTokenResponse(payload["access_token"], refresh_token, expires_at.isoformat())


async def fetch_youtube_channel(access_token: str) -> YouTubeChannel:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{YOUTUBE_API_URL}/channels",
            params={"part": "id,snippet", "mine": "true", "maxResults": 1},
            headers={"Authorization": f"Bearer {access_token}"}
        )
    response.raise_for_status()
    items = response.json().get("items", [])

    if not items:
        raise ValueError("The selected Google account does not have a YouTube channel.")

    item = items[0]
    return YouTubeChannel(str(item["id"]), str(item.get("snippet", {}).get("title") or item["id"]))
