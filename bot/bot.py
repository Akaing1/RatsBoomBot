import logging

import twitchio
from twitchio import eventsub
from twitchio.ext import commands

from bot.commands.moderation import ModerationCommands
from bot.commands.points import PointsCommands
from bot.commands.socials import SocialCommands
from bot.commands.utility import UtilityCommands
from bot.events.chat import ChatEvents
from bot.services.service_container import ServiceContainer
from config.settings import settings
from database.db import save_token

LOGGER = logging.getLogger("Bot")


class TwitchBot(commands.AutoBot):
    def __init__(self, *, token_database, subs):
        self.token_database = token_database
        self.services: ServiceContainer | None = None

        super().__init__(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            bot_id=settings.BOT_ID,
            owner_id=settings.OWNER_ID,
            prefix=settings.PREFIX,
            subscriptions=subs,
            force_subscribe=True,
        )

    async def setup_hook(self) -> None:
        self.services = ServiceContainer(self)

        await self.add_component(UtilityCommands(self))
        await self.add_component(SocialCommands(self))
        await self.add_component(PointsCommands(self))
        await self.add_component(ModerationCommands(self))
        await self.add_component(ChatEvents(self))

        await self.services.start()

        LOGGER.info("Loaded commands:")
        for command in self.commands.values():
            LOGGER.info(" - %s", command.name)

    async def close(self) -> None:
        if self.services:
            await self.services.stop()

        await super().close()

    async def event_ready(self) -> None:
        LOGGER.info("Logged in as %s", self.bot_id)

    async def event_command_error(self, payload) -> None:
        LOGGER.error("Command error: %r", payload)
        LOGGER.error("Exception: %r", getattr(payload, "exception", None))

    async def add_token(self, token: str, refresh: str):
        resp = await super().add_token(token, refresh)

        await save_token(
            self.token_database,
            resp.user_id,
            token,
            refresh,
        )

        LOGGER.info("Saved token for user %s", resp.user_id)

        return resp

    async def event_oauth_authorized(
        self,
        payload: twitchio.authentication.UserTokenPayload,
    ) -> None:
        await self.add_token(
            payload.access_token,
            payload.refresh_token,
        )

        if not payload.user_id:
            return

        subs = [
            eventsub.ChatMessageSubscription(
                broadcaster_user_id=payload.user_id,
                user_id=self.bot_id,
            )
        ]

        resp = await self.multi_subscribe(subs)

        if resp.errors:
            LOGGER.warning(
                "Failed to subscribe to %r for user %s",
                resp.errors,
                payload.user_id,
            )