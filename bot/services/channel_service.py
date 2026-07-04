import logging

LOGGER = logging.getLogger("Bot")


class ChannelService:
    def __init__(self):
        self.active_channels: dict[str, str] = {}

    def track_channel(self, payload) -> None:
        self.active_channels[payload.broadcaster.id] = payload.broadcaster.name

    def get_active_channels(self) -> dict[str, str]:
        return self.active_channels.copy()
