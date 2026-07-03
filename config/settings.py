from dataclasses import dataclass


@dataclass
class Settings:
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""
    BOT_ID: str = ""
    OWNER_ID: str = ""
    PREFIX: str = "!"
    DATABASE_PATH: str = "tokens.db"


settings = Settings()
