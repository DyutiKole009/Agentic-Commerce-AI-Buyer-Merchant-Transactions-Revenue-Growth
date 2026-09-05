from fastapi import APIRouter, HTTPException

from app.schemas.growth import GrowthApprovalRequest
from app.services.growth_agent import growth_agent
from app.services.persistence import persistence

router = APIRouter(prefix="/merchant", tags=["Merchant Growth"])


@router.get("/dashboard")
async def dashboard(merchant_id: str = "merchant_electromax"):
    try:
        return growth_agent.dashboard(merchant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Merchant not found")


@router.get("/opportunities")
async def opportunities(merchant_id: str):
    return {"opportunities": growth_agent.list_opportunities(merchant_id)}


@router.post("/opportunities/{opportunity_id}/approve")
async def approve_opportunity(opportunity_id: str, request: GrowthApprovalRequest):
    try:
        opportunity = next(item for item in growth_agent.list_opportunities() if item.opportunity_id == opportunity_id)
        token_merchant_id = persistence.merchant_from_token(request.merchant_token) if request.merchant_token else None
        password_authenticated = persistence.authenticate_merchant(request.merchant_id, request.password) if request.password else None
        if opportunity.merchant_id != request.merchant_id or (token_merchant_id != request.merchant_id and not password_authenticated):
            raise HTTPException(status_code=403, detail="Merchant approval required: valid merchant credentials are required")
        return growth_agent.approve_opportunity(opportunity_id, request.approved_by)
    except KeyError:
        raise HTTPException(status_code=404, detail="Opportunity not found")


@router.post("/opportunities/{opportunity_id}/execute")
async def execute_opportunity(opportunity_id: str):
    try:
        return growth_agent.execute_opportunity(opportunity_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except ValueError as error:
        raise HTTPException(status_code=502 if "channel" in str(error) else 409, detail=str(error))
