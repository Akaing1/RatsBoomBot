import asqlite
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from database.db import save_token
from web.oauth import (
    build_bot_oauth_url,
    build_channel_oauth_url,
    exchange_code_for_token,
)

app = FastAPI(title="RatsBoomBot Web")


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!doctype html>
    <html>
        <head>
            <title>RatsBoomBot</title>
        </head>
        <body>
            <h1>RatsBoomBot</h1>
            <p>Connect your Twitch channel to RatsBoomBot.</p>

            <p>
                <a href="/connect/channel">
                    <button>Connect Channel</button>
                </a>
            </p>

            <p>
                <a href="/connect/bot">
                    <button>Connect Bot Account</button>
                </a>
            </p>
        </body>
    </html>
    """


@app.get("/connect/channel")
async def connect_channel():
    return RedirectResponse(build_channel_oauth_url())


@app.get("/connect/bot")
async def connect_bot():
    return RedirectResponse(build_bot_oauth_url())


@app.get("/oauth/channel", response_class=HTMLResponse)
async def oauth_channel_callback(code: str | None = None, error: str | None = None):
    if error:
        return f"<h1>Twitch auth failed</h1><p>{error}</p>"

    if not code:
        return "<h1>Twitch auth failed</h1><p>No code was provided.</p>"

    try:
        token_response = await exchange_code_for_token(
            code=code,
            redirect_uri=settings.CHANNEL_REDIRECT_URI
        )
    except Exception as exc:
        return f"<h1>Token exchange failed</h1><p>{exc!r}</p>"

    async with asqlite.create_pool(settings.DATABASE_PATH) as db:
        # Temporary placeholder until we add Twitch user validation.
        # This will be improved next.
        await save_token(
            db=db,
            user_id="channel_pending_user_lookup",
            token=token_response.access_token,
            refresh=token_response.refresh_token
        )

    return """
    <h1>Channel connected</h1>
    <p>RatsBoomBot received and saved the channel token.</p>
    <p>You can close this window.</p>
    """


@app.get("/oauth/bot", response_class=HTMLResponse)
async def oauth_bot_callback(code: str | None = None, error: str | None = None):
    if error:
        return f"<h1>Twitch bot auth failed</h1><p>{error}</p>"

    if not code:
        return "<h1>Twitch bot auth failed</h1><p>No code was provided.</p>"

    try:
        token_response = await exchange_code_for_token(
            code=code,
            redirect_uri=settings.BOT_REDIRECT_URI
        )
    except Exception as exc:
        return f"<h1>Token exchange failed</h1><p>{exc!r}</p>"

    async with asqlite.create_pool(settings.DATABASE_PATH) as db:
        # Temporary placeholder until we add Twitch user validation.
        # This will be improved next.
        await save_token(
            db=db,
            user_id="bot_pending_user_lookup",
            token=token_response.access_token,
            refresh=token_response.refresh_token
        )

    return """
    <h1>Bot account connected</h1>
    <p>RatsBoomBot received and saved the bot token.</p>
    <p>You can close this window.</p>
    """
