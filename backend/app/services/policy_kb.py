import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.policy import SpendPolicy
from app.services.persistence import persistence


class PolicyKnowledgeBase:
    dimensions = 96

    def _embedding(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 8) for value in vector]

    def _chunks(self, text: str) -> List[Dict[str, Any]]:
        sections = [part.strip() for part in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", text) if part.strip()]
        chunks: List[Dict[str, Any]] = []
        current = ""
        for section in sections:
            if current and len(current) + len(section) > 900:
                chunks.append({"index": len(chunks), "content": current, "embedding": self._embedding(current)})
                current = ""
            current = f"{current}\n{section}".strip()
        if current:
            chunks.append({"index": len(chunks), "content": current, "embedding": self._embedding(current)})
        return chunks or [{"index": 0, "content": text, "embedding": self._embedding(text)}]

    def _constraints(self, text: str) -> Dict[str, Any]:
        amounts = [float(value.replace(",", "")) for value in re.findall(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)]
        autonomous = amounts[0] if amounts else 4000.0
        approval = amounts[1] if len(amounts) > 1 else autonomous
        blocked = re.findall(r"(?:excluded|not allowed|prohibited)\s*[:\-]?\s*([a-z][a-z _-]+)", text, re.IGNORECASE)
        policy = SpendPolicy(max_autonomous_spend=autonomous, require_confirmation_above=approval)
        return {**policy.model_dump(), "blocked_categories": [item.strip().lower() for item in blocked]}

    def ingest(self, source_name: str, content: bytes, content_type: str, policy_id: str = "company_purchase_policy", effective_from: Optional[str] = None, effective_to: Optional[str] = None, merchant_id: Optional[str] = None) -> Dict[str, Any]:
        if "pdf" in content_type or source_name.lower().endswith(".pdf"):
            from pypdf import PdfReader
            import io
            text = "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
        elif "word" in content_type or source_name.lower().endswith(".docx"):
            from docx import Document
            import io
            text = "\n\n".join(paragraph.text for paragraph in Document(io.BytesIO(content)).paragraphs)
        else:
            raise ValueError("Only PDF and DOCX policy documents are supported")
        if not text.strip():
            raise ValueError("Policy document contains no extractable text")
        storage_policy_id = f"{merchant_id}:{policy_id}" if merchant_id else policy_id
        version = persistence.next_policy_version(storage_policy_id, merchant_id)
        effective = effective_from or datetime.now(timezone.utc).isoformat()
        persistence.save_policy_version(storage_policy_id, version, source_name, hashlib.sha256(content).hexdigest(), text, self._constraints(text), effective, effective_to, self._chunks(text), merchant_id)
        return {"policy_id": storage_policy_id, "version": version, "merchant_id": merchant_id, "content_hash": hashlib.sha256(content).hexdigest(), "effective_from": effective, "active": False}

    def activate(self, policy_id: str, version: int, merchant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return persistence.activate_policy_version(policy_id, version, merchant_id)

    def retrieve(self, query: str, limit: int = 3, merchant_id: Optional[str] = None) -> List[str]:
        policy = persistence.get_active_policy(merchant_id)
        if not policy:
            return []
        query_vector = self._embedding(query)
        scored = []
        for chunk in persistence.policy_chunks(policy["policy_id"], policy["version"]):
            score = sum(left * right for left, right in zip(query_vector, chunk["embedding"]))
            scored.append((score, chunk["content"]))
        return [content for _, content in sorted(scored, reverse=True)[:limit]]


policy_kb = PolicyKnowledgeBase()
