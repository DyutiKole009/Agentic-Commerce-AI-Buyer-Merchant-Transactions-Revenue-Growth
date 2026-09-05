from typing import Any, Dict, List

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from app.agents.merchant_agents import MerchantAgent, merchant_agents_pool
from app.schemas.merchant import A2AQueryPayload, MerchantProduct, ProductFeatureMap
from app.schemas.growth import AgentOrderRequest, AgentQuoteRequest, AgentSearchRequest, UpsellAcceptanceRequest, UpsellQuoteRequest
from app.services.growth_agent import growth_agent
from app.services.persistence import persistence
from app.schemas.protocols import protocol_headers

router = APIRouter(prefix="/agent", tags=["Merchant Agent Protocol"])


class MerchantRegistrationRequest(BaseModel):
    merchant_id: str = Field(min_length=3, pattern=r"^[a-z0-9_-]+$")
    merchant_name: str = Field(min_length=2)
    agent_name: str = Field(min_length=2)
    endpoint: str = "http://localhost:8000/api/v1/agent"
    password: str = Field(min_length=8)


class MerchantLoginRequest(BaseModel):
    merchant_id: str
    password: str


class MerchantProductRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8)
    merchant_token: str | None = None
    title: str = Field(min_length=2)
    category: str = Field(min_length=2)
    price: float = Field(gt=0)
    stock_count: int = Field(default=1, ge=0)
    delivery_days: int = Field(default=3, ge=1, le=30)


def _all_products() -> List[Any]:
    return [product for agent in merchant_agents_pool.values() for product in agent.products]


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    return {
        "protocol": "razorpay-agent-commerce-v1",
        "capabilities": ["catalog", "product", "search", "quote", "order", "upsell"],
        "currency": "INR",
    }


@router.get("/catalog")
async def catalog() -> Dict[str, Any]:
    return {"merchants": list(merchant_agents_pool.keys()), "products": [item.model_dump() for item in _all_products()]}


@router.get("/merchants/{merchant_id}/catalog")
async def merchant_catalog(merchant_id: str) -> Dict[str, Any]:
    merchant = next((item for item in persistence.registered_merchants() if item["merchant_id"] == merchant_id), None)
    if merchant:
        agent = merchant_agents_pool.get(merchant_id)
        if agent:
            stored_products = merchant.get("products", [])
            stored_ids = {item.get("product_id") for item in stored_products}
            agent_products = [item.model_dump() for item in agent.products if item.product_id not in stored_ids]
            merchant["products"] = stored_products + agent_products
        return merchant
    agent = merchant_agents_pool.get(merchant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return {"merchant_id": merchant_id, "merchant_name": agent.merchant_name, "agent_name": agent.agent_name, "endpoint": agent.endpoint, "products": [item.model_dump() for item in agent.products]}


@router.post("/merchants/login")
async def merchant_login(request: MerchantLoginRequest) -> Dict[str, Any]:
    merchant = persistence.authenticate_merchant(request.merchant_id, request.password)
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid merchant credentials")
    return {"status": "AUTHENTICATED", "token": persistence.create_merchant_session(request.merchant_id), "merchant": await merchant_catalog(request.merchant_id)}


@router.post("/merchants/logout")
async def merchant_logout(authorization: str | None = Header(default=None)) -> Dict[str, str]:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if token:
        persistence.revoke_merchant_session(token)
    return {"status": "SIGNED_OUT"}


@router.post("/merchants/{merchant_id}/products")
async def add_merchant_product(merchant_id: str, request: MerchantProductRequest) -> Dict[str, Any]:
    token_merchant_id = persistence.merchant_from_token(request.merchant_token) if request.merchant_token else None
    merchant = persistence.authenticate_merchant(merchant_id, request.password) if request.password else None
    if token_merchant_id == merchant_id:
        merchant = next((item for item in persistence.registered_merchants() if item["merchant_id"] == merchant_id), None)
    if not merchant:
        raise HTTPException(status_code=401, detail="Invalid merchant credentials")
    product = MerchantProduct(product_id=f"prod_{merchant_id}_{__import__('uuid').uuid4().hex[:8]}", merchant_id=merchant_id, merchant_name=merchant["merchant_name"], title=request.title, category=request.category, base_price=request.price, in_stock=request.stock_count > 0, stock_count=request.stock_count, delivery_days=request.delivery_days, features=ProductFeatureMap())
    persistence.save_merchant_product(product.model_dump())
    agent = merchant_agents_pool.get(merchant_id)
    if agent:
        agent.products.append(product)
    return {"status": "ADDED", "product": product, "catalog": await merchant_catalog(merchant_id)}


@router.post("/merchants/register")
async def register_merchant(request: MerchantRegistrationRequest) -> Dict[str, Any]:
    if request.merchant_id in merchant_agents_pool or any(item["merchant_id"] == request.merchant_id for item in persistence.registered_merchants()):
        raise HTTPException(status_code=409, detail="Merchant ID already registered")
    agent = MerchantAgent(request.merchant_id)
    agent.merchant_name = request.merchant_name
    agent.agent_name = request.agent_name
    agent.endpoint = request.endpoint.rstrip("/")
    agent.products = []
    merchant_agents_pool[request.merchant_id] = agent
    try:
        persistence.save_merchant(request.merchant_id, request.merchant_name, request.agent_name, agent.endpoint, request.password, [])
    except Exception as error:
        merchant_agents_pool.pop(request.merchant_id, None)
        raise HTTPException(status_code=500, detail=f"Merchant could not be persisted: {error}") from error
    return {"status": "REGISTERED", "merchant_id": request.merchant_id, "agent_name": request.agent_name, "a2a_endpoint": f"/api/v1/agent/merchants/{request.merchant_id}/a2a/query", "catalog": await merchant_catalog(request.merchant_id)}


@router.get("/product/{product_id}")
async def product(product_id: str) -> Any:
    match = next((item for item in _all_products() if item.product_id == product_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Product not found")
    return match


@router.post("/search")
async def search(request: AgentSearchRequest) -> Dict[str, Any]:
    products = [item for item in _all_products() if request.category.lower() in item.category.lower()]
    if request.max_price is not None:
        products = [item for item in products if item.base_price <= request.max_price]
    if request.max_delivery_days is not None:
        products = [item for item in products if item.delivery_days <= request.max_delivery_days]
    return {"products": [item.model_dump() for item in products]}


@router.post("/merchants/{merchant_id}/a2a/query")
async def merchant_a2a_query(merchant_id: str, request: A2AQueryPayload, response: Response) -> Dict[str, Any]:
    """Network-facing merchant-agent endpoint used by external buyer agents."""
    agent = merchant_agents_pool.get(merchant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Merchant agent not found")
    result = await agent.handle_a2a_query(request)
    if result["offer"] is None:
        raise HTTPException(status_code=204, detail="Merchant cannot satisfy request")
    response.headers.update(protocol_headers("razorpay-agent-commerce", request.protocol_version, request.request_id))
    return result


@router.post("/quote")
async def quote(request: AgentQuoteRequest) -> Dict[str, Any]:
    product_item = next((item for item in _all_products() if item.product_id == request.product_id), None)
    if not product_item or not product_item.in_stock:
        raise HTTPException(status_code=409, detail="Product unavailable")
    return {
        "product_id": product_item.product_id,
        "quantity": request.quantity,
        "unit_price": product_item.base_price,
        "total": product_item.base_price * request.quantity,
        "currency": product_item.currency,
        "merchant_id": product_item.merchant_id,
    }


@router.post("/order")
async def order(request: AgentOrderRequest) -> Dict[str, Any]:
    quote_result = await quote(AgentQuoteRequest(product_id=request.product_id, quantity=request.quantity))
    return {
        "status": "PENDING_POLICY",
        "buyer_agent_id": request.buyer_agent_id,
        "quote": quote_result,
        "message": "Order proposal created; policy authorization is required before payment.",
    }


@router.post("/upsell/quote")
async def upsell_quote(request: UpsellQuoteRequest) -> Dict[str, Any]:
    quote_result = growth_agent.get_upsell_quote(request.base_product_id)
    if not quote_result:
        opportunity = next((item for item in growth_agent.list_opportunities() if item.base_product_id == request.base_product_id), None)
        if not opportunity:
            raise HTTPException(status_code=404, detail="No related-product opportunity available")
        return {"status": "PENDING_APPROVAL", "base_product_id": request.base_product_id, "recommended_product_id": opportunity.recommended_product_id, "recommended_product_title": opportunity.recommended_product_title, "price": opportunity.recommended_price, "reason": "Frequently bought together recommendation is awaiting merchant approval.", "opportunity_id": opportunity.opportunity_id}
    if request.session_id:
        persistence.record_metric(quote_result["opportunity_id"].split("_bundle")[0].replace("opp_", ""), request.session_id, "UPSELL_OFFERED", product_id=quote_result["recommended_product_id"], metadata={"opportunity_id": quote_result["opportunity_id"], "base_product_id": request.base_product_id})
    return {**quote_result, "status": "AVAILABLE"}


@router.post("/upsell/accept")
async def accept_upsell(request: UpsellAcceptanceRequest) -> Dict[str, Any]:
    quote_result = growth_agent.get_upsell_quote(request.base_product_id)
    if not quote_result:
        raise HTTPException(status_code=409, detail="Merchant approval required before accepting this recommendation")
    opportunity = next(item for item in growth_agent.list_opportunities() if item.opportunity_id == quote_result["opportunity_id"])
    persistence.record_metric(opportunity.merchant_id, request.session_id, "UPSELL_ACCEPTED", amount=quote_result["price"], product_id=quote_result["recommended_product_id"], metadata={"opportunity_id": opportunity.opportunity_id, "base_product_id": request.base_product_id})
    return {**quote_result, "status": "ACCEPTED"}
