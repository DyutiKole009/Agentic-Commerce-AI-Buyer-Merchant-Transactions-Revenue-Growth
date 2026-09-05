from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes_commerce import router as commerce_router
from app.api.routes_mandates import router as mandates_router
from app.api.routes_webhooks import router as webhooks_router
from app.api.routes_agent import router as agent_router
from app.api.routes_growth import router as growth_router
from app.api.routes_system import router as system_router
from app.api.routes_customers import router as customers_router
from app.api.routes_protocols import router as protocols_router
from app.api.routes_discovery import router as discovery_router
from app.api.auth import require_api_key

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Full Closed-Loop Agentic Commerce Platform with Razorpay Transaction Layer (Track 1)"
)

# Enable CORS for local dev and frontend dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Agent-Protocol",
        "X-Agent-Protocol-Version",
        "X-Agent-Request-ID",
        "PAYMENT-REQUIRED",
        "X-Payment-Required",
    ],
)

@app.middleware("http")
async def api_authentication(request, call_next):
    if request.url.path.startswith(settings.API_V1_STR):
        await require_api_key(request.headers.get("x-api-key"))
    return await call_next(request)

# Include Routers
app.include_router(commerce_router, prefix=settings.API_V1_STR)
app.include_router(mandates_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router, prefix=settings.API_V1_STR)
app.include_router(agent_router, prefix=settings.API_V1_STR)
app.include_router(growth_router, prefix=settings.API_V1_STR)
app.include_router(system_router, prefix=settings.API_V1_STR)
app.include_router(customers_router, prefix=settings.API_V1_STR)
app.include_router(protocols_router, prefix=settings.API_V1_STR)
app.include_router(discovery_router)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
