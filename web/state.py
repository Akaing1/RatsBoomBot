bot = None
db = None


def set_runtime(*, twitch_bot, token_database) -> None:
    global bot, db

    bot = twitch_bot
    db = token_database


def get_bot():
    return bot


def get_db():
    return db
