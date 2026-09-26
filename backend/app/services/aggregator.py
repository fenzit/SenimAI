import datetime
import uuid
from typing import List, Optional
from app.schemas.analysis import AnalyzeResponse, Summary
from app.schemas.claim import ClaimResult, SourceTier, Verdict


class Aggregator:
    @staticmethod
    def aggregate(
        claims: List[ClaimResult],
        original_text: Optional[str] = None,
        analysis_id: Optional[str] = None,
        processing_time_ms: Optional[float] = None,
    ) -> AnalyzeResponse:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        total = len(claims)
        if total == 0:
            summary = Summary(
                total_claims=0,
                supported=0,
                contradicted=0,
                partially_supported=0,
                unverified=0,
                not_fact_checkable=0,
                conflicting=0,
                verification_score=1.0,
                high_quality_sources_count=0,
                average_confidence=1.0,
            )
            return AnalyzeResponse(
                analysis_id=analysis_id or f"analysis_{uuid.uuid4().hex[:12]}",
                summary=summary,
                claims=[],
                original_text=original_text,
                processing_time_ms=processing_time_ms,
                timestamp=now_iso,
            )

        counts = {
            Verdict.SUPPORTED: 0,
            Verdict.CONTRADICTED: 0,
            Verdict.PARTIALLY_SUPPORTED: 0,
            Verdict.UNVERIFIED: 0,
            Verdict.NOT_FACT_CHECKABLE: 0,
            Verdict.CONFLICTING: 0,
        }

        high_quality_sources = 0
        total_conf = 0.0

        for c in claims:
            total_conf += c.confidence
            for s in c.sources:
                if s.quality == SourceTier.HIGH:
                    high_quality_sources += 1

            if c.verdict in counts:
                counts[c.verdict] += 1
            else:
                counts[Verdict.UNVERIFIED] += 1

        avg_conf = round(total_conf / total, 2) if total > 0 else 0.0

        # Calculate verification score as defined in Section 25 of Tech Spec:
        # score = (supported * 1.0 + partially_supported * 0.5 + unverified * 0.25 + contradicted * 0.0) / total_checkable
        checkable_total = total - counts[Verdict.NOT_FACT_CHECKABLE]
        if checkable_total <= 0:
            score = 1.0
        else:
            raw_score = (
                counts[Verdict.SUPPORTED] * 1.0
                + counts[Verdict.PARTIALLY_SUPPORTED] * 0.5
                + counts[Verdict.CONFLICTING] * 0.3
                + counts[Verdict.UNVERIFIED] * 0.2
                + counts[Verdict.CONTRADICTED] * 0.0
            ) / checkable_total
            score = round(max(0.0, min(1.0, raw_score)), 2)

        # Determine overall verdict
        if checkable_total <= 0:
            overall_verdict = "OPINION"
        elif counts[Verdict.CONTRADICTED] >= (counts[Verdict.SUPPORTED] + counts[Verdict.PARTIALLY_SUPPORTED]) and counts[Verdict.CONTRADICTED] > 0:
            overall_verdict = "FALSE"
        elif score >= 0.75 and counts[Verdict.CONTRADICTED] == 0:
            overall_verdict = "TRUE"
        elif counts[Verdict.UNVERIFIED] == checkable_total:
            overall_verdict = "UNVERIFIED"
        else:
            overall_verdict = "MIXED"

        summary = Summary(
            total_claims=total,
            supported=counts[Verdict.SUPPORTED],
            contradicted=counts[Verdict.CONTRADICTED],
            partially_supported=counts[Verdict.PARTIALLY_SUPPORTED],
            unverified=counts[Verdict.UNVERIFIED],
            not_fact_checkable=counts[Verdict.NOT_FACT_CHECKABLE],
            conflicting=counts[Verdict.CONFLICTING],
            verification_score=score,
            high_quality_sources_count=high_quality_sources,
            average_confidence=avg_conf,
            overall_verdict=overall_verdict,
        )

        return AnalyzeResponse(
            analysis_id=analysis_id or f"analysis_{uuid.uuid4().hex[:12]}",
            summary=summary,
            claims=claims,
            original_text=original_text,
            processing_time_ms=processing_time_ms,
            timestamp=now_iso,
        )
