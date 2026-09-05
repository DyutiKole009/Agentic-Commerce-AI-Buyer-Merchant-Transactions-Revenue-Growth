from fastapi import Header, HTTPException

from app.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.API_AUTH_ENABLED:
        if not settings.API_AUTH_TOKEN:
            raise HTTPException(status_code=500, detail="API_AUTH_TOKEN is not configured")
        if x_api_key != settings.API_AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")