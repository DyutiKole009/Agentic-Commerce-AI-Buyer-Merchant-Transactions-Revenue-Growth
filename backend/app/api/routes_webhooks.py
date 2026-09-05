import hmac
import hashlib
from typing import Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException
from app.config import settings
from app.api.routes_commerce import ACTIVE_SESSIONS

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/razorpay")
async def razorpay_webhook(request: Request, x_razorpay_signature: str = Header(None)):
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')

    # Signature verification if secret configured and signature provided
    if settings.RAZORPAY_WEBHOOK_SECRET and x_razorpay_signature:
        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, x_razorpay_signature):
            # In mock mode, allow if simulated
            if not x_razorpay_signature.startswith("mock_"):
                raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = await request.json()
    event_name = payload.get("event", "unknown")

    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id") or payload.get("order_id")
    session_updated = False
    for session_id, fsm in ACTIVE_SESSIONS.items():
        order = fsm.session_data.get("razorpay_order") or {}
        if order.get("order_id") == order_id or order.get("id") == order_id:
            fsm.log_audit("RAZORPAY_WEBHOOK_RECEIVED", f"Received Razorpay event {event_name}", payload)
            fsm.session_data["payment_result"] = {"event": event_name, "payload": payload}
            session_updated = True
            if event_name in {"payment.captured", "order.paid"} and fsm.current_state == "PAYMENT_INITIATED":
                fsm.transition_to("PAYMENT_VERIFIED", reason="Razorpay webhook confirmed captured payment")
                fsm.transition_to("PURCHASE_COMPLETED", reason="Webhook-confirmed order completed")
            elif event_name == "payment.failed" and fsm.current_state in {"ORDER_CREATED", "PAYMENT_INITIATED"}:
                if fsm.current_state == "ORDER_CREATED":
                    fsm.transition_to("PAYMENT_INITIATED", reason="Razorpay webhook reported payment attempt")
                fsm.transition_to("PAYMENT_FAILED", reason="Razorpay webhook reported payment failure")
            break
    
    return {
        "status": "received",
        "event": event_name,
        "session_updated": session_updated,
        "payload": payload
    }
