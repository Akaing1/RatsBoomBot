import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")

    BOT_ID = os.getenv("BOT_ID")
    OWNER_ID = os.getenv("OWNER_ID")

    PREFIX = os.getenv("PREFIX", "!")
    DATABASE_PATH = os.getenv("DATABASE_PATH", ".data/tokens.db")

    STREAM_LOGS_PATH = os.getenv("STREAM_LOGS_PATH", ".data/logs")

    ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
    ADMIN_PORT = int(os.getenv("ADMIN_PORT", "4345"))
    ADMIN_BASE_URL = os.getenv(
        "ADMIN_BASE_URL",
        f"http://{ADMIN_HOST}:{ADMIN_PORT}"
    )

    ADMIN_SECRET = os.getenv("ADMIN_SECRET")
    SESSION_SECRET = os.getenv("SESSION_SECRET")

    BOT_REDIRECT_URI = os.getenv(
        "BOT_REDIRECT_URI",
        f"{ADMIN_BASE_URL}/oauth/bot"
    )

    CHANNEL_REDIRECT_URI = os.getenv(
        "CHANNEL_REDIRECT_URI",
        f"{ADMIN_BASE_URL}/oauth/channel"
    )

    BOT_SCOPES = os.getenv(
        "BOT_SCOPES",
        "user:read:chat user:write:chat user:bot"
    )

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
        "channel:manage:moderators"
        "moderator:manage:shoutouts"
    )

    IGNORED_USERS = {
        user.strip().lower()
        for user in os.getenv("IGNORED_USERS", "").split(",")
        if user.strip()
    }

    BOT_DETECTION_MODE = os.getenv(
        "BOT_DETECTION_MODE",
        "learning"
    ).strip().lower()

    DAILY_REDEEM_TITLE = os.getenv(
        "DAILY_REDEEM_TITLE",
        "Steal some cheese"
    )

    FIRST_REDEEM_TITLE = os.getenv(
        "FIRST_REDEEM_TITLE",
        "first"
    )

    DAILY_REDEEM_BREAD = int(
        os.getenv("DAILY_REDEEM_BREAD", "100")
    )

    FIRST_REDEEM_BREAD = int(
        os.getenv("FIRST_REDEEM_BREAD", "250")
    )


settings = Settings()

VALID_BOT_DETECTION_MODES = {
    "learning",
    "shadow",
    "active"
}

if not settings.ADMIN_SECRET:
    raise ValueError("ADMIN_SECRET must be configured in .env.")

if not settings.SESSION_SECRET:
    raise ValueError("SESSION_SECRET must be configured in .env.")

if settings.BOT_DETECTION_MODE not in VALID_BOT_DETECTION_MODES:
    raise ValueError(
        "BOT_DETECTION_MODE must be learning, shadow, or active."
    )
