from typing import Any, Dict

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Agent Discovery"])


def _base_url() -> str:
    return settings.PUBLIC_BASE_URL.rstrip("/")


def _manifest() -> Dict[str, Any]:
    base = _base_url()
    api = settings.API_V1_STR
    return {
        "name": settings.PROJECT_NAME,
        "description": "Merchant catalog and policy-gated agentic commerce capabilities.",
        "version": settings.VERSION,
        "protocols": {
            "uap": {"version": "1", "query_endpoint": f"{base}{api}/agent/merchants/{{merchant_id}}/uap/query"},
            "google_ap2": {"version": "1", "query_endpoint": f"{base}{api}/agent/merchants/{{merchant_id}}/ap2/query"},
            "openai_acp": {"version": "1", "query_endpoint": f"{base}{api}/agent/merchants/{{merchant_id}}/acp/query"},
            "x402": {"version": "1", "query_endpoint": f"{base}{api}/agent/merchants/{{merchant_id}}/x402/query"},
        },
        "capabilities": ["catalog", "product", "search", "quote", "order", "upsell"],
        "catalog_url": f"{base}{api}/agent/catalog",
        "capabilities_url": f"{base}{api}/agent/capabilities",
        "openapi_url": f"{base}/openapi.json",
        "authentication": {"required": settings.API_AUTH_ENABLED, "header": "x-api-key"},
    }


@router.get("/.well-known/agent-manifest.json")
async def agent_manifest() -> Dict[str, Any]:
    return _manifest()


@router.get("/ai-plugin.json")
async def ai_plugin() -> Dict[str, Any]:
    base = _base_url()
    return {
        "schema_version": "v1",
        "name_for_model": "razorpay_merchant_catalog",
        "name_for_human": settings.PROJECT_NAME,
        "description_for_model": "Discover products and create policy-gated agentic commerce quotes.",
        "description_for_human": "Discover products and agentic checkout capabilities.",
        "auth": {"type": "none" if not settings.API_AUTH_ENABLED else "service_http", "instructions": "Use the x-api-key header." if settings.API_AUTH_ENABLED else ""},
        "api": {"type": "openapi", "url": f"{base}/openapi.json", "has_user_authentication": settings.API_AUTH_ENABLED},
        "logo_url": f"{base}/favicon.ico",
        "contact_email": "support@example.com",
        "legal_info_url": f"{base}/",
    }