"""Shared preconditions for channel JSON read endpoints."""
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from web.channel.auth import CHANNEL_USER_ID_KEY, logout_channel_user


@dataclass(frozen=True)
class ChannelAPIContext:
    broadcaster_id: str
    runtime_bot: Any
    broadcaster: Any

    @property
    def services(self):
        return self.runtime_bot.services


def resolve_channel_api_context(request: Request, runtime_provider: Callable[[], Any]) -> ChannelAPIContext | JSONResponse:
    broadcaster_id = request.session.get(CHANNEL_USER_ID_KEY)
    if not broadcaster_id:
        return JSONResponse({"detail": "Channel authentication required."}, status_code=401)
    runtime_bot = runtime_provider()
    if runtime_bot is None or runtime_bot.services is None:
        return JSONResponse({"detail": "Bot runtime unavailable."}, status_code=503)
    broadcaster = runtime_bot.services.broadcasters.get_broadcasters().get(str(broadcaster_id))
    if broadcaster is None:
        logout_channel_user(request)
        return JSONResponse({"detail": "Connected channel not found."}, status_code=404)
    return ChannelAPIContext(broadcaster_id, runtime_bot, broadcaster)
