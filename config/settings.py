import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")

    BOT_ID = os.getenv("BOT_ID")
    OWNER_ID = os.getenv("OWNER_ID")

    PREFIX = os.getenv("PREFIX", "!")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "tokens.db")

    IGNORED_USERS = {
        user.strip().lower()
        for user in os.getenv("IGNORED_USERS", "").split(",")
        if user.strip()
    }

    DISCORD = os.getenv("DISCORD")
    YOUTUBE = os.getenv("YOUTUBE")

    DAILY_REDEEM_TITLE = os.getenv(
        "DAILY_REDEEM_TITLE",
        "Steal some cheese"
    )
    FIRST_REDEEM_TITLE = os.getenv(
        "FIRST_REDEEM_TITLE",
        "first"
    )

    DAILY_REDEEM_BREAD = int(os.getenv("DAILY_REDEEM_BREAD", "100"))
    FIRST_REDEEM_BREAD = int(os.getenv("FIRST_REDEEM_BREAD", "250"))


settings = Settings()
