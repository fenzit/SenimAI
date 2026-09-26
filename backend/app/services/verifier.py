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
2. MULTI-HOP INFERENCE & CAUSAL REASONING:
   - Mechanism & Concurrency: If evidence states "asyncio uses a single-threaded cooperative event loop where tasks must await I/O", deduce that CPU-bound tasks running in a single thread cannot execute in parallel and will block the loop. Verdict: CONTRADICTED, Sufficiency: COMBINED.
   - Causal Sophisms / False Deductions: If evidence confirms Premise A ("HTTP is stateless") but also shows ("Servers maintain sessions and state via cookies/storage"), deduce that the inference "therefore server cannot store state" is logically false. Verdict: CONTRADICTED or PARTIALLY_SUPPORTED with explicit explanation of the invalid deduction.
   - Identity vs Value / Caching: If evidence states CPython caches integers in range [-5, 256], deduce that comparing arbitrary integers outside this range with `is` (identity) is not guaranteed to be true, and `is` tests identity while `==` tests value equality. Verdict: CONTRADICTED or NUANCED.
3. If a single source directly confirms or refutes the exact claim, mark evidence_sufficiency: 'DIRECT'.
4. If the conclusion is derived from synthesizing multiple sources/premises or applying logical deduction to established mechanisms, mark evidence_sufficiency: 'COMBINED'.
5. If the evidence provides only indirect/circumstantial support, mark evidence_sufficiency: 'INDIRECT'.
6. Only return 'UNVERIFIED' with evidence_sufficiency: 'INSUFFICIENT' if the provided evidence has ZERO relevant information about the concepts/mechanisms in the claim.
7. If the claim touches upon a subtle technical distinction or terminology dispute (e.g. Python argument passing being 'call by sharing / object reference' rather than pure 'by value' or 'by reference'), return 'NUANCED'.
8. If reputable sources in the evidence directly contradict each other, return 'CONFLICTING'.
9. If the evidence directly or through multi-hop deduction refutes the claim, return 'CONTRADICTED'.
10. If the evidence confirms the claim, return 'SUPPORTED'.
11. Provide a clear, objective explanation in the requested language ({language}) citing specific details and logical steps.
12. Provide a 'why_verdict' breakdown explaining the step-by-step reasoning or logical chain (Premise 1 -> Premise 2 -> Deduction).
13. For each source evaluated, classify its stance: 'SUPPORTS', 'CONTRADICTS', 'NEUTRAL', or 'INSUFFICIENT'.

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
      "stance": "SUPPORTS | CONTRADICTS | NEUTRAL | INSUFFICIENT"
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

            # Update source stances
            stances_map = {}
            for st in result.get("source_stances", []):
                s_idx = int(st.get("source_index", 0))
                s_val = str(st.get("stance", "NEUTRAL")).upper()
                try:
                    stances_map[s_idx] = SourceStance(s_val)
                except ValueError:
                    stances_map[s_idx] = SourceStance.NEUTRAL

            updated_sources: List[Source] = []
            for i, src in enumerate(sources, start=1):
                src_copy = src.model_copy()
                if i in stances_map:
                    src_copy.stance = stances_map[i]
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
            return ClaimResult(
                id=claim.id,
                text=claim.text,
                type=claim.type,
                verdict=Verdict.UNVERIFIED,
                confidence=0.3,
                explanation=(
                    f"Произошла ошибка при верификации: {str(e)[:100]}. Требуется ручная проверка."
                    if language == "ru"
                    else f"Verification error: {str(e)[:100]}. Manual check recommended."
                ),
                why_verdict=f"Ошибка обработки: {str(e)[:100]}",
                sources=sources,
                supporting_evidence=[],
                original_quote=claim.original_quote,
                start_char=claim.start_char,
                end_char=claim.end_char,
                evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT,
                causal_role=claim.causal_role,
            )
