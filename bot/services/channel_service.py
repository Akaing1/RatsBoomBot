import logging

LOGGER = logging.getLogger("RatBoomBot")


class ChannelService:

    def __init__(self):
        self.active_channels: dict[str, str] = {}

    def track_channel(self, payload) -> None:

        broadcaster_id = str(payload.broadcaster.id)
        broadcaster_name = payload.broadcaster.name

        previous_name = self.active_channels.get(broadcaster_id)

        self.active_channels[broadcaster_id] = broadcaster_name

        if previous_name is None:
            LOGGER.info(
                "[Channels] Tracking channel %s (%s).",
                broadcaster_name,
                broadcaster_id
            )
            return

        if previous_name != broadcaster_name:
            LOGGER.info(
                "[Channels] Updated channel %s from %s to %s.",
                broadcaster_id,
                previous_name,
                broadcaster_name
            )
            return

        LOGGER.debug(
            "[Channels] Channel %s (%s) is already tracked.",
            broadcaster_name,
            broadcaster_id
        )

    def get_active_channels(self) -> dict[str, str]:

        LOGGER.debug(
            "[Channels] Returning %d active channels.",
            len(self.active_channels)
        )

        return self.active_channels.copy()
