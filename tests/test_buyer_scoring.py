import pytest
from app.agents.intent_agent import intent_agent
from app.agents.buyer_agent import buyer_agent

@pytest.mark.asyncio
async def test_requirement_aware_scoring_prefers_anc():
    prompt = "I need wireless headphones under ₹5,000, with good battery life, for daily commuting. Prioritize noise cancellation."
    spec = await intent_agent.extract_intent(prompt)
    
    discovered = await buyer_agent.discover_merchants(spec)
    assert len(discovered) >= 3
    
    raw_offers = await buyer_agent.collect_merchant_offers(spec, discovered)
    assert len(raw_offers) >= 3
    
    winner, ranked, narrative = await buyer_agent.select_best_offer(raw_offers, spec)
    
    # The winner MUST have active noise cancellation because user prioritized ANC
    assert winner.features.noise_cancellation is True
    assert winner.price <= 5000.0
    assert winner.total_match_score > 75.0
    
    # Check that non-ANC cheap offer (e.g. BudgetGizmos at ₹3,900) did not win simply by being cheap
    bg_offer = next((o for o in ranked if "budgetgizmos" in o.merchant_id), None)
    if bg_offer:
        assert winner.total_match_score > bg_offer.total_match_score
