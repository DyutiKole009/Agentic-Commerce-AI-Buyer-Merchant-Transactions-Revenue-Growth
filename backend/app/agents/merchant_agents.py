import uuid
import json
from typing import Dict, Any, List, Optional
from app.schemas.merchant import MerchantOffer, MerchantProduct, ProductFeatureMap, A2AQueryPayload
from app.services.mock_merchants_db import MERCHANT_CATALOGS
from app.config import settings
from app.services.persistence import persistence
from openai import AsyncOpenAI

class MerchantAgent:
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        catalog_info = MERCHANT_CATALOGS.get(merchant_id, {})
        self.merchant_name = catalog_info.get("merchant_name", "Unknown Merchant")
        self.agent_name = catalog_info.get("agent_name", f"{self.merchant_name} Agent")
        self.seller_rating = catalog_info.get("seller_rating", 4.5)
        self.products: List[MerchantProduct] = catalog_info.get("products", [])
        self.endpoint = catalog_info.get("endpoint", "https://api.merchant.example/a2a")
        self.llm_client = AsyncOpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL) if settings.GROQ_API_KEY else None
        self.last_reasoning_source = "DETERMINISTIC_FALLBACK"

    async def evaluate_request(self, query: A2AQueryPayload) -> Optional[MerchantOffer]:
        """
        Reasoning on behalf of the merchant:
        1. Check product category & constraints
        2. Check stock & price
        3. Dynamically apply promotions or suggest higher-grade substitute if within budget
        4. Return tailored MerchantOffer
        """
        intent = query.intent_spec
        budget_max = intent.get("budget", {}).get("max", 5000.0)
        preferences = intent.get("preferences", {})
        high_anc_required = preferences.get("noise_cancellation") == "high priority"

        # Find best matching product in catalog
        best_product: Optional[MerchantProduct] = None
        applied_discount = 0.0
        reasoning_notes = []
        substitute_explanation = None

        for prod in self.products:
            if query.max_delivery_days is not None and prod.delivery_days > query.max_delivery_days:
                continue
            if high_anc_required and not prod.features.noise_cancellation and not query.allow_substitutions:
                continue
            # Check price flexibility / dynamic coupon
            effective_price = prod.base_price
            if prod.base_price > budget_max:
                # If product exceeds budget by <= 10%, merchant agent reasons to offer an auto-discount to close deal
                discount_needed = prod.base_price - budget_max
                if discount_needed <= (prod.base_price * 0.12):
                    effective_price = budget_max
                    applied_discount = round(discount_needed, 2)
                    reasoning_notes.append(
                        f"Applied dynamic merchant promotional coupon of ₹{applied_discount:.0f} to match customer budget (Base ₹{prod.base_price:.0f} -> ₹{effective_price:.0f})."
                    )
                else:
                    continue # Exceeds budget even with discount
            
            # Stock & Substitution logic
            if not prod.in_stock:
                continue

            # Check if this meets ANC requirements
            if high_anc_required and not prod.features.noise_cancellation:
                # Merchant agent notes missing feature
                reasoning_notes.append(f"Model lacks active ANC (passive isolation only), offered at competitive budget ₹{effective_price:.0f}.")
            else:
                reasoning_notes.append(f"Model strictly satisfies Active Noise Cancellation ({prod.features.anc_type}) & {prod.features.battery_hours}h battery.")

            best_product = prod
            break

        if not best_product:
            return None

        # Merchant specific reasoning
        if self.merchant_id == "merchant_soundvault":
            substitute_explanation = "Flagship AcoustiQ model selected with extended 40h battery & Dual ANC; merchant promotional discount applied."
        elif self.merchant_id == "merchant_electromax":
            substitute_explanation = "Direct stock match: SoundPro X2 ANC optimized for commuting with 32h battery."
        elif self.merchant_id == "merchant_budgetgizmos":
            substitute_explanation = "Budget-optimized option with 35h battery (Passive isolation, no Active ANC)."
        elif self.merchant_id == "merchant_sonicwave":
            substitute_explanation = "SonicWave Commute model with 30h battery and fast ambient mode."

        final_price = best_product.base_price - applied_discount

        # Calculate merchant's estimation of requirement satisfaction ratio
        satisfaction = 1.0
        if high_anc_required and not best_product.features.noise_cancellation:
            satisfaction = 0.65
        if final_price <= (budget_max * 0.9):
            satisfaction = min(1.0, satisfaction + 0.1)

        offer = MerchantOffer(
            offer_id=f"off_{self.merchant_id}_{uuid.uuid4().hex[:6]}",
            merchant_id=self.merchant_id,
            merchant_name=self.merchant_name,
            product_id=best_product.product_id,
            product_title=best_product.title,
            price=final_price,
            original_price=best_product.base_price,
            discount_applied=applied_discount,
            currency=best_product.currency,
            in_stock=best_product.in_stock,
            delivery_days=best_product.delivery_days,
            features=best_product.features,
            merchant_notes=" | ".join(reasoning_notes),
            substitute_reasoning=substitute_explanation,
            satisfaction_ratio=round(satisfaction, 2),
            purchase_endpoint=f"{self.endpoint}/checkout",
            order_token=f"tok_{uuid.uuid4().hex[:12]}"
        )
        if self.llm_client:
            try:
                response = await self.llm_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "You are a merchant commerce agent. Return JSON with reasoning and satisfaction_ratio between 0 and 1. Explain stock, price, discount, and requirement fit. Do not change the quoted price."},
                        {"role": "user", "content": json.dumps({"merchant": self.merchant_name, "request": intent, "offer": offer.model_dump()})},
                    ],
                )
                reasoning = json.loads(response.choices[0].message.content or "{}")
                offer.merchant_notes = reasoning.get("reasoning") or offer.merchant_notes
                if reasoning.get("satisfaction_ratio") is not None:
                    offer.satisfaction_ratio = max(0.0, min(1.0, float(reasoning["satisfaction_ratio"])))
                self.last_reasoning_source = "LLM"
                if response.usage:
                    persistence.record_usage(None, self.agent_name, "groq", settings.GROQ_MODEL, response.usage)
            except Exception:
                self.last_reasoning_source = "DETERMINISTIC_FALLBACK"
        return offer

    async def handle_a2a_query(self, query: A2AQueryPayload) -> Dict[str, Any]:
        """Handle the network-facing A2A contract and return a serializable response."""
        offer = await self.evaluate_request(query)
        return {
            "protocol": query.protocol_version,
            "request_id": query.request_id,
            "merchant_agent_id": self.merchant_id,
            "buyer_agent_id": query.buyer_agent_id,
            "offer": offer.model_dump() if offer else None,
        }

# Initialize the ecosystem of Merchant Agents
merchant_agents_pool: Dict[str, MerchantAgent] = {
    m_id: MerchantAgent(m_id) for m_id in MERCHANT_CATALOGS.keys()
}

for registered in persistence.registered_merchants():
    agent = MerchantAgent(registered["merchant_id"])
    agent.merchant_name = registered["merchant_name"]
    agent.agent_name = registered["agent_name"]
    agent.endpoint = registered["endpoint"]
    agent.products = [MerchantProduct(**product) for product in registered["products"]]
    merchant_agents_pool[registered["merchant_id"]] = agent
