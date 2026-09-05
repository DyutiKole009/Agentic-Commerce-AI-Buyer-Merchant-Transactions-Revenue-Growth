from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.schemas.transaction import PurchaseStateEnum, CommercialSessionState
from app.services.persistence import persistence

# Allowed valid transitions in the closed-loop agentic commerce state machine
VALID_TRANSITIONS: Dict[PurchaseStateEnum, List[PurchaseStateEnum]] = {
    "INTENT_RECEIVED": ["INTENT_VALIDATED", "PURCHASE_ABORTED"],
    "INTENT_VALIDATED": ["MERCHANTS_DISCOVERED", "PURCHASE_ABORTED"],
    "MERCHANTS_DISCOVERED": ["OFFERS_RECEIVED", "PURCHASE_ABORTED"],
    "OFFERS_RECEIVED": ["PRODUCT_SELECTED", "PURCHASE_ABORTED"],
    "PRODUCT_SELECTED": ["AWAITING_AUTHORIZATION", "AUTHORIZED", "PURCHASE_ABORTED"],
    "AWAITING_AUTHORIZATION": ["AUTHORIZED", "PURCHASE_ABORTED"],
    "AUTHORIZED": ["ORDER_CREATED", "PURCHASE_ABORTED"],
    "ORDER_CREATED": ["PAYMENT_INITIATED", "PAYMENT_FAILED", "PURCHASE_ABORTED"],
    "PAYMENT_INITIATED": ["PAYMENT_VERIFIED", "PAYMENT_FAILED"],
    "PAYMENT_VERIFIED": ["PURCHASE_COMPLETED"],
    "PAYMENT_FAILED": ["FAILURE_ANALYSIS", "PURCHASE_ABORTED"],
    "FAILURE_ANALYSIS": ["RECOVERY_ACTION", "PURCHASE_ABORTED"],
    "RECOVERY_ACTION": ["ORDER_CREATED", "PAYMENT_INITIATED", "PRODUCT_SELECTED", "PURCHASE_ABORTED"],
    "PURCHASE_COMPLETED": [],
    "PURCHASE_ABORTED": []
}

class PurchaseStateMachine:
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.current_state: PurchaseStateEnum = "INTENT_RECEIVED"
        self.history: List[Dict[str, Any]] = [
            {
                "state": "INTENT_RECEIVED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Session initialized"
            }
        ]
        self.session_data: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "current_state": "INTENT_RECEIVED",
            "state_history": self.history,
            "intent_spec": None,
            "intent_source": None,
            "discovered_merchants": [],
            "received_offers": [],
            "selected_offer": None,
            "authorization_result": None,
            "razorpay_order": None,
            "payment_result": None,
            "recovery_plan": None,
            "recovery_attempts": 0,
            "max_recovery_attempts": 1,
            "is_completed": False,
            "is_failed": False,
            "audit_logs": []
        }
        persistence.save_session(self.session_data, user_id)

    def transition_to(self, new_state: PurchaseStateEnum, reason: str = "", metadata: Optional[Dict[str, Any]] = None) -> bool:
        allowed = VALID_TRANSITIONS.get(self.current_state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Invalid FSM transition: Cannot transition from {self.current_state} to {new_state}. "
                f"Valid next states are: {allowed}"
            )
        
        self.current_state = new_state
        entry = {
            "state": new_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "metadata": metadata or {}
        }
        self.history.append(entry)
        self.session_data["current_state"] = new_state
        self.session_data["state_history"] = self.history
        
        if new_state == "PURCHASE_COMPLETED":
            self.session_data["is_completed"] = True
        elif new_state == "PURCHASE_ABORTED":
            self.session_data["is_failed"] = True

        self.log_audit("FSM_STATE_CHANGE", f"State transitioned to {new_state}: {reason}", metadata)
        persistence.save_session(self.session_data, self.user_id)
        return True

    def log_audit(self, event_type: str, message: str, payload: Optional[Dict[str, Any]] = None):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
            "payload": payload or {}
        }
        self.session_data["audit_logs"].append(log_entry)
        persistence.record_audit(self.session_id, event_type, message, payload or {})
        persistence.save_session(self.session_data, self.user_id)

    def get_snapshot(self) -> Dict[str, Any]:
        return self.session_data.copy()
