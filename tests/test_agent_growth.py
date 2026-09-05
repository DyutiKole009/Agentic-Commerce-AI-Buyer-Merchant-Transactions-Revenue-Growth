import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_agent_protocol_and_growth_approval_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        capabilities = await client.get("/api/v1/agent/capabilities")
        assert capabilities.status_code == 200
        assert "quote" in capabilities.json()["capabilities"]

        catalog = await client.get("/api/v1/agent/catalog")
        assert catalog.status_code == 200
        product_id = catalog.json()["products"][0]["product_id"]

        quote = await client.post("/api/v1/agent/quote", json={"product_id": product_id})
        assert quote.status_code == 200
        assert quote.json()["total"] > 0

        proposal = await client.post("/api/v1/agent/order", json={"product_id": product_id})
        assert proposal.status_code == 200
        assert proposal.json()["status"] == "PENDING_POLICY"

        dashboard = await client.get("/api/v1/merchant/dashboard")
        assert dashboard.status_code == 200
        opportunity = dashboard.json()["opportunities"][0]
        assert opportunity["status"] == "PROPOSED"

        approved = await client.post(
            f"/api/v1/merchant/opportunities/{opportunity['opportunity_id']}/approve",
            json={"approved_by": "merchant_electromax", "merchant_id": "merchant_electromax", "password": "demo_merchant_password"},
        )
        assert approved.status_code == 200
        assert approved.json()["policy_status"] == "APPROVED"

        executed = await client.post(
            f"/api/v1/merchant/opportunities/{opportunity['opportunity_id']}/execute"
        )
        assert executed.status_code == 200
        assert executed.json()["status"] == "EXECUTED"

        upsell = await client.post(
            "/api/v1/agent/upsell/quote",
            json={"base_product_id": opportunity["base_product_id"]},
        )
        assert upsell.status_code == 200
        assert upsell.json()["price"] == 799.0
