from pathlib import Path


APP_NAME = "RatsBoomBot"
APP_VERSION = "8.10.4"

PROJECT_DIRECTORY = Path(__file__).resolve().parent.parent
DEPLOYMENT_STAMP_PATH = PROJECT_DIRECTORY / ".data" / "deployment.txt"


def get_deployment_stamp() -> str:
    try:
        deployment_stamp = DEPLOYMENT_STAMP_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return f"v{APP_VERSION}"

    return deployment_stamp or f"v{APP_VERSION}"
