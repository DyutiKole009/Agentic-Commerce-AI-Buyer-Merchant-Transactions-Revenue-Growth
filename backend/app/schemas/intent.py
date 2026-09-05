from typing import Optional, Dict, List, Literal
from pydantic import BaseModel, Field

class BudgetSpec(BaseModel):
    max: float = Field(..., description="Maximum budget value")
    min: Optional[float] = Field(default=0.0, description="Minimum budget value")
    currency: str = Field(default="INR", description="Currency ISO code")

class ConstraintsSpec(BaseModel):
    brand: Optional[str] = None
    color: Optional[str] = None
    form_factor: Optional[str] = None
    max_delivery_days: Optional[int] = None

class PurchaseIntentSpecification(BaseModel):
    intent_id: str = Field(..., description="Unique ID for this purchase intent")
    product_category: str = Field(..., description="Normalized product category, e.g. 'wireless headphones'")
    raw_prompt: str = Field(..., description="Original user prompt")
    budget: BudgetSpec
    use_case: Optional[str] = Field(default="general", description="Primary use case, e.g. 'daily commuting', 'gaming', 'office'")
    preferences: Dict[str, Literal["high priority", "medium priority", "low priority", "optional"]] = Field(
        default_factory=dict,
        description="Attribute priority ratings (e.g. noise_cancellation, battery_life, water_resistance)"
    )
    constraints: ConstraintsSpec = Field(default_factory=ConstraintsSpec)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: str

class IntentExtractionRequest(BaseModel):
    prompt: str
    user_id: Optional[str] = "cust_demo_01"
    session_id: Optional[str] = None
