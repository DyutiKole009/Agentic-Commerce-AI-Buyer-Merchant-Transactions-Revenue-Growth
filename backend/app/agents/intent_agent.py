import re
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from app.config import settings
from app.services.persistence import persistence
from app.schemas.intent import PurchaseIntentSpecification, BudgetSpec, ConstraintsSpec

class IntentAgent:
    def __init__(self):
        self.name = "Intent Extraction Agent"
        self.last_source = "DETERMINISTIC_FALLBACK"
        self.llm_client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL,
        ) if settings.GROQ_API_KEY else None

    async def extract_intent(self, prompt: str, session_id: Optional[str] = None) -> PurchaseIntentSpecification:
        if self.llm_client:
            try:
                response = await self.llm_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Extract a commerce purchase intent as strict JSON. Include "
                                "product_category, budget {max,min,currency}, use_case, preferences "
                                "with values high priority/medium priority/low priority/optional, "
                                "constraints {brand,color,form_factor,max_delivery_days}, and "
                                "confidence_score between 0 and 1. Never invent a budget; use 5000 INR if absent."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                parsed = json.loads(response.choices[0].message.content or "{}")
                intent = PurchaseIntentSpecification(
                    intent_id=f"intent_{uuid.uuid4().hex[:8]}",
                    raw_prompt=prompt,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    **parsed,
                )
                self.last_source = "LLM"
                if response.usage:
                    persistence.record_usage(session_id, self.name, "groq", settings.GROQ_MODEL, response.usage)
                return intent
            except Exception:
                # A provider outage or malformed response must not block checkout.
                pass
        self.last_source = "DETERMINISTIC_FALLBACK"
        return await self._extract_deterministic(prompt)

    async def _extract_deterministic(self, prompt: str) -> PurchaseIntentSpecification:
        """
        Extracts structured purchase intent from natural language.
        Parses budget, category, use cases, prioritized features, and constraints.
        """
        normalized_prompt = prompt.lower()
        
        # 1. Budget extraction
        budget_max = 5000.0 # default if not specified
        budget_min = 0.0
        currency = "INR"
        
        # Extract patterns like "under ₹5,000", "below 4500", "budget 5k", "< 5000"
        budget_match = re.search(r'(?:under|below|budget|within|max|less than|<)?\s*(?:₹|rs\.?|inr)?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)\s*(?:k|thousand)?', normalized_prompt)
        
        # More targeted budget matcher
        number_matches = re.findall(r'(?:₹|rs\.?|inr|\b)\s*([0-9]+(?:,[0-9]+)*)\b', normalized_prompt)
        for num_str in number_matches:
            val = float(num_str.replace(',', ''))
            if val > 500: # realistic budget threshold
                budget_max = val
                break

        # Check for 'k' notation e.g., '5k'
        k_match = re.search(r'([0-9]+)\s*k\b', normalized_prompt)
        if k_match:
            budget_max = float(k_match.group(1)) * 1000

        # 2. Product Category
        category = "wireless headphones"
        if "earbuds" in normalized_prompt or "tws" in normalized_prompt:
            category = "wireless earbuds"
        elif "smartwatch" in normalized_prompt or "watch" in normalized_prompt:
            category = "smartwatches"
        elif "headphone" in normalized_prompt or "headset" in normalized_prompt:
            category = "wireless headphones"

        # 3. Use Case
        use_case = "general"
        if "commute" in normalized_prompt or "commuting" in normalized_prompt or "travel" in normalized_prompt or "metro" in normalized_prompt:
            use_case = "daily commuting"
        elif "gym" in normalized_prompt or "workout" in normalized_prompt or "running" in normalized_prompt or "sports" in normalized_prompt:
            use_case = "workout & sports"
        elif "gaming" in normalized_prompt:
            use_case = "gaming"
        elif "office" in normalized_prompt or "calls" in normalized_prompt or "meeting" in normalized_prompt:
            use_case = "office & calls"

        # 4. Feature Priorities
        preferences: Dict[str, str] = {}
        
        # Noise cancellation priority
        if "noise cancel" in normalized_prompt or "anc" in normalized_prompt:
            if "prioritize" in normalized_prompt or "must" in normalized_prompt or "high" in normalized_prompt or "essential" in normalized_prompt:
                preferences["noise_cancellation"] = "high priority"
            else:
                preferences["noise_cancellation"] = "high priority"
        else:
            preferences["noise_cancellation"] = "medium priority"

        # Battery life priority
        if "battery" in normalized_prompt or "backup" in normalized_prompt or "long lasting" in normalized_prompt:
            preferences["battery_life"] = "high priority"
        else:
            preferences["battery_life"] = "medium priority"

        # Water resistance priority
        if "water" in normalized_prompt or "sweat" in normalized_prompt or "ipx" in normalized_prompt:
            preferences["water_resistance"] = "high priority"
        else:
            preferences["water_resistance"] = "optional"

        # Fast charging
        if "fast charge" in normalized_prompt or "quick charge" in normalized_prompt:
            preferences["fast_charging"] = "medium priority"

        # 5. Constraints
        constraints = ConstraintsSpec()
        if "sony" in normalized_prompt:
            constraints.brand = "Sony"
        elif "boat" in normalized_prompt:
            constraints.brand = "boAt"
        elif "jbl" in normalized_prompt:
            constraints.brand = "JBL"

        if "black" in normalized_prompt:
            constraints.color = "Black"
        elif "white" in normalized_prompt:
            constraints.color = "White"

        if "fast delivery" in normalized_prompt or "1 day" in normalized_prompt or "urgent" in normalized_prompt:
            constraints.max_delivery_days = 1

        return PurchaseIntentSpecification(
            intent_id=f"intent_{uuid.uuid4().hex[:8]}",
            product_category=category,
            raw_prompt=prompt,
            budget=BudgetSpec(max=budget_max, min=budget_min, currency=currency),
            use_case=use_case,
            preferences=preferences,
            constraints=constraints,
            confidence_score=0.96,
            created_at=datetime.now(timezone.utc).isoformat()
        )

intent_agent = IntentAgent()
