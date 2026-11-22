"""Owner-only Stream Together controls using Twitch's Guest Star API."""
import asyncio
import re
import time

from twitchio.http import Route


class StreamTogetherError(ValueError):
    pass


class StreamTogetherService:
    def __init__(self, bot):
        self.bot = bot
        self._states = {}
        self._locks = {}
        self._settings = {}
        self._connected_states = {}

    async def connected_state(self, channel_id, host_id):
        """Read an invited channel's session without granting host controls."""
        if not re.fullmatch(r"[0-9]{1,25}", host_id) or channel_id == host_id:
            return None
        key = (channel_id, host_id)
        async with self._locks.setdefault(key, asyncio.Lock()):
            now = time.monotonic()
            cached = self._connected_states.get(key)
            if cached and now - cached[0] < 10:
                return cached[1]
            result = await self._request(channel_id, "GET", "session", broadcaster_id=host_id, moderator_id=channel_id)
            session = next(iter(result.get("data", [])), None)
            guests = (session or {}).get("guests", [])
            own_guest = any(str(guest.get("user_id")) == channel_id for guest in guests)
            # Twitch can number slot zero from the authenticated guest's point of view.
            state = {"state": "active", "session": session, "invites": [], "slot_count": 0,
                     "is_host": False} if own_guest else None
            self._connected_states[key] = (now, state)
            return state

    async def _request(self, channel_id, method, path, **params):
        return await self.bot._http.request_json(Route(method, f"guest_star/{path}",
            params={"broadcaster_id": channel_id, **params}, token_for=channel_id))

    async def _read(self, channel_id):
        now = time.monotonic()
        cached = self._states.get(channel_id)
        if cached and now - cached[0] < 10:
            return cached[1]
        data = await self._request(channel_id, "GET", "session", moderator_id=channel_id)
        session = next(iter(data.get("data", [])), None)
        settings = self._settings.get(channel_id)
        if not settings or now - settings[0] > 300:
            result = await self._request(channel_id, "GET", "channel_settings", moderator_id=channel_id)
            settings = (now, next(iter(result.get("data", [])), {}))
            self._settings[channel_id] = settings
        invites = []
        if session:
            result = await self._request(channel_id, "GET", "invites", moderator_id=channel_id, session_id=session["id"])
            invites = result.get("data", [])
        state = {"state": "active" if session else "idle", "session": session, "invites": invites,
                 "slot_count": settings[1].get("slot_count", 0)}
        self._states[channel_id] = (now, state)
        return state

    async def state(self, channel_id):
        async with self._locks.setdefault(channel_id, asyncio.Lock()):
            return await self._read(channel_id)

    async def action(self, channel_id, action, values):
        async with self._locks.setdefault(channel_id, asyncio.Lock()):
            if action not in {"start", "end", "invite", "revoke", "assign", "move", "remove", "settings"}:
                raise StreamTogetherError("Unknown Stream Together action.")
            # Recheck the session before writing so a stale overlay cannot affect a new call.
            self._states.pop(channel_id, None)
            state = await self._read(channel_id)
            session = state["session"]
            if action == "start":
                if session:
                    raise StreamTogetherError("A session is already active. Refresh to see it.")
                params, method, path = {}, "POST", "session"
            else:
                if not session or values.get("session_id") != session["id"]:
                    raise StreamTogetherError("The session has changed. Refresh and try again.")
                params = {"session_id": session["id"]}
                if action == "end":
                    method, path = "DELETE", "session"
                else:
                    params["moderator_id"] = channel_id
                    guest_id = str(values.get("guest_id", ""))
                    if action in {"invite", "revoke", "assign", "remove"}:
                        if not re.fullmatch(r"\d{1,25}", guest_id) or guest_id == channel_id:
                            raise StreamTogetherError("Choose a guest other than yourself.")
                        params["guest_id"] = guest_id
                    if action in {"invite", "revoke"}:
                        method, path = ("POST" if action == "invite" else "DELETE"), "invites"
                    else:
                        slot = str(values.get("slot_id", ""))
                        if not slot.isdecimal() or not 1 <= int(slot) <= state["slot_count"]:
                            raise StreamTogetherError("Choose a valid guest slot.")
                        if action == "assign":
                            if not any(str(invite.get("user_id")) == guest_id and invite.get("status") == "READY" for invite in state["invites"]):
                                raise StreamTogetherError("That guest is not ready to join yet.")
                            params["slot_id"] = slot
                            method, path = "POST", "slot"
                        elif action == "move":
                            if not any(str(guest.get("slot_id")) == slot for guest in session.get("guests", [])):
                                raise StreamTogetherError("That guest has moved or left. Refresh and try again.")
                            destination = str(values.get("destination_slot_id", ""))
                            if not destination.isdecimal() or not 1 <= int(destination) <= state["slot_count"]:
                                raise StreamTogetherError("Choose a valid destination slot.")
                            params.update(source_slot_id=slot, destination_slot_id=destination)
                            method, path = "PATCH", "slot"
                        else:
                            guest = next((guest for guest in session.get("guests", []) if str(guest.get("slot_id")) == slot), None)
                            if not guest or (action == "remove" and str(guest.get("user_id")) != guest_id):
                                raise StreamTogetherError("That guest has moved or left. Refresh and try again.")
                            params["slot_id"] = slot
                            if action == "remove":
                                method, path = "DELETE", "slot"
                            else:
                                for key in ("is_audio_enabled", "is_video_enabled", "is_live"):
                                    if key in values:
                                        if values[key] not in {"true", "false"}:
                                            raise StreamTogetherError("Invalid guest setting.")
                                        params[key] = values[key]
                                if "volume" in values:
                                    volume = str(values["volume"])
                                    if not volume.isdecimal() or not 0 <= int(volume) <= 100:
                                        raise StreamTogetherError("Volume must be between 0 and 100.")
                                    params["volume"] = volume
                                if len(params) == 3:
                                    raise StreamTogetherError("Choose a guest setting to change.")
                                method, path = "PATCH", "slot_settings"
            # Do not retry writes: an invite/start may have succeeded even if its response was lost.
            try:
                await self._request(channel_id, method, path, **params)
            finally:
                self._states.pop(channel_id, None)
