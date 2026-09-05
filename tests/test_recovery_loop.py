import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_failure_diagnosis_and_recovery_loop():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        customer = await client.post("/api/v1/customers/register", json={"email": "recovery_customer@example.com", "customer_name": "Recovery Customer", "password": "customer_password"})
        if customer.status_code == 409:
            customer = await client.post("/api/v1/customers/login", json={"email": "recovery_customer@example.com", "password": "customer_password"})
        token = customer.json()["token"]
        # Start and advance session to ORDER_CREATED
        res = await client.post("/api/v1/commerce/session/start", json={"customer_token": token})
        session_id = res.json()["session_id"]
        
        await client.post("/api/v1/commerce/intent/extract", json={
            "prompt": "I need wireless headphones under ₹5,000 for daily commuting with noise cancellation.",
            "session_id": session_id
        })
        
        score_res = await client.post(f"/api/v1/commerce/orchestrate/discover-and-score?session_id={session_id}")
        if score_res.json()["fsm_state"] == "AWAITING_AUTHORIZATION":
            await client.post("/api/v1/commerce/policy/grant-user-approval", json={"session_id": session_id, "customer_token": token})
        
        await client.post(f"/api/v1/commerce/transaction/create-razorpay-order?session_id={session_id}")

        # Inject Failure: MERCHANT_STOCK_CHANGED
        fail_res = await client.post("/api/v1/commerce/transaction/simulate-failure", json={
            "session_id": session_id,
            "error_type": "MERCHANT_STOCK_CHANGED"
        })
        assert fail_res.status_code == 200
        assert fail_res.json()["fsm_state"] == "RECOVERY_ACTION"
        recovery_plan = fail_res.json()["recovery_plan"]
        assert recovery_plan["strategy_type"] == "FALLBACK_MERCHANT_OFFER"
        assert recovery_plan["target_merchant_id"] is not None

        # Execute recovery: Switches to fallback merchant without starting over!
        rec_res = await client.post(f"/api/v1/commerce/transaction/execute-recovery?session_id={session_id}")
        assert rec_res.status_code == 200
        assert rec_res.json()["fsm_state"] == "ORDER_CREATED"

        # Now complete payment on the recovered order
        succ_res = await client.post(f"/api/v1/commerce/transaction/simulate-success?session_id={session_id}")
        assert succ_res.status_code == 200
        assert succ_res.json()["fsm_state"] == "PURCHASE_COMPLETED"
