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
                nuanced=0,
                unverified=0,
                not_fact_checkable=0,
                conflicting=0,
                verified_claims_count=0,
                evidence_status="INSUFFICIENT",
                verification_score=1.0,
                high_quality_sources_count=0,
                average_confidence=1.0,
                overall_verdict="TRUE",
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
            Verdict.NUANCED: 0,
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

        checkable_total = total - counts[Verdict.NOT_FACT_CHECKABLE]
        verified_claims_count = (
            counts[Verdict.SUPPORTED]
            + counts[Verdict.CONTRADICTED]
            + counts[Verdict.PARTIALLY_SUPPORTED]
            + counts[Verdict.NUANCED]
            + counts[Verdict.CONFLICTING]
        )

        # Evidence Status
        if verified_claims_count == 0 and checkable_total > 0:
            evidence_status = "INSUFFICIENT"
        elif counts[Verdict.UNVERIFIED] > 0:
            evidence_status = "PARTIAL"
        else:
            evidence_status = "SUFFICIENT"

        # Verification Score & Verdict calculation:
        # Trust score is computed ONLY on claims where evidence was actually retrieved
        if checkable_total <= 0:
            score = 1.0
            overall_verdict = "OPINION"
        elif verified_claims_count == 0:
            score = 0.0
            overall_verdict = "INSUFFICIENT_EVIDENCE"
        else:
            raw_score = (
                counts[Verdict.SUPPORTED] * 1.0
                + counts[Verdict.PARTIALLY_SUPPORTED] * 0.6
                + counts[Verdict.NUANCED] * 0.5
                + counts[Verdict.CONFLICTING] * 0.3
                + counts[Verdict.CONTRADICTED] * 0.0
            ) / verified_claims_count
            score = round(max(0.0, min(1.0, raw_score)), 2)

            # Determine overall verdict
            if counts[Verdict.CONTRADICTED] >= (counts[Verdict.SUPPORTED] + counts[Verdict.PARTIALLY_SUPPORTED]) and counts[Verdict.CONTRADICTED] > 0:
                overall_verdict = "FALSE"
            elif counts[Verdict.CONTRADICTED] > 0 and score < 0.4:
                overall_verdict = "FALSE"
            elif score >= 0.75 and counts[Verdict.CONTRADICTED] == 0:
                overall_verdict = "TRUE"
            elif counts[Verdict.NUANCED] > 0 and counts[Verdict.CONTRADICTED] == 0 and counts[Verdict.SUPPORTED] == 0:
                overall_verdict = "NUANCED"
            else:
                overall_verdict = "MIXED"

        summary = Summary(
            total_claims=total,
            supported=counts[Verdict.SUPPORTED],
            contradicted=counts[Verdict.CONTRADICTED],
            partially_supported=counts[Verdict.PARTIALLY_SUPPORTED],
            nuanced=counts[Verdict.NUANCED],
            unverified=counts[Verdict.UNVERIFIED],
            not_fact_checkable=counts[Verdict.NOT_FACT_CHECKABLE],
            conflicting=counts[Verdict.CONFLICTING],
            verified_claims_count=verified_claims_count,
            evidence_status=evidence_status,
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
