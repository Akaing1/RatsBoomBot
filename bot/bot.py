import logging

from twitchio import eventsub
from twitchio.ext import commands

from bot.commands.moderation import ModerationCommands
from bot.commands.points import PointsCommands
from bot.commands.socials import SocialCommands
from bot.commands.utility import UtilityCommands
from bot.commands.counters import CounterCommands

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

    async def setup_hook(self):
        self.services = ServiceContainer(self, self.token_database)
        await self.services.setup()

        await self.add_component(UtilityCommands(self))
        await self.add_component(SocialCommands(self))
        await self.add_component(PointsCommands(self))
        await self.add_component(ModerationCommands(self))
        await self.add_component(ChatEvents(self))
        await self.add_component(CounterCommands(self))

        await self.services.start()

        LOGGER.info("Loaded Commands:")
        for cmd in self.commands.values():
            LOGGER.info(" - %s", cmd.name)

    async def close(self) -> None:
        if self.services:
            await self.services.stop()

        await super().close()

    async def event_ready(self):
        LOGGER.info("Logged in as %s", self.bot_id)

    async def add_token(self, token: str, refresh: str):
        resp = await super().add_token(token, refresh)

        await save_token(
            self.token_database,
            resp.user_id,
            token,
            refresh,
        )

        return resp

    async def event_oauth_authorized(self, payload):
        await self.add_token(
            payload.access_token,
            payload.refresh_token,
        )

        if not payload.user_id:
            return

        if payload.user_id == self.bot_id:
            return

        subs = [
            eventsub.ChatMessageSubscription(
                broadcaster_user_id=payload.user_id,
                user_id=self.bot_id
            ),
            eventsub.ChannelFollowSubscription(
                broadcaster_user_id=payload.user_id,
                moderator_user_id=payload.user_id
            ),
            eventsub.ChannelSubscribeSubscription(
                broadcaster_user_id=payload.user_id
            ),
            eventsub.ChannelSubscribeMessageSubscription(
                broadcaster_user_id=payload.user_id
            ),
            eventsub.ChannelBanSubscription(
                broadcaster_user_id=payload.user_id,
                moderator_user_id=payload.user_id
            ),
            eventsub.AdBreakBeginSubscription(
                broadcaster_user_id=payload.user_id
            )
        ]

        await self.multi_subscribe(subs)

    async def event_command_error(self, payload):
        LOGGER.error("Command error: %r", payload)
        LOGGER.error("Exception: %r", getattr(payload, "exception", None))
