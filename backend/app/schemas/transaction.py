from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field

PurchaseStateEnum = Literal[
    "INTENT_RECEIVED",
    "INTENT_VALIDATED",
    "MERCHANTS_DISCOVERED",
    "OFFERS_RECEIVED",
    "PRODUCT_SELECTED",
    "AWAITING_AUTHORIZATION",
    "AUTHORIZED",
    "ORDER_CREATED",
    "PAYMENT_INITIATED",
    "PAYMENT_VERIFIED",
    "PURCHASE_COMPLETED",
    "PAYMENT_FAILED",
    "FAILURE_ANALYSIS",
    "RECOVERY_ACTION",
    "PURCHASE_ABORTED"
]

class RazorpayOrderPayload(BaseModel):
    order_id: str
    amount: int # amount in paise
    currency: str = "INR"
    receipt: str
    status: str
    notes: Dict[str, str] = Field(default_factory=dict)
    checkout_url: Optional[str] = None
    key_id: Optional[str] = None
    is_simulated: Optional[bool] = None

class PaymentVerificationRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    session_id: str

class PaymentFailureEvent(BaseModel):
    code: str # e.g. "BAD_REQUEST_ERROR", "PAYMENT_METHOD_DECLINED", "GATEWAY_TIMEOUT"
    description: str
    source: str # "customer", "bank", "gateway", "razorpay"
    step: str
    reason: str
    payment_id: Optional[str] = None
    order_id: Optional[str] = None

class RecoveryStrategy(BaseModel):
    strategy_type: Literal["RETRY_SAME_GATEWAY", "SWITCH_PAYMENT_METHOD", "FALLBACK_MERCHANT_OFFER", "ABORT_PURCHASE"]
    diagnosis: str
    action_description: str
    target_merchant_id: Optional[str] = None
    target_offer_id: Optional[str] = None
    retry_delay_seconds: int = 0
    automated: bool = True
    attempt: int = 1
    max_attempts: int = 1
    retry_permitted: bool = True

class CommercialSessionState(BaseModel):
    session_id: str
    current_state: PurchaseStateEnum
    state_history: List[Dict[str, Any]] = Field(default_factory=list)
    intent_spec: Optional[Dict[str, Any]] = None
    discovered_merchants: List[str] = Field(default_factory=list)
    received_offers: List[Dict[str, Any]] = Field(default_factory=list)
    selected_offer: Optional[Dict[str, Any]] = None
    authorization_result: Optional[Dict[str, Any]] = None
    razorpay_order: Optional[Dict[str, Any]] = None
    payment_result: Optional[Dict[str, Any]] = None
    recovery_plan: Optional[Dict[str, Any]] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 1
    is_completed: bool = False
    is_failed: bool = False
    audit_logs: List[Dict[str, Any]] = Field(default_factory=list)
