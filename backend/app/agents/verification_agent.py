from typing import Dict, Any, List, Optional, Tuple
from app.schemas.transaction import RecoveryStrategy, PaymentVerificationRequest
from app.schemas.merchant import MerchantOffer
from app.services.razorpay_service import razorpay_service

class ClosedLoopVerificationAgent:
    def __init__(self):
        self.name = "Closed-Loop Verification & Self-Healing Agent"

    def verify_payment_outcome(self, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies Razorpay payment signature and transaction authenticity.
        """
        order_id = verification_data.get("razorpay_order_id")
        payment_id = verification_data.get("razorpay_payment_id")
        signature = verification_data.get("razorpay_signature")

        is_valid = razorpay_service.verify_payment_signature(order_id, payment_id, signature)

        if not is_valid:
            return {
                "verified": False,
                "status": "SIGNATURE_VERIFICATION_FAILED",
                "message": "Payment signature mismatch. Transaction cannot be verified."
            }

        return {
            "verified": True,
            "status": "PAYMENT_CAPTURED_AND_VERIFIED",
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "fulfillment_status": "MERCHANT_ORDER_CONFIRMED",
            "message": "Transaction verified via Razorpay. Order confirmed with Merchant."
        }

    def diagnose_failure_and_plan_recovery(
        self,
        failure_event: Dict[str, Any],
        ranked_offers: List[Dict[str, Any]],
        current_offer: Dict[str, Any],
        attempt: int = 1,
        max_attempts: int = 1,
    ) -> RecoveryStrategy:
        """
        Autonomous Closed-Loop Recovery Reasoning Engine.
        Analyzes failure root-cause and formulates the recovery path.
        """
        error_code = failure_event.get("error_code", "")
        error_source = failure_event.get("error_source", "")
        error_desc = failure_event.get("error_description", "")
        retry_permitted = attempt <= max_attempts

        if not retry_permitted:
            return RecoveryStrategy(
                strategy_type="ABORT_PURCHASE",
                diagnosis="The bounded recovery budget has been exhausted.",
                action_description="No further payment attempt was made. Customer authorization is required for a new attempt.",
                target_merchant_id=current_offer.get("merchant_id"),
                target_offer_id=current_offer.get("offer_id"),
                automated=False,
                attempt=attempt,
                max_attempts=max_attempts,
                retry_permitted=False,
            )

        # 1. Merchant Stock conflict / Merchant issue -> Switch to runner-up offer
        if "INVENTORY" in error_code or "MERCHANT" in error_source.upper() or "stock" in error_desc.lower():
            # Find next best alternative offer from a different merchant
            runner_up = None
            for off in ranked_offers:
                if off.get("merchant_id") != current_offer.get("merchant_id") and off.get("in_stock", True):
                    runner_up = off
                    break

            if runner_up:
                return RecoveryStrategy(
                    strategy_type="FALLBACK_MERCHANT_OFFER",
                    diagnosis="Primary merchant encountered inventory lock conflict during checkout window.",
                    action_description=f"Auto-switching order to 2nd-best alternative: {runner_up.get('merchant_name')} '{runner_up.get('product_title')}' (₹{runner_up.get('price'):.0f}, Match Score: {runner_up.get('total_match_score')}).",
                    target_merchant_id=runner_up.get("merchant_id"),
                    target_offer_id=runner_up.get("offer_id"),
                    retry_delay_seconds=0,
                    automated=True
                    , attempt=attempt, max_attempts=max_attempts, retry_permitted=True
                )

        # 2. Bank Technical / 3DS Timeout -> Retry with instant UPI Intent
        if "BAD_REQUEST" in error_code or "bank" in error_source.lower() or "timeout" in error_desc.lower():
            return RecoveryStrategy(
                strategy_type="RETRY_SAME_GATEWAY",
                diagnosis="Transient 3D Secure / Issuer bank latency spike detected.",
                action_description="Re-routing transaction through Razorpay Fast-Track UPI Rails with 1-second auto-backoff.",
                target_merchant_id=current_offer.get("merchant_id"),
                target_offer_id=current_offer.get("offer_id"),
                retry_delay_seconds=1,
                automated=True, attempt=attempt, max_attempts=max_attempts, retry_permitted=True
            )

        # 3. Card limit or decline -> Switch method
        if "LIMIT" in error_code or "card" in error_source.lower() or "decline" in error_desc.lower():
            return RecoveryStrategy(
                strategy_type="SWITCH_PAYMENT_METHOD",
                diagnosis="Payment method declined due to card spend threshold.",
                action_description="Switching checkout intent to Razorpay NetBanking / Direct UPI VPA.",
                target_merchant_id=current_offer.get("merchant_id"),
                target_offer_id=current_offer.get("offer_id"),
                retry_delay_seconds=0,
                automated=True, attempt=attempt, max_attempts=max_attempts, retry_permitted=True
            )

        # Default: Retry with fallback route
        return RecoveryStrategy(
            strategy_type="RETRY_SAME_GATEWAY",
            diagnosis="Temporary gateway glitch.",
            action_description="Retrying Razorpay order settlement.",
            target_merchant_id=current_offer.get("merchant_id"),
            target_offer_id=current_offer.get("offer_id"),
            retry_delay_seconds=1,
            automated=True, attempt=attempt, max_attempts=max_attempts, retry_permitted=True
        )

verification_agent = ClosedLoopVerificationAgent()
