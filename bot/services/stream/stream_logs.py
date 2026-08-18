import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger("RatBoomBot")


class StreamSessionLogHandler(logging.Handler):

    def __init__(self, stream_log_service) -> None:
        super().__init__(level=logging.INFO)
        self.stream_log_service = stream_log_service
        self.handling_record = False

    def emit(self, record: logging.LogRecord) -> None:
        if self.handling_record:
            return

        broadcaster_id = getattr(record, "broadcaster_id", None)

        if broadcaster_id is None:
            return

        broadcaster_id = str(broadcaster_id)

        if broadcaster_id not in self.stream_log_service.active_sessions:
            return

        self.handling_record = True

        try:
            message = self.format(record)
            self.stream_log_service.write(broadcaster_id, record.levelname, message)
        finally:
            self.handling_record = False


@dataclass
class StreamLogSession:
    broadcaster_id: str
    stream_id: str
    channel_name: str
    log_path: Path


class StreamLogService:

    MAX_SAVED_SESSIONS_PER_CHANNEL = 10

    def __init__(self, bot, broadcaster_service, logs_path: str):
        self.bot = bot
        self.broadcasters = broadcaster_service
        self.logs_path = Path(logs_path)
        self.active_sessions: dict[str, StreamLogSession] = {}
        self.log_handler = StreamSessionLogHandler(self)
        self.log_handler.setFormatter(logging.Formatter("%(message)s"))

    async def setup(self) -> None:
        LOGGER.info(
            "[Stream Logs] Preparing stream log directory at %s.",
            self.logs_path
        )

        try:
            self.logs_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            LOGGER.exception(
                "[Stream Logs] Failed to create stream log directory at %s.",
                self.logs_path
            )
            raise

        if self.log_handler not in LOGGER.handlers:
            LOGGER.addHandler(self.log_handler)

        await self.start_live_sessions()
        self.prune_all_channels()

        LOGGER.info(
            "[Stream Logs] Stream logging ready with %d active sessions.",
            len(self.active_sessions)
        )

    async def stop(self) -> None:
        session_count = len(self.active_sessions)

        LOGGER.info(
            "[Stream Logs] Stopping %d active stream log sessions.",
            session_count
        )

        for broadcaster_id in list(self.active_sessions):
            self.write(
                broadcaster_id,
                "SYSTEM",
                "RatsBoomBot stopped while this stream was still active."
            )

        self.active_sessions.clear()
        LOGGER.removeHandler(self.log_handler)

        LOGGER.info("[Stream Logs] Stream logging stopped.")

    async def start_live_sessions(self) -> None:
        broadcasters = self.broadcasters.get_broadcasters()

        if not broadcasters:
            LOGGER.info(
                "[Stream Logs] No broadcasters are available for live session discovery."
            )
            return

        LOGGER.info(
            "[Stream Logs] Checking %d broadcasters for active streams.",
            len(broadcasters)
        )

        resumed_count = 0

        for broadcaster_id, broadcaster in broadcasters.items():
            try:
                partial_user = self.bot.create_partialuser(broadcaster_id)
                stream = await partial_user.fetch_stream()
            except Exception:
                LOGGER.exception(
                    "[Stream Logs] Failed to check stream state for broadcaster %s.",
                    broadcaster_id
                )
                continue

            if stream is None:
                LOGGER.debug(
                    "[Stream Logs] Broadcaster %s is offline.",
                    broadcaster_id
                )
                continue

            stream_id = self.get_stream_id(stream)

            if stream_id is None:
                LOGGER.warning(
                    "[Stream Logs] Live stream for broadcaster %s did not expose a stream ID.",
                    broadcaster_id
                )
                continue

            await self.start_session(
                broadcaster_id=broadcaster_id,
                stream_id=stream_id,
                channel_name=broadcaster.name or broadcaster_id
            )

            resumed_count += 1

        LOGGER.info(
            "[Stream Logs] Started or resumed %d live stream sessions.",
            resumed_count
        )

    async def start_session(self, broadcaster_id: str, stream_id: str,
                            channel_name: str | None = None) -> StreamLogSession:
        broadcaster_id = str(broadcaster_id)
        stream_id = str(stream_id)
        existing_session = self.active_sessions.get(broadcaster_id)

        if existing_session and existing_session.stream_id == stream_id:
            LOGGER.debug(
                "[Stream Logs] Stream session %s is already active for broadcaster %s.",
                stream_id,
                broadcaster_id
            )
            return existing_session

        if existing_session:
            self.write(
                broadcaster_id,
                "SYSTEM",
                "A new stream session replaced the previous active session."
            )

            self.active_sessions.pop(broadcaster_id, None)

            LOGGER.warning(
                "[Stream Logs] Replaced stream session %s with %s for broadcaster %s.",
                existing_session.stream_id,
                stream_id,
                broadcaster_id
            )

        broadcaster = self.broadcasters.get_broadcasters().get(broadcaster_id)

        if not channel_name and broadcaster:
            channel_name = broadcaster.name

        channel_name = channel_name or broadcaster_id
        safe_channel_name = self.sanitize_path_part(channel_name)
        safe_stream_id = self.sanitize_path_part(stream_id)
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
        channel_directory = self.logs_path / safe_channel_name
        existing_session_directory = self.find_stream_directory(channel_directory, safe_stream_id)

        if existing_session_directory:
            session_directory = existing_session_directory
            resumed = True
        else:
            session_directory = channel_directory / f"{timestamp}_stream-{safe_stream_id}"
            resumed = False

        try:
            session_directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            LOGGER.exception(
                "[Stream Logs] Failed to create stream session directory at %s.",
                session_directory
            )
            raise

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
            message = (
                f"Stream session started | Channel: {channel_name} | "
                f"Broadcaster ID: {broadcaster_id} | Stream ID: {stream_id}"
            )

            self.write(broadcaster_id, "SYSTEM", message)

        LOGGER.info(
            "[Stream Logs] %s stream logging for %s. File: %s",
            "Resumed" if resumed else "Started",
            channel_name,
            log_path
        )

        self.prune_channel_logs(channel_directory)

        return session

    async def end_session(self, broadcaster_id: str) -> None:
        broadcaster_id = str(broadcaster_id)
        session = self.active_sessions.get(broadcaster_id)

        if session is None:
            LOGGER.debug(
                "[Stream Logs] No active session found for broadcaster %s.",
                broadcaster_id
            )
            return

        message = (
            f"Stream session ended | Channel: {session.channel_name} | "
            f"Stream ID: {session.stream_id}"
        )

        self.write(broadcaster_id, "SYSTEM", message)
        self.active_sessions.pop(broadcaster_id, None)

        LOGGER.info(
            "[Stream Logs] Stopped stream logging for %s.",
            session.channel_name
        )

    def write(self, broadcaster_id: str, event_type: str, message: str) -> bool:
        broadcaster_id = str(broadcaster_id)
        session = self.active_sessions.get(broadcaster_id)

        if session is None:
            LOGGER.debug(
                "[Stream Logs] Skipped %s event because broadcaster %s has no active session.",
                event_type,
                broadcaster_id
            )
            return False

        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
        clean_event_type = event_type.strip().upper()
        clean_message = self.clean_message(message)
        line = f"{timestamp} {clean_event_type:<12} {clean_message}\n"

        try:
            with session.log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(line)
        except OSError:
            LOGGER.exception(
                "[Stream Logs] Failed to write stream log at %s.",
                session.log_path
            )
            return False

        LOGGER.debug(
            "[Stream Logs] Wrote %s event for broadcaster %s.",
            clean_event_type,
            broadcaster_id
        )

        return True

    def is_active(self, broadcaster_id: str) -> bool:
        return str(broadcaster_id) in self.active_sessions

    def get_active_session(self, broadcaster_id: str) -> StreamLogSession | None:
        return self.active_sessions.get(str(broadcaster_id))

    def prune_all_channels(self) -> int:
        deleted_count = 0

        try:
            channel_directories = [path for path in self.logs_path.iterdir() if path.is_dir()]
        except OSError:
            LOGGER.exception("[Stream Logs] Failed to inspect log directory %s.", self.logs_path)
            return 0

        for channel_directory in channel_directories:
            deleted_count += self.prune_channel_logs(channel_directory)

        return deleted_count

    def prune_channel_logs(self, channel_directory: Path) -> int:
        channel_directory = channel_directory.resolve()

        try:
            channel_directory.relative_to(self.logs_path.resolve())
            session_directories = [
                path
                for path in channel_directory.iterdir()
                if path.is_dir() and (path / "log.txt").is_file()
            ]
            session_directories.sort(
                key=lambda path: (path / "log.txt").stat().st_mtime,
                reverse=True
            )
        except (OSError, ValueError):
            LOGGER.exception(
                "[Stream Logs] Failed to inspect channel log directory %s",
                channel_directory
            )
            return 0

        active_directories = {
            session.log_path.parent.resolve()
            for session in self.active_sessions.values()
        }

        retained_directories = {
            path.resolve()
            for path in session_directories
            if path.resolve() in active_directories
        }

        for session_directory in session_directories:
            if len(retained_directories) >= self.MAX_SAVED_SESSIONS_PER_CHANNEL:
                break

            retained_directories.add(session_directory.resolve())

        deleted_count = 0

        for session_directory in session_directories:
            if session_directory.resolve() in retained_directories:
                continue

            if self.delete_session_directory(session_directory):
                deleted_count += 1

        if deleted_count:
            LOGGER.info(
                "[Stream Logs] Removed %d expired stream logs from %s.",
                deleted_count,
                channel_directory.name
            )

        return deleted_count

    def delete_log(self, log_path: Path):
        resolved_log_path = log_path.resolve()
        active_log_paths = {
            session.log_path.resolve()
            for session in self.active_sessions.values()
        }

        if resolved_log_path in active_log_paths:
            return False, "Active stream logs cannot be deleted."

        if not resolved_log_path.is_file() or resolved_log_path.name != "log.txt":
            return False, "That stream log does not exist"

        if not self.delete_session_directory(resolved_log_path.parent):
            return False, "The stream log could not be deleted."

        LOGGER.info(
            "[Stream Logs] Manually deleted stream log %s",
            resolved_log_path
        )

        return True, "Stream log deleted."

    def delete_session_directory(self, session_directory: Path) -> bool:
        resolved_directory = session_directory.resolve()

        try:
            relative_path = resolved_directory.relative_to(self.logs_path.resolve())
        except ValueError:
            LOGGER.warning(
                "[Stream Logs] Refused to delete log directory outside %s: %s",
                self.logs_path,
                resolved_directory
            )
            return False

        if len(relative_path.parts) != 2 or not (resolved_directory / "log.txt").is_file():
            LOGGER.warning(
                "[Stream Logs] refused to delete invalid session directory: %s",
                resolved_directory
            )
            return False

        try:
            shutil.rmtree(resolved_directory)
        except OSError:
            LOGGER.exception(
                "[Stream logs] Failed to delete stream log directory %s.",
                resolved_directory
            )

    @staticmethod
    def get_stream_id(stream) -> str | None:
        stream_id = getattr(stream, "id", None)

        if stream_id is None:
            stream_id = getattr(stream, "stream_id", None)

        if stream_id is None:
            return None

        return str(stream_id)

    @staticmethod
    def find_stream_directory(channel_directory: Path, stream_id: str) -> Path | None:
        if not channel_directory.exists():
            return None

        try:
            matches = list(channel_directory.glob(f"*_stream-{stream_id}"))

            if not matches:
                return None

            matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            LOGGER.exception(
                "[Stream Logs] Failed to inspect stream directories in %s.",
                channel_directory
            )
            return None

        return matches[0]

    @staticmethod
    def sanitize_path_part(value: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
        sanitized = sanitized.strip("_")

        return sanitized.lower() or "unknown"

    @staticmethod
    def clean_message(message: str) -> str:
        return " ".join(str(message).splitlines()).strip()
