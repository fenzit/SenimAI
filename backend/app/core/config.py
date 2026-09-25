from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "SenimAI - AI Trust Fact-Checking API"
    DEBUG: bool = False

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "*",
    ]

    # Mode: if True, returns realistic prepared demo outputs without requiring external APIs
    MOCK_MODE: bool = False

    # LLM Settings
    # Supports OpenAI / OpenRouter / Groq / DeepSeek / Local Ollama or Google Gemini
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Gemini API settings (alternative LLM provider)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    # Search Provider Settings
    SEARCH_PROVIDER: str = "tavily"  # "tavily", "serper", "duckduckgo", "mock"
    TAVILY_API_KEY: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None

    # Pipeline Concurrency & Limits
    MAX_CLAIMS: int = 8
    MAX_CONCURRENT_CLAIMS: int = 4
    SEARCH_RESULTS_PER_CLAIM: int = 4
    REQUEST_TIMEOUT_SECONDS: int = 30


settings = Settings()
