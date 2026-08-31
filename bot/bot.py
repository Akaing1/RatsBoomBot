import asyncio
import logging

from twitchio.ext import commands

from bot.component_loader import load_components
from bot.context import ChannelContext
from bot.profiles import CHANNEL_PROFILES, activate_profile, create_generic_profile, get_active_profile
from bot.services.container import ServiceContainer
from config.settings import settings
from storage.database import create_broadcaster_subscriptions, delete_token, save_token

LOGGER = logging.getLogger("RatBoomBot")


class TwitchBot(commands.AutoBot):

    def get_context(self, payload, *, cls=None):
        return super().get_context(payload, cls=cls or ChannelContext)

    def __init__(self, *, token_database, subs, broadcaster_ids, league_database=None):
        self.token_database = token_database
        self.league_database = league_database
        self.broadcaster_ids = [str(broadcaster_id) for broadcaster_id in broadcaster_ids]
        self.services: ServiceContainer | None = None

        self._close_lock = asyncio.Lock()
        self._closed = False

        LOGGER.info(
            "[Startup] Creating Twitch client for bot account %s with %d broadcasters and %d EventSub subscriptions.",
            settings.BOT_ID,
            len(self.broadcaster_ids),
            len(subs)
        )

        super().__init__(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            bot_id=settings.BOT_ID,
            owner_id=settings.OWNER_ID,
            prefix=settings.PREFIX,
            case_insensitive=True,
            subscriptions=subs,
            force_subscribe=True
        )

    async def setup_hook(self) -> None:
        LOGGER.info("[Startup] Running Twitch bot setup hook.")

        self.services = ServiceContainer(self, self.token_database, self.broadcaster_ids, self.league_database)

        LOGGER.info("[Services] Initializing service container.")
        await self.services.setup()
        LOGGER.info("[Services] Service container initialized.")

        LOGGER.info("[Components] Loading bot components.")
        await load_components(self)
        LOGGER.info("[Components] Bot components loaded.")

        LOGGER.info("[Services] Starting background services.")
        await self.services.start()
        LOGGER.info("[Services] Background services started.")

        command_names = sorted(command.name for command in self.commands.values())

        LOGGER.info(
            "[Commands] Loaded %d commands.",
            len(command_names)
        )

        for command_name in command_names:
            LOGGER.debug(
                "[Commands] Loaded command: %s.",
                command_name
            )

        LOGGER.info("[Startup] Twitch bot setup hook completed.")

    async def close(self) -> None:
        async with self._close_lock:
            if self._closed:
                return

            LOGGER.info("[Shutdown] Closing Twitch bot.")

            services = self.services

            if services is not None:
                LOGGER.info("[Services] Stopping background services.")

                try:
                    await services.stop()
                except Exception:
                    LOGGER.exception(
                        "[Services] Failed while stopping background services."
                    )
                else:
                    LOGGER.info("[Services] Background services stopped.")

            try:
                await super().close()
            except Exception:
                LOGGER.exception("[Shutdown] Failed while closing Twitch client.")
                raise

            self._closed = True

            LOGGER.info("[Shutdown] Twitch bot closed.")

    async def add_token(self, token: str, refresh: str):
        LOGGER.debug("[OAuth] Adding OAuth token to Twitch client.")

        try:
            response = await super().add_token(token, refresh)
        except Exception:
            LOGGER.exception(
                "[OAuth] Failed to add OAuth token to Twitch client."
            )
            raise

        LOGGER.info(
            "[OAuth] OAuth token accepted for user %s.",
            response.user_id
        )

        await save_token(self.token_database, response.user_id, token, refresh)

        return response

    async def onboard_bot_account(self, token: str, user_id: str, refresh: str) -> None:
        user_id = str(user_id)
        bot_id = str(self.bot_id)

        LOGGER.info(
            "[OAuth] Processing bot account authorization for user %s.",
            user_id
        )

        if user_id != bot_id:
            LOGGER.warning(
                "[OAuth] Authorized account %s does not match configured bot account %s.",
                user_id,
                bot_id
            )
            return

        await self.add_token(token, refresh)

        LOGGER.info(
            "[OAuth] Bot account %s onboarded successfully.",
            user_id
        )

    async def onboard_custom_bot_account(self, broadcaster_id: str, token: str, user_id: str, refresh: str, login: str, display_name: str) -> None:
        if self.services is None:
            raise RuntimeError("Bot services are not available.")

        broadcaster_id = str(broadcaster_id)
        user_id = str(user_id)
        identity_state = self.services.chat_identity.get_state(broadcaster_id)

        if not identity_state.premium_enabled:
            raise ValueError("Premium custom identity access is not enabled for this channel.")

        if user_id in {broadcaster_id, str(self.bot_id)} or user_id in self.broadcaster_ids:
            raise ValueError("Choose a dedicated Twitch bot account that is not connected as a broadcaster.")

        previous_user_id = identity_state.bot_user_id
        await self.add_token(token, refresh)

        try:
            await self.services.chat_identity.connect(broadcaster_id, user_id, login, display_name)
        except Exception:
            if previous_user_id != user_id:
                await delete_token(self.token_database, user_id)

            raise

        if previous_user_id and previous_user_id != str(user_id) and not self.services.chat_identity.is_custom_bot(previous_user_id):
            await delete_token(self.token_database, previous_user_id)

        LOGGER.info("[OAuth] Custom bot account %s onboarded for broadcaster %s.", user_id, broadcaster_id)

    async def onboard_broadcaster(self, user_id: str, token: str, refresh: str) -> None:
        user_id = str(user_id)

        LOGGER.info(
            "[OAuth] Processing broadcaster authorization for user %s.",
            user_id
        )

        if user_id == str(self.bot_id):
            LOGGER.info(
                "[OAuth] Skipping broadcaster onboarding for bot account %s.",
                user_id
            )
            return

        await self.add_token(token, refresh)

        subscriptions = create_broadcaster_subscriptions(user_id)

        LOGGER.info(
            "[EventSub] Submitting %d subscriptions for broadcaster %s.",
            len(subscriptions),
            user_id
        )

        try:
            await self.multi_subscribe(subscriptions)
        except Exception:
            LOGGER.exception(
                "[EventSub] Failed to subscribe broadcaster %s to Twitch events.",
                user_id
            )
            raise

        LOGGER.info(
            "[EventSub] Submitted subscriptions for broadcaster %s.",
            user_id
        )

        services = self.services

        if services is None:
            LOGGER.warning(
                "[Services] Broadcaster %s was authorized before the service container was available.",
                user_id
            )
        else:
            LOGGER.info(
                "[Broadcasters] Adding broadcaster %s to the active broadcaster service.",
                user_id
            )

            services.broadcasters.add_broadcaster(user_id)

            try:
                broadcaster = await services.broadcasters.refresh_broadcaster(user_id)
            except Exception:
                LOGGER.exception(
                    "[Broadcasters] Failed to refresh broadcaster %s after onboarding.",
                    user_id
                )
                raise

            channel_name = broadcaster.login if broadcaster is not None and broadcaster.login else f"channel_{user_id}"
            base_profile = CHANNEL_PROFILES.get(channel_name.lower(), create_generic_profile(channel_name))
            profile = services.profile_settings.apply_overrides(user_id, base_profile)
            was_active = get_active_profile(user_id) is not None
            activate_profile(user_id, profile)

            if not was_active:
                for component_class in profile.components:
                    await self.add_component(component_class(self, profile, user_id))

            LOGGER.info(
                "[Broadcasters] Broadcaster %s added and refreshed.",
                user_id
            )

        if user_id not in self.broadcaster_ids:
            self.broadcaster_ids.append(user_id)

        LOGGER.info(
            "[OAuth] Broadcaster %s onboarded successfully.",
            user_id
        )

    async def event_oauth_authorized(self, payload) -> None:
        if not payload.user_id:
            LOGGER.warning(
                "[OAuth] Received authorization event without a user ID."
            )
            return

        LOGGER.info(
            "[OAuth] Received authorization event for user %s.",
            payload.user_id
        )

        if self.services is not None and self.services.chat_identity.is_custom_bot(payload.user_id):
            LOGGER.info("[OAuth] Recognized managed custom bot account %s.", payload.user_id)
            return

        if str(payload.user_id) == str(self.bot_id):
            await self.onboard_bot_account(user_id=payload.user_id, token=payload.access_token, refresh=payload.refresh_token)
            return

        await self.onboard_broadcaster(user_id=payload.user_id, token=payload.access_token, refresh=payload.refresh_token)

    async def event_command_error(self, payload) -> None:
        exception = getattr(payload, "exception", None)
        context = getattr(payload, "context", None)
        command = getattr(context, "command", None)
        author = getattr(context, "author", None)
        channel = getattr(context, "channel", None)

        command_name = getattr(command, "name", "unknown")
        author_name = getattr(author, "name", "unknown")
        channel_name = getattr(channel, "name", "unknown")

        LOGGER.error(
            "[Commands] Command %s failed in channel %s for user %s: %r",
            command_name,
            channel_name,
            author_name,
            exception
        )

        if exception is not None:
            LOGGER.debug(
                "[Commands] Command failure payload: %r",
                payload,
                exc_info=(type(exception), exception, exception.__traceback__)
            )
