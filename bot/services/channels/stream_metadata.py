from dataclasses import dataclass


@dataclass(frozen=True)
class StreamMetadataUpdate:
    value: str
    announcement: str
    game_id: str | None = None


class StreamCategoryNotFoundError(ValueError):
    pass


class StreamCategoryLookupError(RuntimeError):
    pass


async def update_stream_title(bot, broadcaster_id: str, title: str) -> StreamMetadataUpdate:
    broadcaster = bot.create_partialuser(str(broadcaster_id))
    await broadcaster.modify_channel(title=title)
    return StreamMetadataUpdate(title, f'Stream title updated to "{title}".')


async def update_stream_game(bot, broadcaster_id: str, game_name: str, *, token_for: str | None = None) -> StreamMetadataUpdate:
    try:
        options = {"token_for": str(token_for)} if token_for is not None else {}
        game = await bot.fetch_game(name=game_name, **options)
    except Exception as error:
        raise StreamCategoryLookupError(game_name) from error

    if game is None:
        raise StreamCategoryNotFoundError(game_name)

    game_id = str(game.id)
    resolved_name = str(getattr(game, "name", None) or game_name)
    broadcaster = bot.create_partialuser(str(broadcaster_id))
    await broadcaster.modify_channel(game_id=game_id)
    return StreamMetadataUpdate(resolved_name, f'Stream game updated to "{resolved_name}".', game_id)


async def clear_stream_category(bot, broadcaster_id: str) -> StreamMetadataUpdate:
    broadcaster = bot.create_partialuser(str(broadcaster_id))
    await broadcaster.modify_channel(game_id="0")
    return StreamMetadataUpdate("No category", "Stream category cleared.")
