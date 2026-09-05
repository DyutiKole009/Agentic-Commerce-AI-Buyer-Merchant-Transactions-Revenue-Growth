import pytest
from app.agents.intent_agent import intent_agent

@pytest.mark.asyncio
async def test_headphones_commute_intent():
    prompt = "I need wireless headphones under ₹5,000, with good battery life, for daily commuting. Prioritize noise cancellation."
    spec = await intent_agent.extract_intent(prompt)
    
    assert spec.product_category == "wireless headphones"
    assert spec.budget.max == 5000.0
    assert spec.budget.currency == "INR"
    assert spec.use_case == "daily commuting"
    assert spec.preferences.get("noise_cancellation") == "high priority"
    assert spec.preferences.get("battery_life") == "high priority"

@pytest.mark.asyncio
async def test_k_notation_budget():
    prompt = "Get me ANC earbuds under 4k with fast delivery"
    spec = await intent_agent.extract_intent(prompt)
    
    assert spec.budget.max == 4000.0
    assert spec.constraints.max_delivery_days == 1
