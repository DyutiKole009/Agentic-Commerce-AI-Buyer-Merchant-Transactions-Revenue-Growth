import uuid
from typing import Dict, Any, Optional
from app.schemas.policy import SpendPolicy, AuthorizationDecision
from app.schemas.merchant import MerchantOffer
from app.schemas.intent import PurchaseIntentSpecification
from app.services.policy_kb import policy_kb
from app.services.persistence import persistence

class PolicyAgent:
    def __init__(self, default_policy: Optional[SpendPolicy] = None):
        self.name = "Policy & Authorization Guardrail Agent"
        self.policy = default_policy or SpendPolicy()

    def update_policy(self, new_policy: SpendPolicy):
        self.policy = new_policy

    def evaluate_authorization(
        self,
        offer: MerchantOffer,
        intent_spec: PurchaseIntentSpecification,
        user_mandate_override: Optional[float] = None,
        explicit_consent: bool = False
    ) -> AuthorizationDecision:
        """
        Enforces policy boundaries separating User Intent from Agent Authorization.
        """
        active_record = persistence.get_active_policy(offer.merchant_id)
        active_policy = SpendPolicy(**active_record["constraints"]) if active_record else self.policy
        price = offer.price
        category = intent_spec.product_category.lower()
        autonomous_limit = user_mandate_override if user_mandate_override is not None else active_policy.max_autonomous_spend
        confirmation_threshold = active_policy.require_confirmation_above

        blocked_categories = active_record["constraints"].get("blocked_categories", []) if active_record else []
        category_match = (any(c in category or category in c for c in active_policy.allowed_categories) or any(w in category for w in ["headphone", "earbud", "audio", "electronic", "wearable", "gadget", "watch"])) and not any(blocked in category for blocked in blocked_categories)
        checks = {
            "within_budget_ceiling": price <= intent_spec.budget.max,
            "category_whitelisted": category_match,
            "below_autonomous_limit": price <= autonomous_limit,
            "below_confirmation_threshold": price <= confirmation_threshold
        }

        # Check Category policy
        if not checks["category_whitelisted"]:
            return AuthorizationDecision(
                is_authorized=False,
                status="REJECTED_POLICY_VIOLATION",
                reason=f"Product category '{intent_spec.product_category}' is outside allowed categories: {active_policy.allowed_categories}",
                mandate_limit=autonomous_limit,
                requested_amount=price,
                policy_checks=checks,
                requires_interaction=False
            )

        # Check Budget Ceiling
        if not checks["within_budget_ceiling"]:
            return AuthorizationDecision(
                is_authorized=False,
                status="REJECTED_POLICY_VIOLATION",
                reason=f"Price ₹{price:.0f} exceeds maximum budget ceiling of ₹{intent_spec.budget.max:.0f}.",
                mandate_limit=autonomous_limit,
                requested_amount=price,
                policy_checks=checks,
                requires_interaction=False
            )

        # Evaluate if Autonomous or Interactive
        if checks["below_autonomous_limit"] and (checks["below_confirmation_threshold"] or explicit_consent):
            token = f"auth_token_auto_{uuid.uuid4().hex[:12]}"
            return AuthorizationDecision(
                is_authorized=True,
                status="AUTO_APPROVED",
                reason=f"Purchase price ₹{price:.0f} is within autonomous limit ₹{autonomous_limit:.0f} and category '{intent_spec.product_category}' is approved.",
                mandate_limit=autonomous_limit,
                requested_amount=price,
                policy_checks=checks,
                approval_token=token,
                requires_interaction=False,
                details={
                    "mode": "AUTONOMOUS_EXECUTION",
                    "mandate_limit": autonomous_limit,
                    "savings_against_budget": intent_spec.budget.max - price,
                    "policy_id": active_record["policy_id"] if active_record else "static_default",
                    "policy_version": active_record["version"] if active_record else 0,
                    "policy_hash": active_record["content_hash"] if active_record else None,
                    "policy_source": active_record["source_name"] if active_record else None,
                    "policy_effective_from": active_record["effective_from"] if active_record else None,
                    "retrieved_clauses": policy_kb.retrieve(f"{intent_spec.product_category} purchase price {price}", merchant_id=offer.merchant_id)
                }
            )
        else:
            # Requires interactive user sign-off
            return AuthorizationDecision(
                is_authorized=False,
                status="REQUIRES_USER_APPROVAL",
                reason=f"Price ₹{price:.0f} exceeds autonomous spending threshold ₹{confirmation_threshold:.0f}. Interactive customer authorization required.",
                mandate_limit=autonomous_limit,
                requested_amount=price,
                policy_checks=checks,
                approval_token=None,
                requires_interaction=True,
                details={
                    "mode": "INTERACTIVE_CONFIRMATION_REQUIRED",
                    "confirmation_threshold": confirmation_threshold,
                    "excess_amount": price - confirmation_threshold
                    ,"retrieved_clauses": policy_kb.retrieve(f"{intent_spec.product_category} purchase price {price}", merchant_id=offer.merchant_id)
                }
            )

    def recheck_before_payment(self, offer: MerchantOffer, intent_spec: PurchaseIntentSpecification, previous: AuthorizationDecision) -> AuthorizationDecision:
        explicit = (previous.details or {}).get("mode") == "EXPLICIT_USER_CONSENT"
        return self.evaluate_authorization(offer, intent_spec, user_mandate_override=offer.price if explicit else None, explicit_consent=explicit)

    def grant_user_approval(self, offer: MerchantOffer, user_id: str = "cust_01") -> AuthorizationDecision:
        """
        Called when the customer clicks 'Approve Purchase' in the UI.
        """
        token = f"auth_token_user_approved_{uuid.uuid4().hex[:12]}"
        return AuthorizationDecision(
            is_authorized=True,
            status="AUTO_APPROVED",
            reason=f"Explicit authorization granted by user {user_id} for ₹{offer.price:.0f}.",
            mandate_limit=offer.price,
            requested_amount=offer.price,
            policy_checks={"user_explicit_consent": True},
            approval_token=token,
            requires_interaction=False,
            details={"mode": "EXPLICIT_USER_CONSENT"}
        )

policy_agent = PolicyAgent()
