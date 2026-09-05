import os
import uuid
from typing import Dict, List, Optional

import httpx

from app.schemas.growth import GrowthOpportunity, MerchantDashboard, MerchantMetrics
from app.schemas.merchant import MerchantProduct
from app.services.mock_merchants_db import MERCHANT_CATALOGS
from app.services.persistence import persistence


class GrowthAgent:
    def __init__(self):
        self.name = "Merchant Growth & Upsell Agent"
        self._opportunities: Dict[str, GrowthOpportunity] = {}
        self._build_opportunities()

    def _build_opportunities(self) -> None:
        catalogs = dict(MERCHANT_CATALOGS)
        catalogs.update({item["merchant_id"]: item for item in persistence.registered_merchants()})
        for merchant_id, catalog in catalogs.items():
            products: List[MerchantProduct] = [item if isinstance(item, MerchantProduct) else MerchantProduct(**item) for item in catalog.get("products", [])]
            if not products:
                continue
            base = products[0]
            recommended_price = 799.0 if merchant_id in MERCHANT_CATALOGS else round(base.base_price * 0.18 / 50) * 50
            product_metrics = persistence.product_metric_summary(merchant_id).get(base.product_id, {})
            observed_purchases = int(product_metrics.get("count", 0))
            observed_revenue = float(product_metrics.get("amount", 0))
            attach_rate = 0.12 if observed_purchases >= 5 else 0.08
            opportunity = GrowthOpportunity(
                opportunity_id=f"opp_{merchant_id}_bundle",
                merchant_id=merchant_id,
                title=f"{base.title} + travel case bundle",
                description="Offer a relevant accessory at checkout to increase basket value.",
                base_product_id=base.product_id,
                recommended_product_id=f"accessory_{merchant_id}_case",
                recommended_product_title="Protective Travel Case",
                recommended_price=recommended_price,
                expected_uplift=round(max(observed_revenue, base.base_price * max(observed_purchases, 1)) * attach_rate, 2),
                confidence=round(min(0.95, 0.35 + min(observed_purchases, 20) * 0.03), 2),
                channel="webhook",
                evidence_status="ESTIMATE",
            )
            self._opportunities[opportunity.opportunity_id] = opportunity

    def list_opportunities(self, merchant_id: Optional[str] = None) -> List[GrowthOpportunity]:
        opportunities = list(self._opportunities.values())
        if merchant_id:
            opportunities = [item for item in opportunities if item.merchant_id == merchant_id]
        return opportunities

    def approve_opportunity(self, opportunity_id: str, approved_by: str) -> GrowthOpportunity:
        opportunity = self._opportunities.get(opportunity_id)
        if not opportunity:
            raise KeyError(opportunity_id)
        opportunity.status = "APPROVED"
        opportunity.policy_status = "APPROVED"
        return opportunity

    def execute_opportunity(self, opportunity_id: str) -> GrowthOpportunity:
        opportunity = self._opportunities.get(opportunity_id)
        if not opportunity:
            raise KeyError(opportunity_id)
        if opportunity.status != "APPROVED" or opportunity.policy_status != "APPROVED":
            raise ValueError("Opportunity requires merchant approval before execution")
        payload = {
            "event": "merchant_campaign.approved",
            "campaign_id": opportunity.opportunity_id,
            "merchant_id": opportunity.merchant_id,
            "offer": {
                "base_product_id": opportunity.base_product_id,
                "recommended_product_id": opportunity.recommended_product_id,
                "recommended_product_title": opportunity.recommended_product_title,
                "price": opportunity.recommended_price,
            },
            "expected_uplift": opportunity.expected_uplift,
        }
        webhook_url = os.getenv("GROWTH_CAMPAIGN_WEBHOOK_URL")
        if webhook_url:
            try:
                response = httpx.post(webhook_url, json=payload, timeout=5.0)
                response.raise_for_status()
                opportunity.channel_status = "DISPATCHED"
                opportunity.channel_reference = response.headers.get("x-campaign-id") or str(uuid.uuid4())
            except httpx.HTTPError as error:
                opportunity.channel_status = "FAILED"
                raise ValueError(f"Campaign channel delivery failed: {error}") from error
        else:
            opportunity.channel_status = "SIMULATED"
            opportunity.channel_reference = f"local_{uuid.uuid4().hex[:10]}"
        opportunity.status = "EXECUTED"
        return opportunity

    def get_upsell_quote(self, base_product_id: str) -> Optional[dict]:
        opportunity = next(
            (item for item in self._opportunities.values() if item.base_product_id == base_product_id),
            None,
        )
        if not opportunity or opportunity.status not in {"APPROVED", "EXECUTED"}:
            return None
        return {
            "base_product_id": base_product_id,
            "recommended_product_id": opportunity.recommended_product_id,
            "recommended_product_title": opportunity.recommended_product_title,
            "price": opportunity.recommended_price,
            "reason": "Frequently purchased with this product and relevant to travel use.",
            "opportunity_id": opportunity.opportunity_id,
        }

    def dashboard(self, merchant_id: str = "merchant_electromax") -> MerchantDashboard:
        catalog = MERCHANT_CATALOGS.get(merchant_id) or next((item for item in persistence.registered_merchants() if item["merchant_id"] == merchant_id), None)
        if not catalog:
            raise KeyError(merchant_id)
        products = catalog.get("products", [])
        if merchant_id not in {item.merchant_id for item in self._opportunities.values()} and products:
            product = products[0] if isinstance(products[0], MerchantProduct) else MerchantProduct(**products[0])
            fallback_price = 799.0 if merchant_id in MERCHANT_CATALOGS else round(product.base_price * 0.18 / 50) * 50
            self._opportunities[f"opp_{merchant_id}_bundle"] = GrowthOpportunity(opportunity_id=f"opp_{merchant_id}_bundle", merchant_id=merchant_id, title=f"{product.title} + travel case bundle", description="Offer a relevant accessory at checkout to increase basket value.", base_product_id=product.product_id, recommended_product_id=f"accessory_{merchant_id}_case", recommended_product_title="Protective Travel Case", recommended_price=fallback_price, expected_uplift=round(product.base_price * 0.08, 2), confidence=0.35)
        opportunities = self.list_opportunities(merchant_id)
        executed = sum(item.status == "EXECUTED" for item in opportunities)
        summary = persistence.metric_summary(merchant_id)
        transactions = int(summary.get("PURCHASE_COMPLETED_count", 0))
        revenue = float(summary.get("PURCHASE_COMPLETED_amount", 0))
        impressions = int(summary.get("UPSELL_OFFERED_count", 0))
        conversions = int(summary.get("UPSELL_ACCEPTED_count", 0))
        incremental_revenue = float(summary.get("UPSELL_ACCEPTED_amount", 0))
        attach_rate = conversions / impressions if impressions else 0.0
        observed_aov = revenue / transactions if transactions else 0.0
        for opportunity in opportunities:
            opportunity.impressions = impressions
            opportunity.conversions = conversions
            opportunity.attach_rate = round(attach_rate, 4)
            opportunity.accepted_upsell_value = incremental_revenue
            opportunity.evidence_status = "MEASURED" if impressions else "ESTIMATE"
        metrics = MerchantMetrics(
            revenue=revenue,
            agent_generated_revenue=revenue,
            conversion_rate=1.0 if transactions else 0.0,
            average_order_value=revenue / transactions if transactions else 0.0,
            recommendations=len(opportunities),
            accepted_recommendations=executed,
            transactions=transactions,
            upsell_impressions=impressions,
            upsell_conversions=conversions,
            upsell_attach_rate=round(attach_rate, 4),
            accepted_upsell_value=incremental_revenue,
        )
        return MerchantDashboard(
            merchant_id=merchant_id,
            merchant_name=catalog["merchant_name"],
            metrics=metrics,
            opportunities=opportunities,
            policy={"max_campaign_budget": 50000.0, "max_discount_percentage": 10.0},
        )


growth_agent = GrowthAgent()
