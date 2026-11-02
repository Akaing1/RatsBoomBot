"""Incoming-raid eligibility and whitelist-based automatic shoutouts."""
import asyncio
import logging
import time

from twitchio.http import Route

from bot.profiles import FeatureName, get_active_profile

LOGGER = logging.getLogger("RatBoomBot")


def listed(names, username):
    return str(username).casefold() in names.casefold().split()


def blocked_automatic_shoutout(broadcaster_id, username, source):
    profile = get_active_profile(str(broadcaster_id))
    if not profile:
        return False
    config = profile.automatic_shoutouts
    if source in {"raid", "auto:raid"}:
        return listed(config.blacklist, username)
    return source.startswith("auto:") and (not config.interactions or not listed(config.users, username))


class AutomaticShoutoutService:
    CACHE_LIMIT = 2048

    def __init__(self, bot, shoutouts):
        self.bot, self.shoutouts = bot, shoutouts
        self.cache, self.inflight, self.last_sent = {}, {}, {}

    async def stop(self):
        tasks = tuple(self.inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def lookup(self, token_owner, path, **params):
        key = (token_owner, path, tuple(sorted(params.items())))
        cached = self.cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        if key not in self.inflight:
            async def fetch():
                try:
                    payload = await asyncio.wait_for(self.bot._http.request_json(
                        Route("GET", path, token_for=token_owner, params=params)), timeout=10)
                    data, ttl = payload.get("data", []), 86400
                except Exception:
                    LOGGER.warning("[Automatic Shoutouts] Could not check %s for channel %s.", path, token_owner)
                    data, ttl = None, 30
                if len(self.cache) >= self.CACHE_LIMIT:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = (time.monotonic() + ttl, data)
                return data
            task = asyncio.create_task(fetch())
            self.inflight[key] = task
            task.add_done_callback(lambda done: self.inflight.pop(key, None))
        return await asyncio.shield(self.inflight[key])

    async def eligible(self, broadcaster_id, user_id, username, config):
        """All selected requirements apply to incoming raids only."""
        if config.require_list and not listed(config.users, username):
            return False
        if config.require_following:
            following = await self.lookup(broadcaster_id, "channels/followed", user_id=broadcaster_id, broadcaster_id=user_id)
            if not following:
                return False
        if config.require_partner:
            users = await self.lookup(broadcaster_id, "users", id=user_id)
            if not users or users[0].get("broadcaster_type") != "partner":
                return False
        if config.require_team:
            own = await self.lookup(broadcaster_id, "teams/channel", broadcaster_id=broadcaster_id)
            if not own:
                return False
            theirs = await self.lookup(broadcaster_id, "teams/channel", broadcaster_id=user_id)
            if not theirs or not ({team["id"] for team in own} & {team["id"] for team in theirs}):
                return False
        return True

    async def handle(self, broadcaster_id, user_id, username, trigger, amount=0):
        broadcaster_id, user_id = str(broadcaster_id), str(user_id)
        profile = get_active_profile(broadcaster_id)
        if not profile or trigger not in {"raid", "chat", "redeem", "subscription", "gift", "bits", "streak"}:
            return False
        config = profile.automatic_shoutouts
        if not getattr(config, trigger) or not (config.native or config.chat_message):
            return False
        services = self.bot.services
        if not services.features.is_enabled(broadcaster_id, FeatureName.CHANNEL):
            return False
        if not user_id.isdigit() or not username or user_id in {broadcaster_id, str(self.bot.bot_id), services.chat_identity.sender_id(broadcaster_id)}:
            return False
        source = f"auto:{trigger}"
        if blocked_automatic_shoutout(broadcaster_id, username, source):
            return False
        if trigger == "raid" and amount < config.minimum_viewers:
            return False
        markers = services.first_chat_shoutouts
        stream_id = await markers.get_live_stream_id(broadcaster_id)
        if stream_id is None:
            return False
        key = (broadcaster_id, user_id)
        if self.last_sent.get(key) == stream_id:
            return False
        if trigger == "raid" and not await self.eligible(broadcaster_id, user_id, username, config):
            return False
        latest = get_active_profile(broadcaster_id)
        if not latest or latest.automatic_shoutouts != config or blocked_automatic_shoutout(broadcaster_id, username, source):
            return False
        if not services.features.is_enabled(broadcaster_id, FeatureName.CHANNEL):
            return False
        # Reuse the persistent first-chat marker so all automatic paths share
        # one atomic reservation, including simultaneous events and restarts.
        if not await markers.mark_seen(broadcaster_id=broadcaster_id, stream_id=stream_id, user_id=user_id, username=username):
            return False
        sent = False
        try:
            if get_active_profile(broadcaster_id) != latest or not services.features.is_enabled(broadcaster_id, FeatureName.CHANNEL):
                return False
            if config.native:
                queued, _, _ = self.shoutouts.enqueue(broadcaster_id=broadcaster_id, user_id=user_id, username=username, requested_by=source)
                if not queued:
                    return False
                sent = True
            if config.chat_message:
                template = config.raid_message if trigger == "raid" else config.event_message
                chat_sent = await self.shoutouts.send_chat_message(broadcaster_id, username, template or None,
                    viewer_count=amount if trigger == "raid" else 0, amount=amount, trigger=trigger,
                    viewer_word="viewer" if amount == 1 else "viewers")
                sent = sent or chat_sent
            return sent
        finally:
            if sent:
                if len(self.last_sent) >= self.CACHE_LIMIT and key not in self.last_sent:
                    self.last_sent.pop(next(iter(self.last_sent)))
                self.last_sent[key] = stream_id
            else:
                await markers.forget_seen(broadcaster_id=broadcaster_id, stream_id=stream_id, user_id=user_id)


async def automatic_shoutout(bot, broadcaster_id, user_id, username, trigger, amount=0):
    service = getattr(getattr(bot, "services", None), "automatic_shoutouts", None)
    if service is None:
        return False
    try:
        return await service.handle(broadcaster_id, user_id, username, trigger, amount)
    except Exception:
        LOGGER.exception("[Automatic Shoutouts] Failed to handle %s in channel %s.", trigger, broadcaster_id)
        return False
