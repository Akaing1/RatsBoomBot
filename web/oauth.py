from urllib.parse import urlencode

from config.settings import settings

TWITCH_AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"


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
        "scope": scopes
    }

    if force_verify:
        params["force_verify"] = "true"

    return f"{TWITCH_AUTHORIZE_URL}?{urlencode(params)}"
