from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class Settings:

    CLIENT_ID: str = os.getenv("CLIENT_ID")
    CLIENT_SECRET: str = os.getenv("CLIENT_SECRET")

    BOT_ID: str = os.getenv("BOT_ID")
    OWNER_ID: str = os.getenv("OWNER_ID")

    PREFIX: str = os.getenv("PREFIX", "!")
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH",
        "tokens.db",
    )


settings = Settings()