import uuid
import json
import asyncio
import time
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.fsm import PurchaseStateMachine
from app.core.event_bus import event_bus
from app.schemas.intent import IntentExtractionRequest, PurchaseIntentSpecification
from app.schemas.merchant import MerchantOffer
from app.schemas.transaction import PaymentVerificationRequest
from app.agents.intent_agent import intent_agent
from app.agents.buyer_agent import buyer_agent
from app.agents.policy_agent import policy_agent
from app.agents.transaction_agent import transaction_agent
from app.agents.verification_agent import verification_agent
from app.services.razorpay_service import razorpay_service
from app.services.persistence import persistence
from app.services.growth_agent import growth_agent

router = APIRouter(prefix="/commerce", tags=["Agentic Commerce"])

# Active sessions store
ACTIVE_SESSIONS: Dict[str, PurchaseStateMachine] = {}

class StartSessionRequest(BaseModel):
    customer_token: str
    session_name: Optional[str] = "Live Commerce Session"

class ApprovalRequest(BaseModel):
    session_id: str
    customer_token: str

class SimulateFailureRequest(BaseModel):
    session_id: str
    error_type: Optional[str] = "BANK_TECHNICAL_ERROR" # or "MERCHANT_STOCK_CHANGED", "CARD_LIMIT_EXCEEDED"

class UpsellDecisionRequest(BaseModel):
    session_id: str
    accept: bool

@router.post("/session/start")
async def start_session(req: StartSessionRequest):
    user_id = persistence.customer_from_token(req.customer_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Customer authentication required")
    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    fsm = PurchaseStateMachine(session_id, user_id)
    ACTIVE_SESSIONS[session_id] = fsm
    
    await event_bus.emit(session_id, "SESSION_INITIALIZED", {
        "session_id": session_id,
        "state": fsm.current_state,
        "message": "Commercial session initiated with deterministic FSM."
    })
    
    return fsm.get_snapshot()

@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str):
    fsm = ACTIVE_SESSIONS.get(session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")
    return fsm.get_snapshot()

@router.get("/session/{session_id}/stream")
async def stream_session_events(session_id: str):
    queue = event_bus.subscribe(session_id)

    async def event_generator():
        try:
            # Send initial greeting/keepalive
            yield f"data: {json.dumps({'event_type': 'CONNECTED', 'session_id': session_id})}\n\n"
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            event_bus.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/intent/extract")
async def extract_purchase_intent(req: IntentExtractionRequest):
    session_id = req.session_id
    if not session_id or session_id not in ACTIVE_SESSIONS:
        raise HTTPException(status_code=401, detail="Authenticated customer session required")
    
    fsm = ACTIVE_SESSIONS[session_id]
    
    # 1. Intent Extraction Agent
    intent_started = time.perf_counter()
    intent_spec = await intent_agent.extract_intent(req.prompt, session_id)
    intent_latency_ms = round((time.perf_counter() - intent_started) * 1000)
    fsm.session_data["intent_spec"] = intent_spec.model_dump()
    extraction_source = intent_agent.last_source
    fsm.session_data["intent_source"] = extraction_source
    fsm.log_audit(
        "INTENT_EXTRACTED",
        f"Intent extracted using {extraction_source}.",
        {"source": extraction_source, "intent_id": intent_spec.intent_id, "from_agent": intent_agent.name, "latency_ms": intent_latency_ms, "input_tokens_estimate": (len(req.prompt) + 3) // 4, "output_tokens_estimate": (len(intent_spec.model_dump_json()) + 3) // 4},
    )
    
    # Transition FSM: INTENT_RECEIVED -> INTENT_VALIDATED
    fsm.transition_to("INTENT_VALIDATED", reason="Intent successfully structured and constraints normalized", metadata=intent_spec.model_dump())
    
    await event_bus.emit(session_id, "INTENT_EXTRACTED", {
        "intent_spec": intent_spec.model_dump(),
        "source": extraction_source,
        "fsm_state": fsm.current_state
    })
    
    return {
        "session_id": session_id,
        "intent_spec": intent_spec,
        "intent_source": extraction_source,
        "fsm_state": fsm.current_state,
        "snapshot": fsm.get_snapshot()
    }

@router.post("/orchestrate/discover-and-score")
async def discover_merchants_and_score(session_id: str = Query(...)):
    fsm = ACTIVE_SESSIONS.get(session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")

    intent_data = fsm.session_data.get("intent_spec")
    if not intent_data:
        raise HTTPException(status_code=400, detail="Intent specification not found in session")

    intent_spec = PurchaseIntentSpecification(**intent_data)

    # 1. Merchant Discovery
    discovered = await buyer_agent.discover_merchants(intent_spec)
    fsm.session_data["discovered_merchants"] = discovered
    fsm.transition_to("MERCHANTS_DISCOVERED", reason=f"Discovered {len(discovered)} merchants in ecosystem: {discovered}", metadata={"merchants": discovered})
    
    await event_bus.emit(session_id, "MERCHANTS_DISCOVERED", {
        "discovered_merchants": discovered,
        "fsm_state": fsm.current_state
    })

    # 2. Agent-to-Agent Negotiation & Offer Collection
    for merchant_id in discovered:
        query_payload = {"from_agent": buyer_agent.agent_id, "to_agent": f"{merchant_id}_agent", "message_type": "A2AQueryPayload", "intent_spec": intent_spec.model_dump(), "max_delivery_days": intent_spec.constraints.max_delivery_days, "allow_substitutions": True, "input_tokens_estimate": (len(intent_spec.model_dump_json()) + 3) // 4}
        query_message = f"Customer → Merchant Side: {intent_spec.raw_prompt}"
        fsm.log_audit("A2A_QUERY_SENT", query_message, query_payload)
        await event_bus.emit(session_id, "A2A_QUERY_SENT", {"message": query_message, "payload": query_payload})

    async def emit_offer(offer: MerchantOffer) -> None:
        payload = {"from_agent": f"{offer.merchant_id}_agent", "to_agent": buyer_agent.agent_id, "message_type": "MerchantOffer", "offer": offer.model_dump(), "latency_ms": round((time.perf_counter() - offer_started) * 1000), "input_tokens_estimate": (len(intent_spec.model_dump_json()) + 3) // 4, "output_tokens_estimate": (len(offer.model_dump_json()) + 3) // 4}
        message = f"Merchant Side → Customer: {offer.product_title} is available at ₹{offer.price:.0f}. {offer.merchant_notes or offer.substitute_reasoning or 'Offer matches the requested constraints.'}"
        await event_bus.emit(session_id, "MERCHANT_OFFER_RECEIVED", {"message": message, "payload": payload})

    offer_started = time.perf_counter()
    raw_offers = await buyer_agent.collect_merchant_offers(intent_spec, discovered, on_offer=emit_offer)
    offer_latency_ms = round((time.perf_counter() - offer_started) * 1000)
    for offer in raw_offers:
        fsm.log_audit("MERCHANT_OFFER_RECEIVED", f"Merchant Side → Customer: {offer.product_title} is available at ₹{offer.price:.0f}. {offer.merchant_notes or offer.substitute_reasoning or 'Offer matches the requested constraints.'}", {"from_agent": f"{offer.merchant_id}_agent", "to_agent": buyer_agent.agent_id, "message_type": "MerchantOffer", "offer": offer.model_dump(), "latency_ms": offer_latency_ms})
    fsm.session_data["received_offers"] = [o.model_dump() for o in raw_offers]
    fsm.transition_to("OFFERS_RECEIVED", reason=f"Received {len(raw_offers)} formal merchant offers via A2A protocol", metadata={"offer_count": len(raw_offers)})
    
    await event_bus.emit(session_id, "OFFERS_RECEIVED", {
        "offers": [o.model_dump() for o in raw_offers],
        "fsm_state": fsm.current_state
    })

    # 3. Requirement-Aware Multi-Factor Scoring & Decision
    winner_offer, ranked_offers, rationale = await buyer_agent.select_best_offer(raw_offers, intent_spec)
    fsm.session_data["selected_offer"] = winner_offer.model_dump()
    fsm.session_data["received_offers"] = [o.model_dump() for o in ranked_offers]
    
    fsm.transition_to("PRODUCT_SELECTED", reason=f"Selected best offer: {winner_offer.product_title} from {winner_offer.merchant_name} (Score: {winner_offer.total_match_score}/100)", metadata={
        "selected_offer_id": winner_offer.offer_id,
        "decision_rationale": rationale
    })

    await event_bus.emit(session_id, "PRODUCT_SELECTED", {
        "selected_offer": winner_offer.model_dump(),
        "ranked_offers": [o.model_dump() for o in ranked_offers],
        "decision_rationale": rationale,
        "fsm_state": fsm.current_state
    })
    selection_payload = {
        "from_agent": buyer_agent.agent_id,
        "to_agent": f"{winner_offer.merchant_id}_agent",
        "message_type": "BuyerSelection",
        "selected_offer_id": winner_offer.offer_id,
        "decision_rationale": rationale,
        "customer_facing": True,
    }
    selection_message = f"Customer → Merchant Side: I selected {winner_offer.product_title} at ₹{winner_offer.price:.0f}. {rationale}"
    fsm.log_audit("BUYER_SELECTION_SENT", selection_message, selection_payload)
    await event_bus.emit(session_id, "BUYER_SELECTION_SENT", {"message": selection_message, "payload": selection_payload})

    # 4. Policy & Spend Authorization Guardrail Check
    auth_decision = policy_agent.evaluate_authorization(winner_offer, intent_spec)
    active_policy = persistence.get_active_policy(winner_offer.merchant_id)
    if active_policy:
        auth_decision.details = {**(auth_decision.details or {}), "policy_id": active_policy["policy_id"], "policy_version": active_policy["version"], "policy_hash": active_policy["content_hash"], "policy_merchant_id": active_policy.get("merchant_id"), "policy_source": active_policy["source_name"], "policy_effective_from": active_policy["effective_from"], "policy_effective_to": active_policy.get("effective_to")}
    fsm.session_data["authorization_result"] = auth_decision.model_dump()

    if auth_decision.is_authorized:
        fsm.transition_to("AUTHORIZED", reason=f"Autonomous purchase authorized under user mandate ceiling (₹{auth_decision.mandate_limit:.0f})", metadata=auth_decision.model_dump())
    else:
        fsm.transition_to("AWAITING_AUTHORIZATION", reason=auth_decision.reason, metadata=auth_decision.model_dump())

    await event_bus.emit(session_id, "AUTHORIZATION_EVALUATED", {
        "auth_decision": auth_decision.model_dump(),
        "fsm_state": fsm.current_state
    })
    if fsm.current_state == "AWAITING_AUTHORIZATION":
        approval_payload = {
            "from_agent": f"{winner_offer.merchant_id}_agent",
            "to_agent": buyer_agent.agent_id,
            "message_type": "MerchantApprovalRequest",
            "offer": winner_offer.model_dump(),
            "reason": auth_decision.reason,
            "customer_facing": True,
        }
        approval_message = f"Merchant Side → Customer: Please confirm the ₹{winner_offer.price:.0f} purchase. {auth_decision.reason}"
        fsm.log_audit("MERCHANT_APPROVAL_REQUEST", approval_message, approval_payload)
        await event_bus.emit(session_id, "MERCHANT_APPROVAL_REQUEST", {"message": approval_message, "payload": approval_payload})

    return {
        "session_id": session_id,
        "selected_offer": winner_offer,
        "ranked_offers": ranked_offers,
        "decision_rationale": rationale,
        "auth_decision": auth_decision,
        "fsm_state": fsm.current_state,
        "snapshot": fsm.get_snapshot()
    }

@router.post("/policy/grant-user-approval")
async def grant_user_approval(req: ApprovalRequest):
    fsm = ACTIVE_SESSIONS.get(req.session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")

    selected_offer_data = fsm.session_data.get("selected_offer")
    if not selected_offer_data:
        raise HTTPException(status_code=400, detail="No selected offer in session")

    offer = MerchantOffer(**selected_offer_data)
    user_id = persistence.customer_from_token(req.customer_token)
    if not user_id or user_id != fsm.user_id:
        raise HTTPException(status_code=401, detail="Customer authentication required")
    auth_decision = policy_agent.grant_user_approval(offer, user_id)
    active_policy = persistence.get_active_policy(offer.merchant_id)
    if active_policy:
        auth_decision.details = {**(auth_decision.details or {}), "policy_id": active_policy["policy_id"], "policy_version": active_policy["version"], "policy_hash": active_policy["content_hash"], "policy_merchant_id": active_policy.get("merchant_id"), "policy_source": active_policy["source_name"], "policy_effective_from": active_policy["effective_from"], "policy_effective_to": active_policy.get("effective_to")}
    fsm.session_data["authorization_result"] = auth_decision.model_dump()
    
    fsm.transition_to("AUTHORIZED", reason=f"Interactive user approval granted by {user_id}", metadata=auth_decision.model_dump())

    approval_message = f"Customer → Merchant Side: Purchase approved for ₹{offer.price:.0f}. Proceed with checkout."
    approval_payload = {
        "from_agent": buyer_agent.agent_id,
        "to_agent": f"{offer.merchant_id}_agent",
        "message_type": "BuyerApprovalResponse",
        "auth_decision": auth_decision.model_dump(),
        "customer_facing": True,
    }
    fsm.log_audit("USER_APPROVAL_GRANTED", approval_message, approval_payload)
    await event_bus.emit(req.session_id, "USER_APPROVAL_GRANTED", {
        "message": approval_message,
        "payload": approval_payload,
        "auth_decision": auth_decision.model_dump(),
        "fsm_state": fsm.current_state
    })

    return {
        "session_id": req.session_id,
        "auth_decision": auth_decision,
        "fsm_state": fsm.current_state,
        "snapshot": fsm.get_snapshot()
    }

@router.post("/upsell/decide")
async def decide_upsell(session_id: str = Query(...)):
    fsm = ACTIVE_SESSIONS.get(session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")
    selected = fsm.session_data.get("selected_offer") or {}
    if not selected:
        raise HTTPException(status_code=400, detail="No selected offer in session")
    recommendation = growth_agent.get_upsell_quote(selected["product_id"])
    if not recommendation:
        decision = {"decision": "PENDING_MERCHANT_APPROVAL", "reason": "The merchant has not approved a complementary-product recommendation yet. The customer will not receive an add-on until the merchant publishes an approved offer."}
        message = f"Merchant Side → Customer: Add-on status is {decision['decision']}. {decision['reason']}"
        fsm.log_audit("BUYER_UPSELL_DECISION", message, decision)
        await event_bus.emit(session_id, "BUYER_UPSELL_DECISION", {"message": message, "payload": decision})
        return {**decision, "message": message}
    intent_data = fsm.session_data.get("intent_spec")
    merchant_id = recommendation.get("opportunity_id", "").replace("opp_", "").replace("_bundle", "")
    merchant_name = next((item.merchant_name for item in merchant_agents_pool.values() if item.merchant_id == merchant_id), merchant_id)
    upsell_payload = {
        "from_agent": f"{merchant_id}_agent",
        "to_agent": buyer_agent.agent_id,
        "message_type": "MerchantAddOnOffer",
        "offer": recommendation,
        "customer_facing": True,
    }
    upsell_message = f"Merchant Side → Customer: We can also add {recommendation['recommended_product_title']} for ₹{recommendation['price']:.0f}. Would this help with the request?"
    fsm.log_audit("MERCHANT_UPSELL_OFFER", upsell_message, upsell_payload)
    await event_bus.emit(session_id, "MERCHANT_UPSELL_OFFER", {"message": upsell_message, "payload": upsell_payload})
    decision = await buyer_agent.decide_upsell(PurchaseIntentSpecification(**intent_data), float(selected["price"]), recommendation, session_id)
    decision["recommended_product_title"] = recommendation["recommended_product_title"]
    decision["merchant_id"] = merchant_id
    decision["from_agent"] = buyer_agent.agent_id
    decision["to_agent"] = f"{merchant_id}_agent"
    decision["message_type"] = "BuyerAddOnDecision"
    message = f"Customer → Merchant Side: {decision['decision']} the add-on. {decision['reason']}"
    fsm.log_audit("BUYER_UPSELL_DECISION", message, decision)
    await event_bus.emit(session_id, "BUYER_UPSELL_DECISION", {"message": message, "payload": decision})
    return {**decision, "message": message}

@router.post("/upsell/customer-decision")
async def customer_upsell_decision(req: UpsellDecisionRequest):
    fsm = ACTIVE_SESSIONS.get(req.session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")
    selected = fsm.session_data.get("selected_offer") or {}
    recommendation = growth_agent.get_upsell_quote(selected.get("product_id", ""))
    if not recommendation:
        raise HTTPException(status_code=409, detail="Merchant approval required before choosing this add-on")
    decision = "ACCEPT" if req.accept else "REJECT"
    fsm.session_data["accepted_upsell"] = recommendation if req.accept else None
    message = f"Customer → Merchant Side: {decision} the {recommendation['recommended_product_title']} add-on."
    payload = {**recommendation, "decision": decision, "from_agent": "customer", "to_agent": f"{selected.get('merchant_id', 'merchant')}_agent"}
    fsm.log_audit("BUYER_UPSELL_DECISION", message, payload)
    await event_bus.emit(req.session_id, "BUYER_UPSELL_DECISION", {"message": message, "payload": payload, "fsm_state": fsm.current_state})
    if req.accept:
        persistence.record_metric(selected.get("merchant_id", "unknown"), req.session_id, "UPSELL_ACCEPTED", amount=recommendation["price"], product_id=recommendation["recommended_product_id"], metadata={"base_product_id": selected.get("product_id"), "opportunity_id": recommendation.get("opportunity_id")})
    return {"decision": decision, "message": message, "accepted_upsell": fsm.session_data["accepted_upsell"], "snapshot": fsm.get_snapshot()}

@router.post("/transaction/create-razorpay-order")
async def create_razorpay_order(session_id: str = Query(...)):
    fsm = ACTIVE_SESSIONS.get(session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")

    if fsm.current_state != "AUTHORIZED":
        raise HTTPException(status_code=400, detail=f"Cannot create order: Session in state {fsm.current_state}, must be AUTHORIZED.")

    offer_data = dict(fsm.session_data.get("selected_offer") or {})
    auth_data = fsm.session_data.get("authorization_result")
    accepted_upsell = fsm.session_data.get("accepted_upsell")
    if accepted_upsell:
        offer_data["price"] = float(offer_data.get("price", 0)) + float(accepted_upsell["price"])
        offer_data["product_title"] = f"{offer_data.get('product_title', 'Product')} + {accepted_upsell['recommended_product_title']}"
    offer = MerchantOffer(**offer_data)
    from app.schemas.policy import AuthorizationDecision
    auth_dec = AuthorizationDecision(**auth_data)

    intent_data = fsm.session_data.get("intent_spec")
    if not intent_data:
        raise HTTPException(status_code=409, detail="Cannot revalidate policy: intent snapshot missing")
    recheck = policy_agent.recheck_before_payment(offer, PurchaseIntentSpecification(**intent_data), auth_dec)
    fsm.session_data["policy_recheck"] = recheck.model_dump()
    if not recheck.is_authorized:
        fsm.log_audit("POLICY_RECHECK_FAILED", recheck.reason, recheck.model_dump())
        raise HTTPException(status_code=409, detail=f"Policy changed before payment: {recheck.reason}")

    order_payload = await transaction_agent.initiate_razorpay_order(offer, recheck, session_id)
    fsm.session_data["razorpay_order"] = order_payload.model_dump()

    fsm.transition_to("ORDER_CREATED", reason=f"Razorpay Order {order_payload.order_id} generated for ₹{offer.price:.0f}", metadata=order_payload.model_dump())

    await event_bus.emit(session_id, "ORDER_CREATED", {
        "razorpay_order": order_payload.model_dump(),
        "fsm_state": fsm.current_state
    })

    return {
        "session_id": session_id,
        "order": order_payload,
        "fsm_state": fsm.current_state,
        "snapshot": fsm.get_snapshot()
    }

@router.post("/transaction/verify-payment")
async def verify_payment(req: PaymentVerificationRequest):
    fsm = ACTIVE_SESSIONS.get(req.session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")

    # Transition to PAYMENT_INITIATED if from ORDER_CREATED
    if fsm.current_state == "ORDER_CREATED":
        fsm.transition_to("PAYMENT_INITIATED", reason="Customer submitted payment credentials")
        await event_bus.emit(req.session_id, "PAYMENT_INITIATED", {"fsm_state": fsm.current_state})

    verification_res = verification_agent.verify_payment_outcome(req.model_dump())
    fsm.session_data["payment_result"] = verification_res

    if verification_res.get("verified"):
        fsm.transition_to("PAYMENT_VERIFIED", reason="Razorpay cryptographic signature & payment status verified")
        await event_bus.emit(req.session_id, "PAYMENT_VERIFIED", {
            "payment_result": verification_res,
            "fsm_state": fsm.current_state
        })

        # Complete the closed loop!
        fsm.transition_to("PURCHASE_COMPLETED", reason="Closed-loop verified: Merchant confirmed order, customer dispatched confirmation.")
        completed_offer = fsm.session_data.get("selected_offer") or {}
        persistence.record_metric(
            completed_offer.get("merchant_id", "unknown"),
            req.session_id,
            "PURCHASE_COMPLETED",
            float(completed_offer.get("price", 0)),
            product_id=completed_offer.get("product_id"),
            metadata={"buyer_agent_id": fsm.session_data.get("buyer_agent_id")},
        )
        await event_bus.emit(req.session_id, "PURCHASE_COMPLETED", {
            "session_id": req.session_id,
            "summary": "Transaction verified and order fulfilled successfully.",
            "fsm_state": fsm.current_state
        })
    else:
        fsm.transition_to("PAYMENT_FAILED", reason="Payment verification signature mismatch", metadata=verification_res)
        await event_bus.emit(req.session_id, "PAYMENT_FAILED", {
            "payment_result": verification_res,
            "fsm_state": fsm.current_state
        })

    return {
        "session_id": req.session_id,
        "verification": verification_res,
        "fsm_state": fsm.current_state,
        "snapshot": fsm.get_snapshot()
    }

@router.post("/transaction/simulate-success")
async def simulate_payment_success(session_id: str = Query(...)):
    fsm = ACTIVE_SESSIONS.get(session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")

    order_data = fsm.session_data.get("razorpay_order")
    if not order_data:
        raise HTTPException(status_code=400, detail="No Razorpay order in session")

    simulated_payment = razorpay_service.simulate_payment_success(
        order_id=order_data["order_id"],
        amount_paise=order_data["amount"]
    )

    verify_req = PaymentVerificationRequest(
        razorpay_order_id=simulated_payment["razorpay_order_id"],
        razorpay_payment_id=simulated_payment["razorpay_payment_id"],
        razorpay_signature=simulated_payment["razorpay_signature"],
        session_id=session_id
    )

    return await verify_payment(verify_req)

@router.post("/transaction/simulate-failure")
async def simulate_payment_failure(req: SimulateFailureRequest):
    session_id = req.session_id
    fsm = ACTIVE_SESSIONS.get(session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")

    order_data = fsm.session_data.get("razorpay_order")
    order_id = order_data.get("order_id") if order_data else "order_mock_001"

    if fsm.current_state == "ORDER_CREATED":
        fsm.transition_to("PAYMENT_INITIATED", reason="Customer submitted payment")

    failure_event = razorpay_service.simulate_payment_failure(order_id, req.error_type or "BANK_TECHNICAL_ERROR")
    fsm.session_data["payment_result"] = failure_event

    fsm.transition_to("PAYMENT_FAILED", reason=f"Payment failed: {failure_event.get('error_description')}", metadata=failure_event)
    await event_bus.emit(session_id, "PAYMENT_FAILED", {
        "failure_event": failure_event,
        "fsm_state": fsm.current_state
    })

    # Closed Loop: Autonomous Diagnosis & Recovery
    fsm.transition_to("FAILURE_ANALYSIS", reason="Verification Agent diagnosing payment failure cause", metadata=failure_event)
    await event_bus.emit(session_id, "FAILURE_ANALYSIS", {
        "failure_event": failure_event,
        "fsm_state": fsm.current_state
    })

    ranked_offers = fsm.session_data.get("received_offers", [])
    current_offer = fsm.session_data.get("selected_offer", {})
    
    recovery_attempt = int(fsm.session_data.get("recovery_attempts", 0)) + 1
    max_recovery_attempts = int(fsm.session_data.get("max_recovery_attempts", 1))
    recovery_plan = verification_agent.diagnose_failure_and_plan_recovery(
        failure_event,
        ranked_offers,
        current_offer,
        attempt=recovery_attempt,
        max_attempts=max_recovery_attempts,
    )
    fsm.session_data["recovery_plan"] = recovery_plan.model_dump()

    fsm.transition_to("RECOVERY_ACTION", reason=f"Recovery strategy activated: {recovery_plan.action_description}", metadata=recovery_plan.model_dump())
    await event_bus.emit(session_id, "RECOVERY_ACTION", {
        "recovery_plan": recovery_plan.model_dump(),
        "fsm_state": fsm.current_state
    })

    return {
        "session_id": session_id,
        "failure_event": failure_event,
        "recovery_plan": recovery_plan,
        "fsm_state": fsm.current_state,
        "snapshot": fsm.get_snapshot()
    }

@router.post("/transaction/execute-recovery")
async def execute_recovery_plan(session_id: str = Query(...)):
    fsm = ACTIVE_SESSIONS.get(session_id)
    if not fsm:
        raise HTTPException(status_code=404, detail="Session not found")

    recovery_plan = fsm.session_data.get("recovery_plan")
    if not recovery_plan:
        raise HTTPException(status_code=400, detail="No recovery plan found")

    strategy_type = recovery_plan.get("strategy_type")

    if not recovery_plan.get("retry_permitted", True) or strategy_type == "ABORT_PURCHASE":
        fsm.transition_to("PURCHASE_ABORTED", reason=recovery_plan.get("action_description", "Recovery budget exhausted"), metadata=recovery_plan)
        await event_bus.emit(session_id, "PURCHASE_ABORTED", {
            "reason": recovery_plan.get("action_description"),
            "fsm_state": fsm.current_state,
        })
        return {"session_id": session_id, "fsm_state": fsm.current_state, "snapshot": fsm.get_snapshot()}

    fsm.session_data["recovery_attempts"] = int(fsm.session_data.get("recovery_attempts", 0)) + 1

    if strategy_type == "FALLBACK_MERCHANT_OFFER":
        target_offer_id = recovery_plan.get("target_offer_id")
        ranked_offers = fsm.session_data.get("received_offers", [])
        fallback_offer = next((o for o in ranked_offers if o.get("offer_id") == target_offer_id), None)
        
        if fallback_offer:
            fsm.session_data["selected_offer"] = fallback_offer
            # Recreate razorpay order with new merchant offer
            offer_obj = MerchantOffer(**fallback_offer)
            auth_data = fsm.session_data.get("authorization_result")
            from app.schemas.policy import AuthorizationDecision
            auth_dec = AuthorizationDecision(**auth_data)
            intent_data = fsm.session_data.get("intent_spec")
            if not intent_data:
                raise HTTPException(status_code=409, detail="Cannot recover: intent snapshot missing")
            recheck = policy_agent.recheck_before_payment(offer_obj, PurchaseIntentSpecification(**intent_data), auth_dec)
            fsm.session_data["policy_recheck"] = recheck.model_dump()
            if not recheck.is_authorized:
                fsm.log_audit("RECOVERY_POLICY_RECHECK_FAILED", recheck.reason, recheck.model_dump())
                raise HTTPException(status_code=409, detail=f"Recovery blocked by current policy: {recheck.reason}")
            
            new_order = await transaction_agent.initiate_razorpay_order(offer_obj, recheck, session_id)
            fsm.session_data["razorpay_order"] = new_order.model_dump()
            
            fsm.transition_to("ORDER_CREATED", reason=f"Replaced with fallback order {new_order.order_id} ({fallback_offer.get('merchant_name')})", metadata=new_order.model_dump())
            await event_bus.emit(session_id, "RECOVERY_ORDER_CREATED", {
                "razorpay_order": new_order.model_dump(),
                "fsm_state": fsm.current_state
            })
    else:
        # RETRY_SAME_GATEWAY or SWITCH_PAYMENT_METHOD
        order_data = fsm.session_data.get("razorpay_order")
        fsm.transition_to("ORDER_CREATED", reason="Retrying transaction via alternate Razorpay payment rail", metadata=order_data)
        await event_bus.emit(session_id, "RECOVERY_RETRY_INITIATED", {
            "razorpay_order": order_data,
            "fsm_state": fsm.current_state
        })

    return {
        "session_id": session_id,
        "fsm_state": fsm.current_state,
        "snapshot": fsm.get_snapshot()
    }
