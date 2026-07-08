import subprocess
import sys
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

ICON_PATH = "assets/NinjaDoro.ico"


PROJECT_DIR = Path(__file__).parent
BOT_PROCESS: subprocess.Popen | None = None


def create_icon():
    return Image.open(ICON_PATH)


def start_bot(icon=None, item=None):
    global BOT_PROCESS

    if BOT_PROCESS and BOT_PROCESS.poll() is None:
        return

    BOT_PROCESS = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=PROJECT_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def stop_bot(icon=None, item=None):
    global BOT_PROCESS

    if BOT_PROCESS and BOT_PROCESS.poll() is None:
        BOT_PROCESS.terminate()
        BOT_PROCESS = None


def exit_app(icon, item):
    stop_bot()
    icon.stop()


def main():
    icon = pystray.Icon(
        "RatsBoomBot",
        create_icon(),
        title="RatsBoomBot",
        menu=pystray.Menu(
            pystray.MenuItem("Start Bot", start_bot),
            pystray.MenuItem("Stop Bot", stop_bot),
            pystray.MenuItem("Exit", exit_app),
        ),
    )

    start_bot()
    icon.run()


if __name__ == "__main__":
    main()
