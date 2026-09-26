import json
import logging
from typing import List
from app.providers.llm import LLMProvider
from app.schemas.claim import (
    Claim,
    ClaimResult,
    ClaimType,
    EvidenceSufficiency,
    Source,
    SourceStance,
    SupportingEvidence,
    Verdict,
)
from app.services.evidence import EvidenceProcessor

logger = logging.getLogger("senimai.verifier")

VERIFIER_SYSTEM_PROMPT = """You are a rigorous, evidence-based factual verification engine.
Your sole mission is to evaluate the provided CLAIM against the provided EXTERNAL EVIDENCE.

CRITICAL INTEGRITY & MULTI-HOP REASONING RULES:
1. DO NOT invent facts out of nowhere, but DO APPLY LOGICAL DEDUCTION on the provided evidence. If the evidence establishes the underlying mechanism, deduce the logical outcome.
2. SEMANTIC EVIDENCE RECOGNITION:
   - Recognize paraphrases and synonyms. For example, if evidence states "stateless HTTP transactions", "HTTP is designed as a stateless protocol", or "server does not maintain client state across HTTP requests", this DIRECTLY SUPPORTS claims asserting that HTTP is stateless.
   - For PostgreSQL: If official documentation states "B-tree index can be used for queries involving LIKE if anchored to beginning (foo%), but NOT col LIKE '%bar'", this DIRECTLY CONTRADICTS claims that "B-tree index automatically accelerates any LIKE query regardless of leading %".
   - For CPython caching: If evidence states CPython caches integers in range [-5, 256], deduce that comparing arbitrary integers outside this range with `is` is not guaranteed to be True, and `is` tests identity while `==` tests equality.
   - Implementation Detail vs Language Specification: If evidence states integer caching or memory sharing is an implementation detail of CPython, claims asserting that this is a "guaranteed specification of the Python language" are CONTRADICTED.
3. MULTI-HOP INFERENCE & CAUSAL REASONING:
   - Mechanism & Concurrency: If evidence states "asyncio uses a single-threaded cooperative event loop where tasks must await I/O", deduce that CPU-bound tasks running in a single thread cannot execute in parallel and will block the loop. Verdict: CONTRADICTED, Sufficiency: COMBINED.
   - Partial Truths & Overstatements: For claims like "await switches execution between tasks without blocking the thread", if evidence shows await yields control only when awaiting asynchronous I/O operations and synchronous CPU computations still block the thread, mark as PARTIALLY_SUPPORTED or NUANCED.
   - Causal Sophisms / False Deductions: If evidence confirms Premise A ("HTTP is stateless") but also shows ("Servers maintain sessions and state via cookies/storage"), deduce that the inference "therefore server cannot store state" is logically false. Verdict: CONTRADICTED or PARTIALLY_SUPPORTED with explicit explanation of the invalid deduction.
4. If a single source directly confirms or refutes the exact claim, mark evidence_sufficiency: 'DIRECT'.
5. If the conclusion is derived from synthesizing multiple sources/premises or applying logical deduction to established mechanisms, mark evidence_sufficiency: 'COMBINED'.
6. If the evidence provides only indirect/circumstantial support, mark evidence_sufficiency: 'INDIRECT'.
7. Only return 'UNVERIFIED' with evidence_sufficiency: 'INSUFFICIENT' if the provided evidence has ZERO relevant information about the concepts/mechanisms in the claim.
8. If the claim touches upon a subtle technical distinction or terminology dispute (e.g. Python argument passing being 'call by sharing / object reference' rather than pure 'by value' or 'by reference'), return 'NUANCED'.
9. If reputable sources in the evidence directly contradict each other, return 'CONFLICTING'.
10. If the evidence directly or through multi-hop deduction refutes the claim, return 'CONTRADICTED'.
11. If the evidence confirms the claim, return 'SUPPORTED'.
12. Provide a clear, objective explanation in the requested language ({language}) citing specific details and logical steps.
13. Provide a 'why_verdict' breakdown explaining the step-by-step reasoning or logical chain (Premise 1 -> Premise 2 -> Deduction).
14. For each source evaluated, classify:
    - stance: 'SUPPORTS' | 'CONTRADICTS' | 'NEUTRAL' | 'INSUFFICIENT'
    - relevance: 'DIRECT' | 'RELATED' | 'NOT_RELEVANT'
    - relevance_reason: 'Brief 1-sentence explanation why this source is direct, related, or irrelevant'

VERDICTS:
- SUPPORTED
- CONTRADICTED
- PARTIALLY_SUPPORTED
- NUANCED
- UNVERIFIED
- CONFLICTING

EVIDENCE SUFFICIENCY:
- DIRECT (single authoritative source directly answers the claim)
- COMBINED (multi-hop synthesis across multiple premises/sources)
- INDIRECT (circumstantial evidence)
- INSUFFICIENT (insufficient information -> UNVERIFIED)

RESPONSE FORMAT:
Return JSON only:
{
  "verdict": "SUPPORTED | CONTRADICTED | PARTIALLY_SUPPORTED | NUANCED | UNVERIFIED | CONFLICTING",
  "evidence_sufficiency": "DIRECT | COMBINED | INDIRECT | INSUFFICIENT",
  "confidence": 0.0 to 1.0,
  "explanation": "Clear explanation of the verdict based on the evidence in {language}",
  "why_verdict": "Step-by-step reasoning breakdown explaining why this verdict was reached",
  "source_stances": [
    {
      "source_index": 1,
      "stance": "SUPPORTS | CONTRADICTS | NEUTRAL | INSUFFICIENT",
      "relevance": "DIRECT | RELATED | NOT_RELEVANT",
      "relevance_reason": "Specific reason why this source is direct, related, or irrelevant"
    }
  ],
  "supporting_evidence": [
    {
      "source_index": 1,
      "reason": "Specific excerpt or reason this source was relevant"
    }
  ]
}
"""


class ClaimVerifier:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def verify(
        self,
        claim: Claim,
        sources: List[Source],
        language: str = "ru",
    ) -> ClaimResult:
        # If the claim is a subjective opinion, do not search or falsely classify
        if claim.type == ClaimType.OPINION:
            return ClaimResult(
                id=claim.id,
                text=claim.text,
                type=claim.type,
                verdict=Verdict.NOT_FACT_CHECKABLE,
                confidence=1.0,
                explanation=(
                    "Данное высказывание является субъективным мнением или оценочным суждением "
                    "и не подлежит объективной проверке фактов."
                    if language == "ru"
                    else "This statement is a subjective opinion or value judgement and cannot be objectively fact-checked."
                ),
                why_verdict=(
                    "Субъективные мнения, предпочтения и эмоциональные оценки не содержат проверяемых фактов."
                    if language == "ru"
                    else "Subjective opinions and personal valuations lack objectively verifiable factual claims."
                ),
                sources=[],
                supporting_evidence=[],
                original_quote=claim.original_quote,
                start_char=claim.start_char,
                end_char=claim.end_char,
            )

        # If no sources found at all
        if not sources:
            return ClaimResult(
                id=claim.id,
                text=claim.text,
                type=claim.type,
                verdict=Verdict.UNVERIFIED,
                confidence=0.5,
                explanation=(
                    "Не удалось найти достаточно достоверных внешних источников для проверки этого утверждения."
                    if language == "ru"
                    else "Insufficient external evidence found to reliably verify or refute this claim."
                ),
                why_verdict=(
                    "Поисковая система не вернула авторитетных источников, содержащих информацию по данному утверждению."
                    if language == "ru"
                    else "Search returned no authoritative sources containing relevant evidence."
                ),
                sources=[],
                supporting_evidence=[],
                original_quote=claim.original_quote,
                start_char=claim.start_char,
                end_char=claim.end_char,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
            )

        evidence_text = EvidenceProcessor.format_evidence_for_prompt(sources)
        system_prompt = VERIFIER_SYSTEM_PROMPT.replace("{language}", language)
        user_prompt = (
            f"CLAIM #{claim.id} (Type: {claim.type.value}):\n{claim.text}\n\n"
            f"EXTERNAL EVIDENCE:\n{evidence_text}\n\n"
            f"Evaluate the claim and return the JSON verdict with evidence_sufficiency."
        )

        try:
            result = await self.llm.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
            )

            raw_verdict = str(result.get("verdict", "UNVERIFIED")).upper()
            try:
                verdict = Verdict(raw_verdict)
            except ValueError:
                verdict = Verdict.UNVERIFIED

            raw_suff = str(result.get("evidence_sufficiency", "DIRECT")).upper()
            try:
                evidence_sufficiency = EvidenceSufficiency(raw_suff)
            except ValueError:
                evidence_sufficiency = (
                    EvidenceSufficiency.INSUFFICIENT
                    if verdict == Verdict.UNVERIFIED
                    else EvidenceSufficiency.DIRECT
                )

            confidence = float(result.get("confidence", 0.8))
            confidence = max(0.0, min(1.0, confidence))

            explanation = result.get(
                "explanation",
                "Результат проверки на основе найденных источников.",
            )
            why_verdict = result.get("why_verdict", explanation)

            # Update source stances and relevance
            stances_map = {}
            relevance_map = {}
            relevance_reason_map = {}
            for st in result.get("source_stances", []):
                s_idx = int(st.get("source_index", 0))
                s_val = str(st.get("stance", "NEUTRAL")).upper()
                r_val = str(st.get("relevance", "RELATED")).upper()
                r_reason = st.get("relevance_reason")
                try:
                    stances_map[s_idx] = SourceStance(s_val)
                except ValueError:
                    stances_map[s_idx] = SourceStance.NEUTRAL
                relevance_map[s_idx] = r_val if r_val in ("DIRECT", "RELATED", "NOT_RELEVANT") else "RELATED"
                if r_reason:
                    relevance_reason_map[s_idx] = str(r_reason)

            updated_sources: List[Source] = []
            for i, src in enumerate(sources, start=1):
                src_copy = src.model_copy()
                if i in stances_map:
                    src_copy.stance = stances_map[i]
                if i in relevance_map:
                    src_copy.relevance = relevance_map[i]
                if i in relevance_reason_map:
                    src_copy.relevance_reason = relevance_reason_map[i]
                updated_sources.append(src_copy)

            supporting_ev = []
            for item in result.get("supporting_evidence", []):
                supporting_ev.append(
                    SupportingEvidence(
                        source_index=int(item.get("source_index", 1)),
                        reason=str(item.get("reason", "")),
                    )
                )

            return ClaimResult(
                id=claim.id,
                text=claim.text,
                type=claim.type,
                verdict=verdict,
                confidence=confidence,
                explanation=explanation,
                why_verdict=why_verdict,
                sources=updated_sources,
                supporting_evidence=supporting_ev,
                original_quote=claim.original_quote,
                start_char=claim.start_char,
                end_char=claim.end_char,
                evidence_sufficiency=evidence_sufficiency,
                causal_role=claim.causal_role,
            )

        except Exception as e:
            logger.error(f"Error during verification for claim #{claim.id}: {e}")
            is_rate_limit = "429" in str(e) or "quota" in str(e).lower()
            return ClaimResult(
                id=claim.id,
                text=claim.text,
                type=claim.type,
                verdict=Verdict.VERIFICATION_ERROR,
                confidence=0.0,
                explanation=(
                    ("⚠️ Верификация прервана: внешний сервис верификации временно перегружен (Rate Limit 429). Доказательства найдены, но финальный шаг анализа не завершён." if is_rate_limit else f"⚠️ Верификация прервана: сбой внешнего сервиса ({str(e)[:100]}). Доказательства найдены, но логический шаг не завершён.")
                    if language == "ru"
                    else ("⚠️ Verification interrupted: external LLM rate limited. Evidence found, but reasoning incomplete." if is_rate_limit else f"⚠️ Verification interrupted: service error ({str(e)[:100]}).")
                ),
                why_verdict=(
                    "Внешний сервис верификации временно перегружен (Rate Limit 429)." if is_rate_limit else f"Ошибка верификатора: {str(e)[:100]}"
                ),
                sources=sources,
                supporting_evidence=[],
                original_quote=claim.original_quote,
                start_char=claim.start_char,
                end_char=claim.end_char,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                causal_role=claim.causal_role,
            )
