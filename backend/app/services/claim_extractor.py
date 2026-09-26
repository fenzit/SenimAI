import logging
import re
from typing import List
from app.providers.llm import LLMProvider
from app.schemas.claim import Claim, ClaimType

logger = logging.getLogger("senimai.claim_extractor")

CLAIM_EXTRACTION_SYSTEM_PROMPT = """You are a precise factual claim extraction system for an AI fact-checking engine.
Your task is to analyze the input text and extract independent, atomic factual claims.

RULES:
1. Split compound and causal statements into separate atomic claims:
   - When a sentence connects a premise and an inference/consequence (e.g., using 'therefore', 'because', 'поэтому', 'поскольку', 'так как', 'вследствие'), ALWAYS extract BOTH the premise and the deduction as separate claims!
   - When a sentence asserts a language guarantee or universality (e.g. 'но это является гарантированной особенностью языка Python', 'это гарантировано спецификацией', 'автоматически для любых запросов'), extract that guarantee assertion as its own atomic claim so it can be verified independently!
   - Example 1: "HTTP is stateless, therefore the server cannot store client state between requests" ->
     Claim 1: "HTTP is a stateless protocol" (PREMISE)
     Claim 2: "An HTTP server cannot store information about previous client requests between requests" (DEDUCTION)
   - Example 2: "In CPython small integers are cached, therefore 256 is 256 may return True, but this is a guaranteed feature of the Python language" ->
     Claim 1: "In CPython small integers are cached" (PREMISE)
     Claim 2: "Comparing 256 is 256 may return True in CPython" (DEDUCTION)
     Claim 3: "Integer caching behavior with is is a guaranteed specification of the Python language itself" (DEDUCTION)
   - Example 3: "asyncio executes CPU-bound tasks in parallel because await switches tasks without blocking" ->
     Claim 1: "asyncio allows executing multiple CPU-bound tasks in parallel in a single thread" (DEDUCTION)
     Claim 2: "await switches execution between tasks without blocking the thread in asyncio" (PREMISE)
2. Keep each claim independently verifiable.
3. Preserve the original language of the text.
4. Do NOT invent information or change original meaning.
5. Extract 'original_quote' - the exact or near-exact phrase/subclause from the original text corresponding to this claim.
6. Ignore greetings, generic conversational filler, and rhetorical questions.
7. Return valid JSON only conforming to the schema below.

CRITICAL CLASSIFICATION GUIDELINES (FACTUAL vs OPINION):
- 'factual': Objective statements, technical recipes, cause-and-effect mechanics, sufficiency assertions, programming language behaviors, and scientific/engineering claims (e.g., "Replacing a list with a tuple is sufficient to prevent mutation" is FACTUAL because it makes a verifiable technical claim about language semantics, NOT an opinion).
- 'numerical': Claims involving statistics, numbers, measurements, percentages, quantities.
- 'temporal': Claims involving dates, years, historical timelines, current status.
- 'comparative': Claims comparing items (e.g., 'most popular', 'fastest', 'larger than').
- 'opinion': ONLY purely subjective personal aesthetic preferences, emotional tastes, or untestable philosophy (e.g., "Python is a beautiful language", "I like tuples more than lists"). Do NOT mark technical recommendations or sufficiency claims as opinion!

JSON OUTPUT SCHEMA:
{
  "claims": [
    {
      "id": 1,
      "text": "Extracted atomic claim in original language",
      "type": "factual | numerical | temporal | comparative | opinion",
      "causal_role": "PREMISE | DEDUCTION | STANDALONE",
      "original_quote": "Exact subclause from the text"
    }
  ]
}
"""


class ClaimExtractor:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def extract(self, text: str, max_claims: int = 12) -> List[Claim]:
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

                causal_role = str(item.get("causal_role", "STANDALONE")).upper()
                if causal_role not in ["PREMISE", "DEDUCTION", "STANDALONE"]:
                    causal_role = "STANDALONE"

                quote = item.get("original_quote", "").strip() or None
                start_char, end_char = None, None
                if quote and quote in text:
                    start_char = text.find(quote)
                    end_char = start_char + len(quote)
                elif claim_text in text:
                    start_char = text.find(claim_text)
                    end_char = start_char + len(claim_text)

                claims.append(
                    Claim(
                        id=int(item.get("id", idx)),
                        text=claim_text,
                        type=ctype,
                        original_quote=quote,
                        start_char=start_char,
                        end_char=end_char,
                        causal_role=causal_role,
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
            start_pos = text.find(sentence) if sentence in text else None
            end_pos = (start_pos + len(sentence)) if start_pos is not None else None
            claims.append(
                Claim(
                    id=idx,
                    text=sentence,
                    type=ClaimType.FACTUAL,
                    original_quote=sentence,
                    start_char=start_pos,
                    end_char=end_pos,
                )
            )
        return claims
