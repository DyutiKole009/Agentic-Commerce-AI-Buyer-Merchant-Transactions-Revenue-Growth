import uuid
from typing import Dict, Any, Optional
from app.schemas.merchant import MerchantOffer
from app.schemas.policy import AuthorizationDecision
from app.schemas.transaction import RazorpayOrderPayload
from app.services.razorpay_service import razorpay_service

class TransactionAgent:
    def __init__(self):
        self.name = "Razorpay Transaction Execution Agent"

    async def initiate_razorpay_order(
        self,
        offer: MerchantOffer,
        auth_decision: AuthorizationDecision,
        session_id: str,
        customer_email: str = "customer@example.com",
        customer_contact: str = "+919876543210"
    ) -> RazorpayOrderPayload:
        """
        Executes order creation on Razorpay after validating policy authorization.
        """
        if not auth_decision.is_authorized or not auth_decision.approval_token:
            raise PermissionError("Transaction rejected: No valid policy authorization token provided.")

        receipt_id = f"rcpt_{session_id[-6:]}_{uuid.uuid4().hex[:4]}"
        
        notes = {
            "session_id": session_id,
            "merchant_id": offer.merchant_id,
            "merchant_name": offer.merchant_name,
            "product_id": offer.product_id,
            "product_title": offer.product_title,
            "auth_token": auth_decision.approval_token,
            "agent_orchestrator": "Track1_Agentic_Commerce"
        }

        # Create order through Razorpay Service
        order_res = razorpay_service.create_order(
            amount_in_inr=offer.price,
            receipt=receipt_id,
            notes=notes
        )

        return RazorpayOrderPayload(
            order_id=order_res["id"],
            amount=order_res["amount"],
            currency=order_res["currency"],
            receipt=order_res["receipt"],
            status=order_res["status"],
            notes=notes,
            key_id=order_res.get("key_id", "rzp_test_mock_agent_key"),
            is_simulated=order_res.get("is_simulated")
        )

transaction_agent = TransactionAgent()
