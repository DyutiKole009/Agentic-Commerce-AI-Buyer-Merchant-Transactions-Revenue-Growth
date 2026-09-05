from fastapi import APIRouter, File, HTTPException, UploadFile
from app.schemas.policy import SpendPolicy
from app.agents.policy_agent import policy_agent
from app.services.policy_kb import policy_kb
from app.services.persistence import persistence

router = APIRouter(prefix="/policy", tags=["Policy & Mandates"])

@router.get("/current", response_model=SpendPolicy)
async def get_current_policy():
    return policy_agent.policy

@router.post("/update", response_model=SpendPolicy)
async def update_policy(policy_update: SpendPolicy):
    policy_agent.update_policy(policy_update)
    return policy_agent.policy


@router.post("/documents/upload")
async def upload_policy_document(file: UploadFile = File(...), policy_id: str = "company_purchase_policy", merchant_id: str | None = None):
    try:
        return policy_kb.ingest(file.filename or "policy", await file.read(), file.content_type or "", policy_id, merchant_id=merchant_id)
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/documents/{policy_id}/{version}/activate")
async def activate_policy_document(policy_id: str, version: int, merchant_id: str | None = None):
    policy = policy_kb.activate(policy_id, version, merchant_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy version not found")
    return policy


@router.get("/documents/current")
async def current_policy_document(merchant_id: str | None = None):
    return persistence.get_active_policy(merchant_id) or {"active": False, "message": "No policy document is active"}
