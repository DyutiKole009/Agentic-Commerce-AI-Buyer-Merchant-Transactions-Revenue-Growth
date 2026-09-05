"""Seed the demo merchant catalog and policies into Supabase PostgreSQL.

Run from backend with:
    .venv\\Scripts\\python.exe scripts\\seed_supabase_demo.py
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.mock_merchants_db import MERCHANT_CATALOGS
from app.services.persistence import persistence
from app.services.policy_kb import policy_kb

SEED_PASSWORD = "demo_merchant_password"
POLICY_TEXT = """Company purchase policy

Autonomous purchases up to INR 4000 are allowed for electronics, audio, wearables, accessories, and computing.
Purchases above INR 4000 and within the user's stated budget require user confirmation.
Purchases above the user's stated budget are not allowed.
"""


def seed_merchants() -> tuple[int, int]:
    existing = {item["merchant_id"]: item for item in persistence.registered_merchants()}
    merchants_created = 0
    products_created = 0
    for merchant_id, catalog in MERCHANT_CATALOGS.items():
        if merchant_id not in existing:
            persistence.save_merchant(
                merchant_id,
                catalog["merchant_name"],
                catalog["agent_name"],
                catalog["endpoint"],
                SEED_PASSWORD,
                [product.model_dump() for product in catalog["products"]],
            )
            merchants_created += 1
            products_created += len(catalog["products"])
            continue
        stored_products = {product["product_id"] for product in existing[merchant_id].get("products", [])}
        for product in catalog["products"]:
            if product.product_id not in stored_products:
                persistence.save_merchant_product(product.model_dump())
                products_created += 1
    return merchants_created, products_created


def seed_policies() -> int:
    created = 0
    content = POLICY_TEXT.encode("utf-8")
    content_hash = hashlib.sha256(content).hexdigest()
    constraints = {
        "max_autonomous_spend": 4000.0,
        "max_budget_ceiling": 10000.0,
        "currency": "INR",
        "allowed_categories": ["electronics", "audio", "wearables", "accessories", "computing"],
        "require_confirmation_above": 4000.0,
        "allow_substitutes": True,
        "min_merchant_rating": 4.0,
    }
    for merchant_id in MERCHANT_CATALOGS:
        if persistence.get_active_policy(merchant_id):
            continue
        policy_id = f"{merchant_id}:company_purchase_policy"
        chunks = policy_kb._chunks(POLICY_TEXT)
        persistence.save_policy_version(
            policy_id,
            1,
            "seed_company_purchase_policy.txt",
            content_hash,
            POLICY_TEXT,
            constraints,
            datetime.now(timezone.utc).isoformat(),
            None,
            chunks,
            merchant_id,
        )
        if persistence.activate_policy_version(policy_id, 1, merchant_id):
            created += 1
    return created


if __name__ == "__main__":
    merchants_created, products_created = seed_merchants()
    policies_created = seed_policies()
    print(f"Supabase seed complete: merchants={merchants_created}, products={products_created}, policies={policies_created}")
    print(f"Demo merchant password: {SEED_PASSWORD}")
