from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

class SpendPolicy(BaseModel):
    max_autonomous_spend: float = Field(default=4000.0, description="Autonomous spend cap")
    max_budget_ceiling: float = Field(default=10000.0, description="Hard budget ceiling")
    currency: str = Field(default="INR")
    allowed_categories: List[str] = Field(default_factory=lambda: ["electronics", "audio", "wearables", "accessories"])
    require_confirmation_above: float = Field(default=4000.0)
    allow_substitutes: bool = True
    min_merchant_rating: float = 4.0

class AuthorizationDecision(BaseModel):
    is_authorized: bool
    status: Literal["AUTO_APPROVED", "REQUIRES_USER_APPROVAL", "REJECTED_POLICY_VIOLATION"]
    reason: str
    mandate_limit: float
    requested_amount: float
    policy_checks: Dict[str, bool] = Field(default_factory=dict)
    approval_token: Optional[str] = None
    requires_interaction: bool = False
    details: Optional[Dict[str, Any]] = None

class UserMandateToken(BaseModel):
    mandate_id: str
    user_id: str
    max_amount: float
    currency: str = "INR"
    scope: str = "single_purchase"
    valid_until: str
    signature: str
