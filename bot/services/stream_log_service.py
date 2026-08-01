import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger("Bot")


@dataclass
class StreamLogSession:
    broadcaster_id: str
    stream_id: str
    channel_name: str
    log_path: Path


class StreamLogService:
    def __init__(self, bot, broadcaster_service, logs_path: str):
        self.bot = bot
        self.broadcasters = broadcaster_service
        self.logs_path = Path(logs_path)
        self.active_sessions: dict[str, StreamLogSession] = {}

    async def setup(self) -> None:
        self.logs_path.mkdir(parents=True, exist_ok=True)
        await self.start_live_sessions()

    async def stop(self) -> None:
        for broadcaster_id in list(self.active_sessions):
            self.write(
                broadcaster_id,
                "SYSTEM",
                "RatsBoomBot stopped while this stream was still active."
            )

        self.active_sessions.clear()

    async def start_live_sessions(self) -> None:
        broadcasters = self.broadcasters.get_broadcasters()

        for broadcaster_id, broadcaster in broadcasters.items():
            try:
                partial_user = self.bot.create_partialuser(broadcaster_id)
                stream = await partial_user.fetch_stream()
            except Exception as error:
                LOGGER.warning(
                    "Could not check stream state for logger %s: %r",
                    broadcaster_id,
                    error
                )
                continue

            if stream is None:
                continue

            stream_id = self.get_stream_id(stream)

            if stream_id is None:
                LOGGER.warning(
                    "Live stream for %s did not expose a stream ID.",
                    broadcaster_id
                )
                continue

            await self.start_session(
                broadcaster_id=broadcaster_id,
                stream_id=stream_id,
                channel_name=broadcaster.name or broadcaster_id
            )

    async def start_session(self, broadcaster_id: str, stream_id: str, channel_name: str | None = None) -> StreamLogSession:
        broadcaster_id = str(broadcaster_id)
        stream_id = str(stream_id)

        existing_session = self.active_sessions.get(broadcaster_id)

        if existing_session and existing_session.stream_id == stream_id:
            return existing_session

        if existing_session:
            self.write(
                broadcaster_id,
                "SYSTEM",
                "A new stream session replaced the previous active session."
            )
            self.active_sessions.pop(broadcaster_id, None)

        broadcaster = self.broadcasters.get_broadcasters().get(broadcaster_id)

        if not channel_name and broadcaster:
            channel_name = broadcaster.name

        channel_name = channel_name or broadcaster_id
        safe_channel_name = self.sanitize_path_part(channel_name)
        safe_stream_id = self.sanitize_path_part(stream_id)

        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
        channel_directory = self.logs_path / safe_channel_name
        existing_session_directory = self.find_stream_directory(
            channel_directory=channel_directory,
            stream_id=safe_stream_id
        )

        if existing_session_directory:
            session_directory = existing_session_directory
            resumed = True
        else:
            session_directory = (
                channel_directory
                / f"{timestamp}_stream-{safe_stream_id}"
            )
            resumed = False

        session_directory.mkdir(parents=True, exist_ok=True)
        log_path = session_directory / "log.txt"

        session = StreamLogSession(
            broadcaster_id=broadcaster_id,
            stream_id=stream_id,
            channel_name=channel_name,
            log_path=log_path
        )

        self.active_sessions[broadcaster_id] = session

        if resumed:
            self.write(
                broadcaster_id,
                "SYSTEM",
                "RatsBoomBot resumed logging this active stream."
            )
        else:
            self.write(
                broadcaster_id,
                "SYSTEM",
                (
                    f"Stream session started | "
                    f"Channel: {channel_name} | "
                    f"Broadcaster ID: {broadcaster_id} | "
                    f"Stream ID: {stream_id}"
                )
            )

        LOGGER.info(
            "Stream logger started for %s. File: %s",
            channel_name,
            log_path
        )

        return session

    async def end_session(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)

        if broadcaster_id not in self.active_sessions:
            return

        session = self.active_sessions[broadcaster_id]

        self.write(
            broadcaster_id,
            "SYSTEM",
            (
                f"Stream session ended | "
                f"Channel: {session.channel_name} | "
                f"Stream ID: {session.stream_id}"
            )
        )

        self.active_sessions.pop(broadcaster_id, None)

        LOGGER.info(
            "Stream logger stopped for %s.",
            session.channel_name
        )

    def write(self, broadcaster_id: str, event_type: str, message: str) -> bool:
        session = self.active_sessions.get(str(broadcaster_id))

        if session is None:
            return False

        timestamp = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S %z"
        )

        clean_event_type = event_type.strip().upper()
        clean_message = self.clean_message(message)

        line = f"{timestamp} {clean_event_type:<12} {clean_message}\n"

        try:
            with session.log_path.open(
                "a",
                encoding="utf-8"
            ) as log_file:
                log_file.write(line)
        except OSError as error:
            LOGGER.error(
                "Failed writing stream log %s: %r",
                session.log_path,
                error
            )
            return False

        return True

    def is_active(self, broadcaster_id: str) -> bool:
        return str(broadcaster_id) in self.active_sessions

    def get_active_session(self, broadcaster_id: str) -> StreamLogSession | None:
        return self.active_sessions.get(str(broadcaster_id))

    def get_stream_id(self, stream) -> str | None:
        stream_id = getattr(stream, "id", None)

        if stream_id is None:
            stream_id = getattr(stream, "stream_id", None)

        if stream_id is None:
            return None

        return str(stream_id)

    def find_stream_directory(self, channel_directory: Path, stream_id: str) -> Path | None:
        if not channel_directory.exists():
            return None

        matches = list(
            channel_directory.glob(f"*_stream-{stream_id}")
        )

        if not matches:
            return None

        matches.sort(
            key=lambda path: path.stat().st_mtime,
            reverse=True
        )

        return matches[0]

    def sanitize_path_part(self, value: str) -> str:
        sanitized = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            value.strip()
        )

        sanitized = sanitized.strip("_")

        return sanitized.lower() or "unknown"

    def clean_message(self, message: str) -> str:
        return " ".join(str(message).splitlines()).strip()
