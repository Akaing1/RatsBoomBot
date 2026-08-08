from fastapi import APIRouter

from config.settings import settings
from config.version import APP_NAME, APP_VERSION

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "application": APP_NAME,
        "version": APP_VERSION,
        "environment": settings.ENVIRONMENT
    }
