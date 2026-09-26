import asyncio
import logging
import uuid
from typing import List, Optional
from app.core.config import settings
from app.providers.llm import LLMProvider, get_llm_provider
from app.providers.search import SearchProvider, get_search_provider
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse, Summary
from app.schemas.claim import (
    Claim,
    ClaimResult,
    ClaimType,
    Source,
    SourceStance,
    SourceTier,
    SupportingEvidence,
    Verdict,
)
from app.services.aggregator import Aggregator
from app.services.claim_extractor import ClaimExtractor
from app.services.search import SearchService
from app.services.verifier import ClaimVerifier

logger = logging.getLogger("senimai.analyzer")


class Analyzer:
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        search_provider: Optional[SearchProvider] = None,
    ):
        self.llm = llm_provider or get_llm_provider()
        self.search_provider = search_provider or get_search_provider()

        self.claim_extractor = ClaimExtractor(self.llm)
        self.search_service = SearchService(self.search_provider)
        self.verifier = ClaimVerifier(self.llm)
        self.aggregator = Aggregator()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        import time

        start_time = time.perf_counter()
        logger.info(f"Starting analysis for text length={len(request.text)}, lang={request.language}")

        # Check for Mock Mode or offline fallback
        if settings.MOCK_MODE:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            resp = self.get_mock_analysis(request.text, request.language)
            resp.processing_time_ms = elapsed_ms
            return resp

        # Step 1: Claim Extraction
        claims = await self.claim_extractor.extract(
            text=request.text,
            max_claims=request.max_claims,
        )

        if not claims:
            logger.warning("No claims extracted from input text.")
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return self.aggregator.aggregate(
                claims=[],
                original_text=request.text,
                processing_time_ms=elapsed_ms,
            )

        logger.info(f"Extracted {len(claims)} claims. Beginning verification pipeline...")

        # Step 2 & 3: Parallel Search + Verification with concurrency limit
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_CLAIMS)

        async def process_single_claim(claim: Claim) -> ClaimResult:
            async with semaphore:
                try:
                    if claim.type == ClaimType.OPINION:
                        return await self.verifier.verify(claim=claim, sources=[], language=request.language)

                    # External search for sources
                    sources = await self.search_service.find_evidence(
                        claim=claim,
                        limit=settings.SEARCH_RESULTS_PER_CLAIM,
                    )

                    # Verify claim against collected sources
                    result = await self.verifier.verify(
                        claim=claim,
                        sources=sources,
                        language=request.language,
                    )
                    return result

                except Exception as e:
                    logger.error(f"Error processing claim #{claim.id}: {e}", exc_info=True)
                    return ClaimResult(
                        id=claim.id,
                        text=claim.text,
                        type=claim.type,
                        verdict=Verdict.UNVERIFIED,
                        confidence=0.3,
                        explanation=f"Ошибка обработки: {str(e)[:100]}",
                        why_verdict=f"Ошибка: {str(e)[:100]}",
                        sources=[],
                        original_quote=claim.original_quote,
                        start_char=claim.start_char,
                        end_char=claim.end_char,
                    )

        results: List[ClaimResult] = await asyncio.gather(
            *[process_single_claim(claim) for claim in claims]
        )

        # Step 4: Aggregate into final structured response
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        response = self.aggregator.aggregate(
            claims=results,
            original_text=request.text,
            processing_time_ms=elapsed_ms,
        )
        logger.info(
            f"Analysis completed in {elapsed_ms}ms: {response.summary.total_claims} claims, score={response.summary.verification_score}"
        )
        return response

    @staticmethod
    def get_mock_analysis(text: str, language: str = "ru") -> AnalyzeResponse:
        """Realistic mock generator matching the 3 hackathon demo scenarios."""
        lower_text = text.lower()
        analysis_id = f"demo_{uuid.uuid4().hex[:8]}"

        # Scenario 2: Obvious Hallucination / Contradiction (Mars)
        if "марс" in lower_text or "mars" in lower_text:
            quote = "Первый человек высадился на Марсе в 1969 году"
            start_pos = text.find(quote) if quote in text else 0
            end_pos = start_pos + len(quote) if quote in text else len(text)
            claims = [
                ClaimResult(
                    id=1,
                    text="Первый человек высадился на Марсе в 1969 году.",
                    type=ClaimType.TEMPORAL,
                    verdict=Verdict.CONTRADICTED,
                    confidence=0.98,
                    explanation="Источники опровергают это утверждение: пилотируемых высадок людей на Марс не было. В 1969 году миссия Аполлон-11 высадилась на Луне.",
                    why_verdict="Официальные исторические архивы NASA и хроники космических полетов подтверждают, что на Марсе работали только автоматические аппараты, а первая высадка человека на Луну состоялась в 1969 году.",
                    original_quote=quote if quote in text else text,
                    start_char=start_pos,
                    end_char=end_pos,
                    sources=[
                        Source(
                            title="NASA Human Spaceflight History",
                            url="https://www.nasa.gov/missions/human-exploration",
                            domain="nasa.gov",
                            snippet="No human has landed on Mars. NASA Apollo 11 landed astronauts on the Moon in July 1969.",
                            quality=SourceTier.HIGH,
                            stance=SourceStance.CONTRADICTS,
                        ),
                        Source(
                            title="Mars Exploration Timeline - Space.com",
                            url="https://www.space.com/mars-missions-history",
                            domain="space.com",
                            snippet="Only robotic probes and rovers (Curiosity, Perseverance) have operated on the surface of Mars.",
                            quality=SourceTier.MEDIUM,
                            stance=SourceStance.CONTRADICTS,
                        ),
                    ],
                    supporting_evidence=[
                        SupportingEvidence(
                            source_index=1,
                            reason="NASA официально подтверждает отсутствие пилотируемых высадок на Марс.",
                        )
                    ],
                )
            ]

        # Scenario 3: Partially Supported / Location error (Eiffel Tower in London)
        elif "эйфелев" in lower_text or "eiffel" in lower_text:
            q1 = "построена в 1889 году"
            q2 = "находится в Лондоне"
            claims = [
                ClaimResult(
                    id=1,
                    text="Эйфелева башня была построена в 1889 году.",
                    type=ClaimType.TEMPORAL,
                    verdict=Verdict.SUPPORTED,
                    confidence=0.97,
                    explanation="Источники подтверждают, что Эйфелева башня была открыта в 1889 году к Всемирной выставке.",
                    why_verdict="Официальный сайт монумента и энциклопедии единогласно указывают дату постройки — 1889 год.",
                    original_quote=q1 if q1 in text else None,
                    start_char=text.find(q1) if q1 in text else None,
                    end_char=text.find(q1) + len(q1) if q1 in text else None,
                    sources=[
                        Source(
                            title="Official Eiffel Tower History",
                            url="https://www.toureiffel.paris/en/the-monument/history",
                            domain="toureiffel.paris",
                            snippet="Built for the 1889 Exposition Universelle by Gustave Eiffel.",
                            quality=SourceTier.HIGH,
                            stance=SourceStance.SUPPORTS,
                        )
                    ],
                ),
                ClaimResult(
                    id=2,
                    text="Эйфелева башня находится в Лондоне.",
                    type=ClaimType.FACTUAL,
                    verdict=Verdict.CONTRADICTED,
                    confidence=0.99,
                    explanation="Источники опровергают данное утверждение: Эйфелева башня расположена в Париже (Франция), а не в Лондоне.",
                    why_verdict="Географические справочники и Википедия подтверждают нахождение башни на Марсовом поле в Париже, опровергая локацию в Лондоне.",
                    original_quote=q2 if q2 in text else None,
                    start_char=text.find(q2) if q2 in text else None,
                    end_char=text.find(q2) + len(q2) if q2 in text else None,
                    sources=[
                        Source(
                            title="Eiffel Tower - Wikipedia",
                            url="https://en.wikipedia.org/wiki/Eiffel_Tower",
                            domain="wikipedia.org",
                            snippet="The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France.",
                            quality=SourceTier.HIGH,
                            stance=SourceStance.CONTRADICTS,
                        )
                    ],
                ),
                ClaimResult(
                    id=3,
                    text="Эйфелева башня является самым посещаемым туристическим объектом в мире.",
                    type=ClaimType.COMPARATIVE,
                    verdict=Verdict.PARTIALLY_SUPPORTED,
                    confidence=0.82,
                    explanation="Эйфелева башня является самым посещаемым платным монументом в мире, однако среди всех достопримечательностей лидерство варьируется в зависимости от методологии подсчета.",
                    why_verdict="Источники называют объект одним из лидеров мирового туризма, но статус 'абсолютно самый посещаемый' зависит от методики учета (платный/бесплатный вход).",
                    original_quote=None,
                    sources=[
                        Source(
                            title="World Tourism Rankings & Monuments",
                            url="https://www.britannica.com/topic/Eiffel-Tower-Paris-France",
                            domain="britannica.com",
                            snippet="It is one of the most visited monuments in the world, with over 6 million visitors annually.",
                            quality=SourceTier.HIGH,
                            stance=SourceStance.SUPPORTS,
                        )
                    ],
                ),
            ]

        # Scenario 1 (Default): Normal supported fact with Python
        else:
            q1 = "создан Гвидо ван Россумом"
            q2 = "в 1991 году"
            claims = [
                ClaimResult(
                    id=1,
                    text="Python был создан Гвидо ван Россумом.",
                    type=ClaimType.FACTUAL,
                    verdict=Verdict.SUPPORTED,
                    confidence=0.96,
                    explanation="Официальная документация и история языка подтверждают авторство Гвидо ван Россума.",
                    why_verdict="Документация Python.org и биография автора подтверждают разработку языка Гвидо ван Россумом в институте CWI.",
                    original_quote=q1 if q1 in text else None,
                    start_char=text.find(q1) if q1 in text else None,
                    end_char=text.find(q1) + len(q1) if q1 in text else None,
                    sources=[
                        Source(
                            title="Python.org History & FAQ",
                            url="https://docs.python.org/3/faq/general.html",
                            domain="python.org",
                            snippet="Python was created in the early 1990s by Guido van Rossum at Stichting Mathematisch Centrum in the Netherlands.",
                            quality=SourceTier.HIGH,
                            stance=SourceStance.SUPPORTS,
                        ),
                        Source(
                            title="Guido van Rossum - Wikipedia",
                            url="https://en.wikipedia.org/wiki/Guido_van_Rossum",
                            domain="wikipedia.org",
                            snippet="Guido van Rossum is a Dutch programmer best known as the creator of the Python programming language.",
                            quality=SourceTier.HIGH,
                            stance=SourceStance.SUPPORTS,
                        ),
                    ],
                ),
                ClaimResult(
                    id=2,
                    text="Python был впервые выпущен в 1991 году.",
                    type=ClaimType.TEMPORAL,
                    verdict=Verdict.SUPPORTED,
                    confidence=0.95,
                    explanation="Первая публичная версия Python 0.9.0 была выпущена в феврале 1991 года.",
                    why_verdict="Архивы релизов alt.sources подтверждают первую публикацию версии 0.9.0 в феврале 1991 года.",
                    original_quote=q2 if q2 in text else None,
                    start_char=text.find(q2) if q2 in text else None,
                    end_char=text.find(q2) + len(q2) if q2 in text else None,
                    sources=[
                        Source(
                            title="A Brief Timeline of Python Releases",
                            url="https://www.python.org/doc/versions/",
                            domain="python.org",
                            snippet="Python 0.9.0 was published to alt.sources in February 1991.",
                            quality=SourceTier.HIGH,
                            stance=SourceStance.SUPPORTS,
                        )
                    ],
                ),
                ClaimResult(
                    id=3,
                    text="Python является лучшим языком программирования для всех задач.",
                    type=ClaimType.OPINION,
                    verdict=Verdict.NOT_FACT_CHECKABLE,
                    confidence=1.0,
                    explanation="Оценка 'лучший язык для всех задач' является субъективным мнением, а не объективным проверяемым фактом.",
                    why_verdict="Субъективные оценочные суждения не имеют проверяемой фактологической базы.",
                    sources=[],
                ),
            ]

        return Aggregator.aggregate(claims=claims, original_text=text, analysis_id=analysis_id)
