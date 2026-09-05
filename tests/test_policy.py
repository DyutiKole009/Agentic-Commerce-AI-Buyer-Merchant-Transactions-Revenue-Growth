import pytest
from app.agents.policy_agent import PolicyAgent
from app.schemas.policy import SpendPolicy
from app.schemas.merchant import MerchantOffer, ProductFeatureMap
from app.schemas.intent import PurchaseIntentSpecification, BudgetSpec

def test_intent_is_not_authorization_boundary():
    # Setup policy with ₹4,000 autonomous confirmation threshold
    policy = SpendPolicy(max_autonomous_spend=4000.0, require_confirmation_above=4000.0)
    agent = PolicyAgent(default_policy=policy)
    
    intent = PurchaseIntentSpecification(
        intent_id="int_01",
        product_category="wireless headphones",
        raw_prompt="under ₹5000",
        budget=BudgetSpec(max=5000.0),
        created_at="2026-09-04T12:00:00Z"
    )
    
    # Offer A: ₹3,500 (Below confirmation threshold -> AUTO_APPROVED)
    offer_a = MerchantOffer(
        offer_id="off_a",
        merchant_id="m_a",
        merchant_name="Store A",
        product_id="p_a",
        product_title="Budget ANC",
        price=3500.0,
        original_price=3500.0,
        in_stock=True,
        delivery_days=2,
        features=ProductFeatureMap(noise_cancellation=True),
        purchase_endpoint="/pay",
        order_token="tok_1"
    )
    decision_a = agent.evaluate_authorization(offer_a, intent)
    assert decision_a.is_authorized is True
    assert decision_a.status == "AUTO_APPROVED"
    assert decision_a.approval_token is not None
    
    # Offer B: ₹4,800 (Above ₹4,000 threshold, but within ₹5,000 budget -> REQUIRES_USER_APPROVAL)
    offer_b = MerchantOffer(
        offer_id="off_b",
        merchant_id="m_b",
        merchant_name="Store B",
        product_id="p_b",
        product_title="Premium Pro ANC",
        price=4800.0,
        original_price=4800.0,
        in_stock=True,
        delivery_days=1,
        features=ProductFeatureMap(noise_cancellation=True),
        purchase_endpoint="/pay",
        order_token="tok_2"
    )
    decision_b = agent.evaluate_authorization(offer_b, intent)
    assert decision_b.is_authorized is False
    assert decision_b.status == "REQUIRES_USER_APPROVAL"
    assert decision_b.requires_interaction is True
