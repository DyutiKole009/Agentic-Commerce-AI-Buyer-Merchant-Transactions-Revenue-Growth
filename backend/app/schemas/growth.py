from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AgentSearchRequest(BaseModel):
    category: str
    max_price: Optional[float] = None
    max_delivery_days: Optional[int] = None


class AgentQuoteRequest(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=20)


class AgentOrderRequest(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=20)
    buyer_agent_id: str = "external_buyer_agent"


class UpsellQuoteRequest(BaseModel):
    base_product_id: str
    session_id: Optional[str] = None


class UpsellAcceptanceRequest(BaseModel):
    base_product_id: str
    session_id: str


class GrowthOpportunity(BaseModel):
    opportunity_id: str
    merchant_id: str
    title: str
    description: str
    base_product_id: str
    recommended_product_id: str
    recommended_product_title: str
    recommended_price: float
    expected_uplift: float
    confidence: float = Field(ge=0, le=1)
    status: Literal["PROPOSED", "APPROVED", "EXECUTED"] = "PROPOSED"
    policy_status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    channel: str = "webhook"
    channel_status: Literal["NOT_DISPATCHED", "DISPATCHED", "SIMULATED", "FAILED"] = "NOT_DISPATCHED"
    channel_reference: Optional[str] = None
    impressions: int = 0
    conversions: int = 0
    attach_rate: float = 0.0
    accepted_upsell_value: float = 0.0
    evidence_status: Literal["ESTIMATE", "MEASURED"] = "ESTIMATE"


class GrowthApprovalRequest(BaseModel):
    approved_by: str = "merchant_admin"
    merchant_id: str
    password: Optional[str] = Field(default=None, min_length=1)
    merchant_token: Optional[str] = None


class MerchantMetrics(BaseModel):
    revenue: float
    agent_generated_revenue: float
    conversion_rate: float
    average_order_value: float
    recommendations: int
    accepted_recommendations: int
    transactions: int
    upsell_impressions: int = 0
    upsell_conversions: int = 0
    upsell_attach_rate: float = 0.0
    accepted_upsell_value: float = 0.0


class MerchantDashboard(BaseModel):
    merchant_id: str
    merchant_name: str
    metrics: MerchantMetrics
    opportunities: List[GrowthOpportunity]
    policy: Dict[str, float]
