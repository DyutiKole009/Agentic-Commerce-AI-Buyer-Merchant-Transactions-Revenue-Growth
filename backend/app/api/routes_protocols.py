import base64
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Response

from app.agents.merchant_agents import merchant_agents_pool
from app.config import settings
from app.schemas.protocols import (
    ACPQueryRequest,
    AP2QueryRequest,
    PaymentRequired,
    PaymentRequirement,
    protocol_headers,
)

router = APIRouter(prefix="/agent/merchants/{merchant_id}", tags=["Protocol Interoperability"])


async def _query_merchant(merchant_id: str, request: Any) -> Dict[str, Any]:
    agent = merchant_agents_pool.get(merchant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Merchant agent not found")
    result = await agent.handle_a2a_query(request.to_a2a())
    if result.get("offer") is None:
        raise HTTPException(status_code=204, detail="Merchant cannot satisfy request")
    return result


@router.post("/uap/query")
async def uap_query(merchant_id: str, request: AP2QueryRequest, response: Response) -> Dict[str, Any]:
    """Universal Agent Protocol envelope backed by the canonical A2A adapter."""
    response.headers.update(protocol_headers("uap", "1", request.request_id))
    return {"protocol": "uap", "response": await _query_merchant(merchant_id, request)}


@router.post("/ap2/query")
async def ap2_query(merchant_id: str, request: AP2QueryRequest, response: Response) -> Dict[str, Any]:
    response.headers.update(protocol_headers("google-ap2", "1", request.request_id))
    return {
        "protocol": "google-ap2",
        "mandate_id": request.mandate_id,
        "cart_id": request.cart_id,
        "response": await _query_merchant(merchant_id, request),
    }


@router.post("/acp/query")
async def acp_query(merchant_id: str, request: ACPQueryRequest, response: Response) -> Dict[str, Any]:
    response.headers.update(protocol_headers("openai-acp", "1", request.request_id))
    return {
        "protocol": "openai-acp",
        "checkout_session_id": request.checkout_session_id,
        "merchant_of_record": request.merchant_of_record,
        "response": await _query_merchant(merchant_id, request),
    }


@router.post("/x402/query")
async def x402_query(
    merchant_id: str,
    request: AP2QueryRequest,
    response: Response,
    payment_signature: Optional[str] = Header(default=None, alias="PAYMENT-SIGNATURE"),
    legacy_payment: Optional[str] = Header(default=None, alias="X-PAYMENT"),
    l402_authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Dict[str, Any]:
    response.headers.update(protocol_headers("x402", "1", request.request_id))
    payment_proof = payment_signature or legacy_payment or l402_authorization
    if not payment_proof:
        challenge = PaymentRequired(
            accepts=[PaymentRequirement(
                amount="0",
                pay_to=settings.X402_PAY_TO,
                resource=f"/api/v1/agent/merchants/{merchant_id}/x402/query",
            )]
        )
        encoded = base64.b64encode(challenge.model_dump_json().encode()).decode()
        raise HTTPException(
            status_code=402,
            detail=challenge.model_dump(),
            headers={
                **protocol_headers("x402", "1", request.request_id),
                "PAYMENT-REQUIRED": encoded,
                "X-Payment-Required": json.dumps(challenge.model_dump()),
            },
        )
    return {
        "protocol": "l402" if l402_authorization else "x402",
        "payment_verified": False,
        "payment_proof_received": True,
        "response": await _query_merchant(merchant_id, request),
    }