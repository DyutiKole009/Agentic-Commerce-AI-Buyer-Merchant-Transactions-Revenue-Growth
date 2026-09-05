import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "Razorpay Closed-Loop Agentic Commerce"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    # Supabase PostgreSQL is the only supported persistence backend.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Razorpay Config (defaults to Test/Sandbox simulator if keys are placeholder)
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "rzp_test_mock_agent_key")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "mock_secret_agent_token")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "mock_webhook_secret")
    RAZORPAY_MODE: str = os.getenv("RAZORPAY_MODE", "test")

    # Enable API-key protection outside local development.
    API_AUTH_ENABLED: bool = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"
    API_AUTH_TOKEN: str = os.getenv("API_AUTH_TOKEN", "")

    # Groq is OpenAI-compatible. The deterministic parser remains the fallback.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    
    # Default Policy Limits
    DEFAULT_MAX_AUTONOMOUS_SPEND: float = 4000.0
    DEFAULT_CURRENCY: str = "INR"
    X402_PAY_TO: str = os.getenv("X402_PAY_TO", "0x0000000000000000000000000000000000000000")
    DEFAULT_ALLOWED_CATEGORIES: list[str] = ["electronics", "audio", "wearables", "accessories", "computing"]

settings = Settings()
