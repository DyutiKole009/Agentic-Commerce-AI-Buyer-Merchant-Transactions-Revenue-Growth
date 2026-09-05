from fastapi import APIRouter

from app.services.persistence import persistence
from app.services.razorpay_service import razorpay_service
from app.config import settings

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/status")
async def system_status():
    return {
        "status": "healthy",
        "razorpay": razorpay_service.status(),
        "llm": {
            "configured": bool(settings.GROQ_API_KEY),
            "provider": "groq",
            "model": settings.GROQ_MODEL,
        },
        "database": {"engine": "postgresql", "provider": "supabase", "configured": bool(persistence.path)},
        "authentication": {"enabled": settings.API_AUTH_ENABLED},
    }


@router.get("/usage")
async def usage(session_id: str | None = None):
    return persistence.usage_summary(session_id)