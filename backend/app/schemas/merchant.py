from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

class ProductFeatureMap(BaseModel):
    noise_cancellation: Optional[bool] = False
    anc_type: Optional[str] = "None" # "Active ANC", "Passive", "Hybrid ANC"
    battery_hours: Optional[int] = 0
    fast_charging: Optional[bool] = False
    water_resistance: Optional[str] = "None" # "IPX4", "IPX7", etc.
    bluetooth_version: Optional[str] = "5.0"
    microphone: Optional[bool] = True
    warranty_months: Optional[int] = 12

class MerchantProduct(BaseModel):
    product_id: str
    merchant_id: str
    merchant_name: str
    title: str
    category: str
    base_price: float
    currency: str = "INR"
    in_stock: bool
    stock_count: int
    features: ProductFeatureMap
    delivery_days: int
    seller_rating: float = Field(default=4.5, ge=1.0, le=5.0)
    image_url: Optional[str] = None
    description: Optional[str] = None

class MerchantOffer(BaseModel):
    offer_id: str
    merchant_id: str
    merchant_name: str
    product_id: str
    product_title: str
    price: float
    original_price: float
    discount_applied: float = 0.0
    currency: str = "INR"
    in_stock: bool
    delivery_days: int
    features: ProductFeatureMap
    merchant_notes: Optional[str] = None
    substitute_reasoning: Optional[str] = None # e.g., "Exact model out of stock; substituted higher-spec model with 10% auto-discount"
    satisfaction_ratio: float = 1.0 # ratio of user requirements met (e.g. 0.95)
    score_breakdown: Optional[Dict[str, float]] = None
    total_match_score: Optional[float] = 0.0
    purchase_endpoint: str
    order_token: str

class A2AQueryPayload(BaseModel):
    intent_spec: Dict[str, Any]
    buyer_agent_id: str
    max_delivery_days: Optional[int] = None
    allow_substitutions: bool = True
    protocol_version: str = "razorpay-agent-commerce-v1"
    request_id: Optional[str] = None
