import sys

from app.runtime import run
from app.tray import run_tray


if __name__ == "__main__":
    if "--runtime" in sys.argv:
        run()
    else:
        run_tray()
