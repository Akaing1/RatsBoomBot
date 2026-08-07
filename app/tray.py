import logging
import subprocess
import sys
from pathlib import Path

import pystray
from PIL import Image, UnidentifiedImageError

LOGGER = logging.getLogger("RatBoomBot")

ICON_PATH = "assets/NinjaDoro.ico"
PROJECT_DIR = Path(__file__).resolve().parent.parent
BOT_PROCESS: subprocess.Popen | None = None


def create_icon() -> Image.Image:
    icon_path = PROJECT_DIR / ICON_PATH

    try:
        return Image.open(icon_path)
    except (FileNotFoundError, UnidentifiedImageError):
        LOGGER.exception(
            "[Tray] Could not load tray icon from %s.",
            icon_path
        )
        raise


def start_bot(icon=None, item=None) -> None:
    global BOT_PROCESS

    if BOT_PROCESS and BOT_PROCESS.poll() is None:
        LOGGER.warning("[Tray] Start ignored because RatBoomBot is already running.")
        return

    command = [sys.executable, "main.py", "--runtime"]

    LOGGER.info("[Tray] Starting RatBoomBot runtime.")

    try:
        BOT_PROCESS = subprocess.Popen(command, cwd=PROJECT_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except OSError:
        LOGGER.exception("[Tray] Failed to start RatBoomBot runtime.")
        BOT_PROCESS = None
        return

    LOGGER.info(
        "[Tray] RatBoomBot runtime started with process ID %s.",
        BOT_PROCESS.pid
    )


def stop_bot(icon=None, item=None) -> None:
    global BOT_PROCESS

    if BOT_PROCESS is None:
        LOGGER.info("[Tray] Stop ignored because no runtime process is tracked.")
        return

    if BOT_PROCESS.poll() is not None:
        LOGGER.info(
            "[Tray] Runtime process %s had already exited with code %s.",
            BOT_PROCESS.pid,
            BOT_PROCESS.returncode
        )

        BOT_PROCESS = None
        return

    process_id = BOT_PROCESS.pid

    LOGGER.info(
        "[Tray] Stopping RatBoomBot runtime process %s.",
        process_id
    )

    try:
        BOT_PROCESS.terminate()
    except OSError:
        LOGGER.exception(
            "[Tray] Failed to stop runtime process %s.",
            process_id
        )
        return

    BOT_PROCESS = None

    LOGGER.info(
        "[Tray] Stop signal sent to runtime process %s.",
        process_id
    )


def exit_app(icon, item) -> None:
    LOGGER.info("[Tray] Exiting RatBoomBot tray application.")

    stop_bot()
    icon.stop()


def run_tray() -> None:
    LOGGER.info("[Tray] Starting RatBoomBot tray application.")

    menu = pystray.Menu(
        pystray.MenuItem("Start Bot", start_bot),
        pystray.MenuItem("Stop Bot", stop_bot),
        pystray.MenuItem("Exit", exit_app)
    )

    icon = pystray.Icon("RatsBoomBot", create_icon(), title="RatsBoomBot", menu=menu)

    start_bot()

    LOGGER.info("[Tray] Tray icon is ready.")

    icon.run()

    LOGGER.info("[Tray] Tray application stopped.")
