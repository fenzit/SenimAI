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
    FALLBACK_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-2.5-pro",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 40,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        raw_model = model or settings.GEMINI_MODEL or "gemini-2.5-flash"
        if raw_model.startswith("models/"):
            raw_model = raw_model[7:]
        self.model = raw_model
        self.timeout = timeout

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        models_to_try = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]

        last_error = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
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

                # Retry up to 3 times for transient 429 or 503 errors with backoff
                for attempt in range(3):
                    try:
                        response = await client.post(url, json=payload)
                        if response.status_code == 404:
                            logger.warning(f"Model {model_name} not found (404). Trying next fallback...")
                            last_error = response.text
                            break

                        if response.status_code in (429, 503):
                            delay = (attempt + 1) * 2.0
                            logger.warning(f"Gemini {model_name} rate limit (429/503). Retrying in {delay}s (attempt {attempt+1}/3)...")
                            await asyncio.sleep(delay)
                            continue

                        response.raise_for_status()
                        data = response.json()
                        text_content = data["candidates"][0]["content"]["parts"][0]["text"].strip()

                        # Clean markdown codeblocks if LLM included them
                        if text_content.startswith("```"):
                            lines = text_content.splitlines()
                            if lines[0].startswith("```"):
                                lines = lines[1:]
                            if lines and lines[-1].startswith("```"):
                                lines = lines[:-1]
                            text_content = "\n".join(lines).strip()

                        return json.loads(text_content)

                    except Exception as e:
                        last_error = e
                        if "429" in str(e) or "503" in str(e):
                            delay = (attempt + 1) * 2.0
                            logger.warning(f"Gemini {model_name} error {e}. Backoff {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        if "404" in str(e):
                            break
                        # If not rate limit or 404, log and break to next model
                        logger.warning(f"Gemini {model_name} attempt {attempt+1} failed: {e}")
                        break

        raise ValueError(f"Gemini API request failed across models: {last_error}")


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
