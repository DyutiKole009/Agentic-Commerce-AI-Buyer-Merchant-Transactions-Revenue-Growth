from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.schemas.merchant import A2AQueryPayload


class ProtocolQueryBase(BaseModel):
    """Common external-agent fields mapped to the canonical A2A query."""

    intent_spec: Dict[str, Any] = Field(default_factory=dict)
    buyer_agent_id: str = Field(min_length=1)
    max_delivery_days: Optional[int] = Field(default=None, ge=1)
    allow_substitutions: bool = True
    request_id: Optional[str] = None

    def to_a2a(self) -> A2AQueryPayload:
        return A2AQueryPayload(
            intent_spec=self.intent_spec,
            buyer_agent_id=self.buyer_agent_id,
            max_delivery_days=self.max_delivery_days,
            allow_substitutions=self.allow_substitutions,
            request_id=self.request_id,
        )


class AP2QueryRequest(ProtocolQueryBase):
    """AP2 cart/mandate context carried alongside the purchase intent."""

    mandate_id: Optional[str] = None
    cart_id: Optional[str] = None


class ACPQueryRequest(ProtocolQueryBase):
    """ACP checkout context carried alongside the purchase intent."""

    checkout_session_id: Optional[str] = None
    merchant_of_record: Optional[str] = None


class PaymentRequirement(BaseModel):
    scheme: str = "exact"
    network: str = "base-sepolia"
    asset: str = "USDC"
    amount: str
    pay_to: str
    resource: str


class PaymentRequired(BaseModel):
    x402_version: int = 1
    accepts: list[PaymentRequirement]


def protocol_headers(protocol: str, version: str, request_id: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "X-Agent-Protocol": protocol,
        "X-Agent-Protocol-Version": version,
        "Vary": "X-Agent-Protocol, X-Agent-Protocol-Version",
    }
    if request_id:
        headers["X-Agent-Request-ID"] = request_id
    return headers