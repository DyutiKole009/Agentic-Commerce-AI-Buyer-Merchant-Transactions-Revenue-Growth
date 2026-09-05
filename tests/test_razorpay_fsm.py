import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_end_to_end_commerce_fsm_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        customer = await client.post("/api/v1/customers/register", json={"email": "fsm_customer@example.com", "customer_name": "FSM Customer", "password": "customer_password"})
        if customer.status_code == 409:
            customer = await client.post("/api/v1/customers/login", json={"email": "fsm_customer@example.com", "password": "customer_password"})
        token = customer.json()["token"]
        # 1. Start Session
        res = await client.post("/api/v1/commerce/session/start", json={"customer_token": token})
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        assert res.json()["current_state"] == "INTENT_RECEIVED"

        # 2. Extract Intent
        prompt = "I need wireless headphones under ₹5,000, with good battery life, for daily commuting. Prioritize noise cancellation."
        res = await client.post("/api/v1/commerce/intent/extract", json={"prompt": prompt, "session_id": session_id})
        assert res.status_code == 200
        assert res.json()["fsm_state"] == "INTENT_VALIDATED"

        # 3. Discover & Score Offers
        res = await client.post(f"/api/v1/commerce/orchestrate/discover-and-score?session_id={session_id}")
        assert res.status_code == 200
        fsm_state = res.json()["fsm_state"]
        assert fsm_state in ["AUTHORIZED", "AWAITING_AUTHORIZATION"]

        # If awaiting authorization (e.g. price > threshold), grant user approval
        if fsm_state == "AWAITING_AUTHORIZATION":
            auth_res = await client.post("/api/v1/commerce/policy/grant-user-approval", json={"session_id": session_id, "customer_token": token})
            assert auth_res.status_code == 200
            assert auth_res.json()["fsm_state"] == "AUTHORIZED"

        # 4. Create Razorpay Order
        res = await client.post(f"/api/v1/commerce/transaction/create-razorpay-order?session_id={session_id}")
        assert res.status_code == 200
        order_data = res.json()["order"]
        assert order_data["order_id"].startswith("order_")
        assert res.json()["fsm_state"] == "ORDER_CREATED"

        # 5. Simulate Successful Payment
        res = await client.post(f"/api/v1/commerce/transaction/simulate-success?session_id={session_id}")
        assert res.status_code == 200
        assert res.json()["fsm_state"] == "PURCHASE_COMPLETED"
        assert res.json()["snapshot"]["is_completed"] is True
