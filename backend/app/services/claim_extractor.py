import logging
import re
from typing import List
from app.providers.llm import LLMProvider
from app.schemas.claim import Claim, ClaimType

logger = logging.getLogger("senimai.claim_extractor")

CLAIM_EXTRACTION_SYSTEM_PROMPT = """You are a precise factual claim extraction system for an AI fact-checking engine.
Your task is to analyze the input text and extract independent, atomic factual claims.

RULES:
1. Split compound statements into separate, atomic claims (e.g. "Python was made by Guido in 1991" -> 1. "Python was made by Guido", 2. "Python was released in 1991").
2. Keep each claim independently verifiable.
3. Preserve the original language of the text.
4. Do NOT invent information or change original meaning.
5. Identify subjective opinions or non-verifiable statements and classify them as 'opinion'.
6. Ignore greetings, generic conversational filler, and rhetorical questions.
7. Return valid JSON only conforming to the schema below.

Allowed claim types:
- factual: standard factual statements
- numerical: claims involving statistics, numbers, measurements, quantities
- temporal: claims involving dates, years, historical timelines, current status
- comparative: claims comparing items (e.g., 'most popular', 'fastest', 'larger than')
- opinion: subjective opinions, recommendations, aesthetic judgements

JSON OUTPUT SCHEMA:
{
  "claims": [
    {
      "id": 1,
      "text": "Extracted atomic claim in original language",
      "type": "factual | numerical | temporal | comparative | opinion"
    }
  ]
}
"""


class ClaimExtractor:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def extract(self, text: str, max_claims: int = 8) -> List[Claim]:
        if not text or not text.strip():
            return []

        user_prompt = f"Extract up to {max_claims} atomic claims from this text:\n\n\"\"\"\n{text.strip()}\n\"\"\""

        try:
            raw_result = await self.llm.generate_json(
                system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.0,
            )

            claims_data = raw_result.get("claims", [])
            claims: List[Claim] = []

            for idx, item in enumerate(claims_data[:max_claims], start=1):
                claim_text = item.get("text", "").strip()
                if not claim_text:
                    continue

                raw_type = str(item.get("type", "factual")).lower()
                try:
                    ctype = ClaimType(raw_type)
                except ValueError:
                    ctype = ClaimType.FACTUAL

                claims.append(
                    Claim(
                        id=int(item.get("id", idx)),
                        text=claim_text,
                        type=ctype,
                    )
                )

            if claims:
                return claims

        except Exception as e:
            logger.error(f"Error in LLM claim extraction: {e}")

        # Fallback simple sentence splitter if LLM fails or returns empty
        return self._fallback_extract(text, max_claims)

    def _fallback_extract(self, text: str, max_claims: int = 8) -> List[Claim]:
        sentences = [
            s.strip()
            for s in re.split(r"[.!?\n]+", text)
            if len(s.strip()) > 10 and not s.strip().startswith(("Привет", "Hello", "Здравствуйте"))
        ]

        claims: List[Claim] = []
        for idx, sentence in enumerate(sentences[:max_claims], start=1):
            claims.append(
                Claim(
                    id=idx,
                    text=sentence,
                    type=ClaimType.FACTUAL,
                )
            )
        return claims
