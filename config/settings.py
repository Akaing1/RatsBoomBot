import os

from dotenv import load_dotenv

load_dotenv()

VALID_BOT_DETECTION_MODES = {"learning", "shadow", "active"}
VALID_ENVIRONMENTS = {"local", "production"}


class Settings:
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")

    BOT_ID = os.getenv("BOT_ID")
    OWNER_ID = os.getenv("OWNER_ID")

    PREFIX = os.getenv("PREFIX", "!")
    DATABASE_PATH = os.getenv("DATABASE_PATH", ".data/tokens.db")
    LEAGUE_DATABASE_PATH = os.getenv("LEAGUE_DATABASE_PATH", ".data/league.db")
    STREAM_LOGS_PATH = os.getenv("STREAM_LOGS_PATH", ".data/logs")

    ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
    ADMIN_PORT = int(os.getenv("ADMIN_PORT", "4345"))
    ADMIN_BASE_URL = os.getenv("ADMIN_BASE_URL", f"http://{ADMIN_HOST}:{ADMIN_PORT}")

    SESSION_SECRET = os.getenv("SESSION_SECRET")
    ADMIN_SESSION_MAX_AGE_SECONDS = int(os.getenv("ADMIN_SESSION_MAX_AGE_SECONDS", str(60 * 60 * 8)))
    CHANNEL_SESSION_MAX_AGE_SECONDS = int(os.getenv("CHANNEL_SESSION_MAX_AGE_SECONDS", str(60 * 60 * 24 * 30)))

    ENVIRONMENT = os.getenv("ENVIRONMENT", "local").strip().lower()
    SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").strip().lower() == "true"
    TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").strip().lower() == "true"

    BOT_REDIRECT_URI = os.getenv("BOT_REDIRECT_URI", f"{ADMIN_BASE_URL}/admin/oauth/bot")
    CHANNEL_REDIRECT_URI = os.getenv("CHANNEL_REDIRECT_URI", f"{ADMIN_BASE_URL}/admin/oauth/channel")
    PUBLIC_CHANNEL_REDIRECT_URI = os.getenv("PUBLIC_CHANNEL_REDIRECT_URI", f"{ADMIN_BASE_URL}/oauth/channel/connect")

    BOT_SCOPES = os.getenv("BOT_SCOPES", "user:read:chat user:write:chat user:bot")

    CHANNEL_SCOPES = os.getenv(
        "CHANNEL_SCOPES",
        "channel:bot "
        "moderator:manage:banned_users "
        "moderator:read:followers "
        "moderator:read:blocked_terms "
        "moderator:read:chat_settings "
        "moderator:read:unban_requests "
        "moderator:read:chat_messages "
        "moderator:read:warnings "
        "moderator:read:moderators "
        "moderator:read:vips "
        "channel:read:redemptions "
        "channel:read:subscriptions "
        "channel:read:ads "
        "clips:edit "
        "channel:manage:raids "
        "channel:manage:moderators "
        "moderator:manage:announcements "
        "moderator:manage:shoutouts"
    )

    IGNORED_USERS = {
        user.strip().lower()
        for user in os.getenv("IGNORED_USERS", "").split(",")
        if user.strip()
    }

    BOT_DETECTION_MODE = os.getenv("BOT_DETECTION_MODE", "learning").strip().lower()


settings = Settings()

if not settings.SESSION_SECRET:
    raise ValueError("SESSION_SECRET must be configured in .env.")

if settings.ADMIN_SESSION_MAX_AGE_SECONDS <= 0:
    raise ValueError("ADMIN_SESSION_MAX_AGE_SECONDS must be greater than zero.")

if settings.CHANNEL_SESSION_MAX_AGE_SECONDS <= 0:
    raise ValueError("CHANNEL_SESSION_MAX_AGE_SECONDS must be greater than zero.")

if settings.BOT_DETECTION_MODE not in VALID_BOT_DETECTION_MODES:
    raise ValueError("BOT_DETECTION_MODE must be learning, shadow, or active.")

if settings.ENVIRONMENT not in VALID_ENVIRONMENTS:
    raise ValueError("ENVIRONMENT must be local or production.")

if settings.ENVIRONMENT == "production" and not settings.SESSION_HTTPS_ONLY:
    raise ValueError("SESSION_HTTPS_ONLY must be true in production.")
