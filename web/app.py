from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from config.settings import settings
from storage.database import save_token, create_broadcaster_subscriptions
from web.oauth import build_bot_oauth_url, build_channel_oauth_url, exchange_code_for_token, fetch_twitch_user
from web.state import get_bot, get_db

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
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.CHANNEL_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
    except Exception as exc:
        return f"<h1>Token exchange failed</h1><p>{exc!r}</p>"

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
        return "<h1>Runtime unavailable</h1><p>The bot runtime is not available.</p>"

    return f"""
    <h1>Channel connected</h1>
    <p>RatsBoomBot received and saved the channel token for {twitch_user.display_name}.</p>
    <p>The bot should now be active in this channel.</p>
    <p>You can close this window.</p>
    """


@app.get("/oauth/bot", response_class=HTMLResponse)
async def oauth_bot_callback(code: str | None = None, error: str | None = None):
    if error:
        return f"<h1>Twitch bot auth failed</h1><p>{error}</p>"

    if not code:
        return "<h1>Twitch bot auth failed</h1><p>No code was provided.</p>"

    try:
        token_response = await exchange_code_for_token(code=code, redirect_uri=settings.BOT_REDIRECT_URI)
        twitch_user = await fetch_twitch_user(token_response.access_token)
    except Exception as exc:
        return f"<h1>Token exchange failed</h1><p>{exc!r}</p>"

    runtime_bot = get_bot()
    runtime_db = get_db()

    if runtime_bot is not None:
        await runtime_bot.onboard_bot_account(
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
        return "<h1>Runtime unavailable</h1><p>The bot runtime is not available.</p>"

    return f"""
        <h1>Bot account connected</h1>
        <p>RatsBoomBot received and saved the bot token for {twitch_user.display_name}.</p>
        <p>You can close this window.</p>
        """
