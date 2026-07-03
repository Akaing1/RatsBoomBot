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


settings = Settings()