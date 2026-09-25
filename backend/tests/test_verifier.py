import pytest
from app.providers.llm import MockLLMProvider
from app.schemas.claim import (
    Claim,
    ClaimType,
    Source,
    SourceTier,
    Verdict,
)
from app.services.aggregator import Aggregator
from app.services.verifier import ClaimVerifier


@pytest.mark.asyncio
async def test_opinion_claim_is_not_fact_checkable():
    verifier = ClaimVerifier(llm=MockLLMProvider())
    opinion_claim = Claim(
        id=1,
        text="Этот фильм просто потрясающий и лучший в мире.",
        type=ClaimType.OPINION,
    )

    result = await verifier.verify(claim=opinion_claim, sources=[], language="ru")
    assert result.verdict == Verdict.NOT_FACT_CHECKABLE
    assert result.confidence == 1.0
    assert len(result.sources) == 0


@pytest.mark.asyncio
async def test_empty_sources_yields_unverified():
    verifier = ClaimVerifier(llm=MockLLMProvider())
    claim = Claim(
        id=2,
        text="Секретный проект X завершен в 2026 году.",
        type=ClaimType.FACTUAL,
    )

    result = await verifier.verify(claim=claim, sources=[], language="ru")
    assert result.verdict == Verdict.UNVERIFIED


@pytest.mark.asyncio
async def test_verifier_with_evidence():
    verifier = ClaimVerifier(llm=MockLLMProvider())
    claim = Claim(
        id=3,
        text="Python создан Гвидо ван Россумом.",
        type=ClaimType.FACTUAL,
    )
    sources = [
        Source(
            title="Python History",
            url="https://python.org",
            domain="python.org",
            snippet="Python was created by Guido van Rossum in 1991.",
            quality=SourceTier.HIGH,
        )
    ]

    result = await verifier.verify(claim=claim, sources=sources, language="ru")
    assert result.verdict in [
        Verdict.SUPPORTED,
        Verdict.CONTRADICTED,
        Verdict.PARTIALLY_SUPPORTED,
        Verdict.UNVERIFIED,
    ]
    assert len(result.sources) == 1


def test_aggregator_score_calculation():
    from app.schemas.claim import ClaimResult

    claims = [
        ClaimResult(
            id=1,
            text="Claim 1",
            type=ClaimType.FACTUAL,
            verdict=Verdict.SUPPORTED,
            confidence=0.9,
            explanation="OK",
            sources=[],
        ),
        ClaimResult(
            id=2,
            text="Claim 2",
            type=ClaimType.FACTUAL,
            verdict=Verdict.CONTRADICTED,
            confidence=0.9,
            explanation="False",
            sources=[],
        ),
    ]

    response = Aggregator.aggregate(claims=claims)
    assert response.summary.total_claims == 2
    assert response.summary.supported == 1
    assert response.summary.contradicted == 1
    assert response.summary.verification_score == 0.5
