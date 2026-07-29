import logging

from twitchio.ext import commands

from bot.component_loader import load_components
from bot.services.service_container import ServiceContainer
from config.settings import settings
from storage.database import create_broadcaster_subscriptions, save_token

LOGGER = logging.getLogger("Bot")


class TwitchBot(commands.AutoBot):
    def __init__(self, *, token_database, subs, broadcaster_ids):
        self.token_database = token_database
        self.broadcaster_ids = broadcaster_ids
        self.services: ServiceContainer | None = None

        super().__init__(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            bot_id=settings.BOT_ID,
            owner_id=settings.OWNER_ID,
            prefix=settings.PREFIX,
            subscriptions=subs,
            force_subscribe=True
        )

    async def setup_hook(self):
        self.services = ServiceContainer(
            self,
            self.token_database,
            self.broadcaster_ids
        )

        await self.services.setup()
        await load_components(self)
        await self.services.start()

        LOGGER.info("Loaded Commands:")

        for command in self.commands.values():
            LOGGER.info(" - %s", command.name)

    async def close(self) -> None:
        if self.services:
            await self.services.stop()

        await super().close()

    async def event_ready(self):
        LOGGER.info("Logged in as %s", self.bot_id)

    async def add_token(self, token: str, refresh: str):
        response = await super().add_token(token, refresh)

        await save_token(
            self.token_database,
            response.user_id,
            token,
            refresh
        )

        return response

    async def onboard_bot_account(self, token: str, user_id: str, refresh: str) -> None:
        if str(user_id) != str(self.bot_id):
            LOGGER.warning(
                "Authorized account %s does not match configured bot account %s.",
                user_id,
                self.bot_id
            )
            return

        await self.add_token(token, refresh)

        LOGGER.info("Bot account %s onboarded successfully.", user_id)

    async def onboard_broadcaster(self, user_id: str, token: str, refresh: str) -> None:
        if str(user_id) == str(self.bot_id):
            LOGGER.info("Skipping broadcaster onboarding for bot account %s.", user_id)
            return

        await self.add_token(token, refresh)

        subscriptions = create_broadcaster_subscriptions(user_id)
        await self.multi_subscribe(subscriptions)

        if self.services:
            self.services.broadcasters.add_broadcaster(user_id)
            await self.services.broadcasters.refresh_broadcaster(user_id)

        LOGGER.info("Broadcaster %s onboarded successfully.", user_id)

    async def event_oauth_authorized(self, payload):
        if not payload.user_id:
            return

        if str(payload.user_id) == str(self.bot_id):
            await self.onboard_bot_account(
                user_id=payload.user_id,
                token=payload.access_token,
                refresh=payload.refresh_token
            )
            return

        await self.onboard_broadcaster(
            user_id=payload.user_id,
            token=payload.access_token,
            refresh=payload.refresh_token
        )

    async def event_command_error(self, payload):
        LOGGER.error("Command error: %r", payload)
        LOGGER.error("Exception: %r", getattr(payload, "exception", None))
