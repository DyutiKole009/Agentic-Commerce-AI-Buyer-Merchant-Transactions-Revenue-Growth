from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.persistence import persistence

router = APIRouter(prefix="/customers", tags=["Customers"])


class CustomerRegistration(BaseModel):
    email: str = Field(min_length=5)
    customer_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8)


class CustomerLogin(BaseModel):
    email: str = Field(min_length=5)
    password: str


@router.post("/register")
async def register_customer(request: CustomerRegistration):
    try:
        customer = persistence.create_customer(request.email, request.customer_name, request.password)
    except Exception as error:
        if "duplicate" in str(error).lower() or "unique" in str(error).lower():
            raise HTTPException(status_code=409, detail="Customer email is already registered") from error
        raise
    return {"customer": customer, "token": persistence.create_customer_session(customer["customer_id"])}


@router.post("/login")
async def login_customer(request: CustomerLogin):
    customer = persistence.authenticate_customer(request.email, request.password)
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid customer credentials")
    return {"customer": customer, "token": persistence.create_customer_session(customer["customer_id"])}


@router.post("/logout")
async def logout_customer(authorization: str | None = Header(default=None)):
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if token:
        persistence.revoke_customer_session(token)
    return {"status": "SIGNED_OUT"}