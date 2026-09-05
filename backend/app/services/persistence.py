import json
import hashlib
import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from sqlalchemy import create_engine, text
from app.config import settings


class Persistence:
    def __init__(self, path: Optional[str] = None):
        configured_path = path or settings.DATABASE_URL
        if not configured_path:
            raise RuntimeError("DATABASE_URL is required; configure the Supabase PostgreSQL connection URI")
        if not configured_path.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must be a Supabase PostgreSQL connection URI")
        self.path = configured_path.replace("postgresql://", "postgresql+psycopg://", 1)
        self.engine = create_engine(self.path, pool_pre_ping=True)
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as connection:
            for statement in (
                "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS audit_events (id BIGSERIAL PRIMARY KEY, session_id TEXT NOT NULL, event_type TEXT NOT NULL, message TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS commerce_metrics (id BIGSERIAL PRIMARY KEY, merchant_id TEXT NOT NULL, session_id TEXT NOT NULL, event_type TEXT NOT NULL, amount DOUBLE PRECISION NOT NULL DEFAULT 0, product_id TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS model_usage (id BIGSERIAL PRIMARY KEY, session_id TEXT, agent_name TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS policy_versions (policy_id TEXT NOT NULL, version INTEGER NOT NULL, merchant_id TEXT, source_name TEXT NOT NULL, content_hash TEXT NOT NULL, raw_text TEXT NOT NULL, constraints_json TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT, active BOOLEAN NOT NULL DEFAULT FALSE, created_at TEXT NOT NULL, PRIMARY KEY(policy_id, version))",
                "CREATE TABLE IF NOT EXISTS policy_chunks (id BIGSERIAL PRIMARY KEY, policy_id TEXT NOT NULL, version INTEGER NOT NULL, chunk_index INTEGER NOT NULL, content TEXT NOT NULL, embedding_json TEXT NOT NULL, UNIQUE(policy_id, version, chunk_index))",
                "CREATE TABLE IF NOT EXISTS merchants (merchant_id TEXT PRIMARY KEY, merchant_name TEXT NOT NULL, agent_name TEXT NOT NULL, endpoint TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS merchant_products (product_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, product_json TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, customer_name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS customer_sessions (token_hash TEXT PRIMARY KEY, customer_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS merchant_sessions (token_hash TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL)",
            ):
                connection.execute(text(statement))
            connection.execute(text("ALTER TABLE commerce_metrics ADD COLUMN IF NOT EXISTS product_id TEXT"))
            connection.execute(text("ALTER TABLE commerce_metrics ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}'"))
            connection.execute(text("ALTER TABLE policy_versions ADD COLUMN IF NOT EXISTS merchant_id TEXT"))
            connection.execute(text("ALTER TABLE customer_sessions ALTER COLUMN expires_at TYPE TIMESTAMPTZ USING expires_at::timestamptz"))

    def save_session(self, snapshot: Dict[str, Any], user_id: str = "cust_01") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as connection:
            connection.execute(
                text("""INSERT INTO sessions(session_id,user_id,snapshot_json,created_at,updated_at)
                    VALUES(:session_id,:user_id,:snapshot_json,:created_at,:updated_at) ON CONFLICT(session_id) DO UPDATE SET snapshot_json=excluded.snapshot_json, updated_at=excluded.updated_at"""),
                {"session_id": snapshot["session_id"], "user_id": user_id, "snapshot_json": json.dumps(snapshot), "created_at": now, "updated_at": now},
            )

    def create_customer(self, email: str, customer_name: str, password: str) -> Dict[str, str]:
        customer_id = f"cust_{uuid.uuid4().hex[:10]}"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode("utf-8")
        now = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO customers(customer_id,email,customer_name,password_hash,created_at) VALUES(:customer_id,:email,:customer_name,:password_hash,:created_at)"), {"customer_id": customer_id, "email": email.lower(), "customer_name": customer_name, "password_hash": password_hash, "created_at": now})
        return {"customer_id": customer_id, "email": email.lower(), "customer_name": customer_name}

    def authenticate_customer(self, email: str, password: str) -> Optional[Dict[str, str]]:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT customer_id,email,customer_name,password_hash FROM customers WHERE email=:email"), {"email": email.lower()}).mappings().first()
        if not row or not bcrypt.checkpw(password.encode(), row["password_hash"].encode("utf-8")):
            return None
        return {key: row[key] for key in ("customer_id", "email", "customer_name")}

    def create_customer_session(self, customer_id: str) -> str:
        raw_token = uuid.uuid4().hex + uuid.uuid4().hex
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO customer_sessions(token_hash,customer_id,created_at,expires_at) VALUES(:token_hash,:customer_id,:created_at,:expires_at)"), {"token_hash": token_hash, "customer_id": customer_id, "created_at": now.isoformat(), "expires_at": (now + timedelta(days=7)).isoformat()})
        return raw_token

    def customer_from_token(self, token: str) -> Optional[str]:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT customer_id FROM customer_sessions WHERE token_hash=:token_hash AND expires_at > CURRENT_TIMESTAMP"), {"token_hash": token_hash}).first()
        return row[0] if row else None

    def revoke_customer_session(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM customer_sessions WHERE token_hash=:token_hash"), {"token_hash": token_hash})

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT snapshot_json FROM sessions WHERE session_id=:session_id"), {"session_id": session_id}).mappings().first()
        return json.loads(row["snapshot_json"]) if row else None

    def record_audit(self, session_id: str, event_type: str, message: str, payload: Dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO audit_events(session_id,event_type,message,payload_json,created_at) VALUES(:session_id,:event_type,:message,:payload_json,:created_at)"),
                {"session_id": session_id, "event_type": event_type, "message": message, "payload_json": json.dumps(payload), "created_at": datetime.now(timezone.utc).isoformat()},
            )

    def record_usage(self, session_id: Optional[str], agent_name: str, provider: str, model: str, usage: Any) -> None:
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
        with self.engine.begin() as connection:
            connection.execute(
                text("""INSERT INTO model_usage(session_id,agent_name,provider,model,prompt_tokens,completion_tokens,total_tokens,created_at)
                    VALUES(:session_id,:agent_name,:provider,:model,:prompt_tokens,:completion_tokens,:total_tokens,:created_at)"""),
                {"session_id": session_id, "agent_name": agent_name, "provider": provider, "model": model, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens, "created_at": datetime.now(timezone.utc).isoformat()},
            )

    def record_metric(self, merchant_id: str, session_id: str, event_type: str, amount: float = 0, product_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO commerce_metrics(merchant_id,session_id,event_type,amount,product_id,metadata_json,created_at) VALUES(:merchant_id,:session_id,:event_type,:amount,:product_id,:metadata_json,:created_at)"),
                {"merchant_id": merchant_id, "session_id": session_id, "event_type": event_type, "amount": amount, "product_id": product_id, "metadata_json": json.dumps(metadata or {}), "created_at": datetime.now(timezone.utc).isoformat()},
            )

    def product_metric_summary(self, merchant_id: str) -> Dict[str, Dict[str, float]]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT product_id, COUNT(*) AS count, COALESCE(SUM(amount), 0) AS amount FROM commerce_metrics WHERE merchant_id=:merchant_id AND event_type='PURCHASE_COMPLETED' AND product_id IS NOT NULL GROUP BY product_id"), {"merchant_id": merchant_id}).mappings().all()
        return {row["product_id"]: {"count": row["count"], "amount": float(row["amount"])} for row in rows}

    def save_policy_version(self, policy_id: str, version: int, source_name: str, content_hash: str, raw_text: str, constraints: Dict[str, Any], effective_from: str, effective_to: Optional[str], chunks: list[Dict[str, Any]], merchant_id: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO policy_versions(policy_id,version,merchant_id,source_name,content_hash,raw_text,constraints_json,effective_from,effective_to,active,created_at) VALUES(:policy_id,:version,:merchant_id,:source_name,:content_hash,:raw_text,:constraints_json,:effective_from,:effective_to,FALSE,:created_at)"), {"policy_id": policy_id, "version": version, "merchant_id": merchant_id, "source_name": source_name, "content_hash": content_hash, "raw_text": raw_text, "constraints_json": json.dumps(constraints), "effective_from": effective_from, "effective_to": effective_to, "created_at": now})
            for chunk in chunks:
                connection.execute(text("INSERT INTO policy_chunks(policy_id,version,chunk_index,content,embedding_json) VALUES(:policy_id,:version,:chunk_index,:content,:embedding_json)"), {"policy_id": policy_id, "version": version, "chunk_index": chunk["index"], "content": chunk["content"], "embedding_json": json.dumps(chunk["embedding"])})

    def next_policy_version(self, policy_id: str, merchant_id: Optional[str] = None) -> int:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT COALESCE(MAX(version), 0) AS version FROM policy_versions WHERE policy_id=:policy_id AND merchant_id IS NOT DISTINCT FROM :merchant_id"), {"policy_id": policy_id, "merchant_id": merchant_id}).first()
        return int(row[0]) + 1

    def activate_policy_version(self, policy_id: str, version: int, merchant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as connection:
            exists = connection.execute(text("SELECT 1 FROM policy_versions WHERE policy_id=:policy_id AND version=:version"), {"policy_id": policy_id, "version": version}).first()
            if not exists:
                return None
            connection.execute(text("UPDATE policy_versions SET active=FALSE WHERE policy_id=:policy_id AND (merchant_id=:merchant_id OR (:merchant_id IS NULL AND merchant_id IS NULL))"), {"policy_id": policy_id, "merchant_id": merchant_id})
            connection.execute(text("UPDATE policy_versions SET active=TRUE WHERE policy_id=:policy_id AND version=:version"), {"policy_id": policy_id, "version": version})
        return self.get_active_policy(merchant_id)

    def get_active_policy(self, merchant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT * FROM policy_versions WHERE active=TRUE AND (merchant_id=:merchant_id OR merchant_id IS NULL) ORDER BY CASE WHEN merchant_id=:merchant_id THEN 0 ELSE 1 END, effective_from DESC LIMIT 1"), {"merchant_id": merchant_id}).mappings().first()
        if not row:
            return None
        record = dict(row)
        record["constraints"] = json.loads(record.pop("constraints_json"))
        return record

    def policy_chunks(self, policy_id: str, version: int) -> list[Dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT chunk_index,content,embedding_json FROM policy_chunks WHERE policy_id=:policy_id AND version=:version ORDER BY chunk_index"), {"policy_id": policy_id, "version": version}).mappings().all()
        return [{"index": row["chunk_index"], "content": row["content"], "embedding": json.loads(row["embedding_json"])} for row in rows]

    def save_merchant(self, merchant_id: str, merchant_name: str, agent_name: str, endpoint: str, password: str, products: list[Dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode("utf-8")
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO merchants(merchant_id,merchant_name,agent_name,endpoint,password_hash,created_at) VALUES(:merchant_id,:merchant_name,:agent_name,:endpoint,:password_hash,:created_at)"), {"merchant_id": merchant_id, "merchant_name": merchant_name, "agent_name": agent_name, "endpoint": endpoint, "password_hash": password_hash, "created_at": now})
            for product in products:
                connection.execute(text("INSERT INTO merchant_products(product_id,merchant_id,product_json,created_at) VALUES(:product_id,:merchant_id,:product_json,:created_at)"), {"product_id": product["product_id"], "merchant_id": merchant_id, "product_json": json.dumps(product), "created_at": now})

    def save_merchant_product(self, product: Dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO merchant_products(product_id,merchant_id,product_json,created_at) VALUES(:product_id,:merchant_id,:product_json,:created_at)"), {"product_id": product["product_id"], "merchant_id": product["merchant_id"], "product_json": json.dumps(product), "created_at": datetime.now(timezone.utc).isoformat()})

    def authenticate_merchant(self, merchant_id: str, password: str) -> Optional[Dict[str, Any]]:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT merchant_id,merchant_name,agent_name,endpoint,password_hash FROM merchants WHERE merchant_id=:merchant_id"), {"merchant_id": merchant_id}).mappings().first()
        if not row or not bcrypt.checkpw(password.encode(), row["password_hash"].encode("utf-8")):
            return None
        return {key: row[key] for key in ("merchant_id", "merchant_name", "agent_name", "endpoint")}

    def create_merchant_session(self, merchant_id: str) -> str:
        raw_token = uuid.uuid4().hex + uuid.uuid4().hex
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO merchant_sessions(token_hash,merchant_id,created_at,expires_at) VALUES(:token_hash,:merchant_id,:created_at,:expires_at)"), {"token_hash": token_hash, "merchant_id": merchant_id, "created_at": now.isoformat(), "expires_at": (now + timedelta(days=7)).isoformat()})
        return raw_token

    def merchant_from_token(self, token: str) -> Optional[str]:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT merchant_id FROM merchant_sessions WHERE token_hash=:token_hash AND expires_at > CURRENT_TIMESTAMP"), {"token_hash": token_hash}).first()
        return row[0] if row else None

    def revoke_merchant_session(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM merchant_sessions WHERE token_hash=:token_hash"), {"token_hash": token_hash})

    def registered_merchants(self) -> list[Dict[str, Any]]:
        with self.engine.connect() as connection:
            merchants = connection.execute(text("SELECT merchant_id,merchant_name,agent_name,endpoint FROM merchants ORDER BY created_at")).mappings().all()
            products = connection.execute(text("SELECT merchant_id,product_json FROM merchant_products ORDER BY created_at")).mappings().all()
        products_by_merchant: Dict[str, list[Dict[str, Any]]] = {}
        for row in products:
            products_by_merchant.setdefault(row["merchant_id"], []).append(json.loads(row["product_json"]))
        return [{**dict(merchant), "products": products_by_merchant.get(merchant["merchant_id"], [])} for merchant in merchants]

    def metric_summary(self, merchant_id: str) -> Dict[str, float]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT event_type, COUNT(*) AS count, COALESCE(SUM(amount),0) AS amount FROM commerce_metrics WHERE merchant_id=:merchant_id GROUP BY event_type"), {"merchant_id": merchant_id}).mappings().all()
        summary: Dict[str, float] = {}
        for row in rows:
            summary[row["event_type"] + "_count"] = row["count"]
            summary[row["event_type"] + "_amount"] = row["amount"]
        return summary

    def usage_summary(self, session_id: Optional[str] = None) -> Dict[str, int]:
        query = "SELECT COALESCE(SUM(prompt_tokens),0) prompt, COALESCE(SUM(completion_tokens),0) completion, COALESCE(SUM(total_tokens),0) total FROM model_usage"
        params = {}
        if session_id:
            query += " WHERE session_id=:session_id"
            params = {"session_id": session_id}
        with self.engine.connect() as connection:
            row = connection.execute(text(query), params).mappings().first()
        return {"prompt_tokens": row["prompt"], "completion_tokens": row["completion"], "total_tokens": row["total"]}


persistence = Persistence()
