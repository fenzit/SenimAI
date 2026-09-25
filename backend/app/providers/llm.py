import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("senimai.llm")


class LLMProvider(ABC):
    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Generate structured JSON response from LLM."""
        pass


class OpenAILLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 40,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 40,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout = timeout

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER INPUT:\n{user_prompt}"}
                    ],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            text_content = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_content)


class MockLLMProvider(LLMProvider):
    """Fallback / Mock LLM provider for zero-dependency local testing."""

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        logger.info("MockLLMProvider invoked.")
        if "claim extraction" in system_prompt.lower():
            return {
                "claims": [
                    {
                        "id": 1,
                        "text": "Python был создан Гвидо ван Россумом.",
                        "type": "factual",
                    },
                    {
                        "id": 2,
                        "text": "Python был создан в 1991 году.",
                        "type": "temporal",
                    },
                ]
            }
        else:
            # Verification response mock
            return {
                "verdict": "SUPPORTED",
                "confidence": 0.95,
                "explanation": "Найденные независимые источники подтверждают данное утверждение.",
                "supporting_evidence": [
                    {
                        "source_index": 1,
                        "reason": "Источник напрямую подтверждает факт создания.",
                    }
                ],
            }


def get_llm_provider() -> LLMProvider:
    """Factory to get configured LLM provider with graceful mock fallback."""
    if settings.MOCK_MODE:
        return MockLLMProvider()
    if settings.OPENAI_API_KEY:
        return OpenAILLMProvider()
    if settings.GEMINI_API_KEY:
        return GeminiLLMProvider()
    logger.warning("No LLM API keys found; falling back to MockLLMProvider.")
    return MockLLMProvider()
