from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from web.oauth import build_bot_oauth_url, build_channel_oauth_url

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

    return f"""
    <h1>Channel OAuth callback received</h1>
    <p>Code received: {"yes" if code else "no"}</p>
    <p>Token exchange comes next.</p>
    """


@app.get("/oauth/bot", response_class=HTMLResponse)
async def oauth_bot_callback(code: str | None = None, error: str | None = None):
    if error:
        return f"<h1>Twitch bot auth failed</h1><p>{error}</p>"

    return f"""
    <h1>Bot OAuth callback received</h1>
    <p>Code received: {"yes" if code else "no"}</p>
    <p>Token exchange comes next.</p>
    """
