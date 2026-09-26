import logging
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.analyzer import Analyzer

logger = logging.getLogger("senimai.api")
router = APIRouter()

analyzer = Analyzer()


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze AI text for factual claims and verify against external evidence",
    status_code=status.HTTP_200_OK,
)
async def analyze_text(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze input text:
    1. Extracts atomic claims (factual, numerical, temporal, comparative, opinion).
    2. Gathers real-time external evidence from trusted web sources.
    3. Verifies each claim strictly against retrieved evidence.
    4. Explains verdicts and returns source citations + aggregate trust score.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input text cannot be empty.",
        )

    try:
        response = await analyzer.analyze(request)
        return response
    except Exception as e:
        logger.error(f"Analysis endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the verification: {str(e)}",
        )


@router.get("/health", summary="Service health and status check")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "mock_mode": settings.MOCK_MODE,
        "search_provider": settings.SEARCH_PROVIDER,
        "llm_model": settings.LLM_MODEL,
    }


@router.get("/demo-cases", summary="Get pre-built hackathon demo test cases")
async def get_demo_cases() -> List[Dict[str, Any]]:
    """Returns curated demo scenarios matching the hackathon requirements:
    1. Fully supported normal answer.
    2. Obvious hallucination / contradiction.
    3. Plausible partially supported answer with localized factual error.
    """
    return [
        {
            "id": "demo-1",
            "title": "Сценарий 1: Корректный ответ (Python)",
            "text": "Python был создан нидерландским программистом Гвидо ван Россумом и впервые выпущен в 1991 году.",
            "description": "Показывает, что система не выдумывает ложные ошибки там, где факты подтверждены.",
        },
        {
            "id": "demo-2",
            "title": "Сценарий 2: Явная галлюцинация (Марс 1969)",
            "text": "Первый человек высадился на поверхность Марса в июле 1969 года в рамках американской космической программы.",
            "description": "Показывает выявление явной фактологической ошибки (CONTRADICTED) с цитированием данных NASA.",
        },
        {
            "id": "demo-3",
            "title": "Сценарий 3: Частичная ошибка (Эйфелева башня в Лондоне)",
            "text": "Эйфелева башня была построена в 1889 году инженером Гюставом Эйфелем и находится в центре Лондона.",
            "description": "Показывает силу атомарного фактчекинга: дата верна (Париж 1889), но локация ошибочна (Париж, не Лондон).",
        },
    ]


@router.post(
    "/export/markdown",
    summary="Export analysis result into a formatted Markdown report",
    status_code=status.HTTP_200_OK,
)
async def export_markdown(analysis: AnalyzeResponse) -> Dict[str, str]:
    """Converts structured verification response into a clean, shareable Markdown report."""
    verdict_emojis = {
        "SUPPORTED": "🟢 SUPPORTED",
        "CONTRADICTED": "🔴 CONTRADICTED",
        "PARTIALLY_SUPPORTED": "🟡 PARTIALLY SUPPORTED",
        "NUANCED": "⚠️ NUANCED",
        "UNVERIFIED": "⚪ UNVERIFIED (Insufficient Evidence)",
        "NOT_FACT_CHECKABLE": "🟣 NOT FACT-CHECKABLE",
        "CONFLICTING": "🟠 CONFLICTING",
        "VERIFICATION_ERROR": "⚠️ VERIFICATION INTERRUPTED (Service Error)",
    }

    overall_verdict_badge = analysis.summary.overall_verdict or "MIXED"
    summary_line = analysis.summary.summary_line or f"{analysis.summary.supported} supported · {analysis.summary.contradicted} contradicted"
    confidence_label = analysis.summary.evidence_confidence_label or "Medium"

    relevance_emojis = {
        "DIRECT": "🟢 Direct Evidence",
        "RELATED": "🟡 Related Context",
        "NOT_RELEVANT": "⚪ Background / Indirect",
    }

    lines = [
        f"# 🛡️ AI Trust Verification Report — ID: `{analysis.analysis_id}`",
        f"## 📋 Result: `{summary_line}`",
        f"**Verdict:** `{overall_verdict_badge}` | **Verified Claims:** `{analysis.summary.verified_claims_count}/{analysis.summary.total_claims}` | **Evidence Status:** `{analysis.summary.evidence_status}`",
        f"**Evidence Confidence:** `{confidence_label}`",
        "",
        "### 📊 Summary Breakdown",
        f"- 🟢 **Supported (Confirmed):** {analysis.summary.supported}",
        f"- 🔴 **Contradicted (False):** {analysis.summary.contradicted}",
        f"- 🟡 **Partially Supported:** {analysis.summary.partially_supported}",
        f"- ⚠️ **Nuanced / Contextual:** {analysis.summary.nuanced}",
        f"- ⚪ **Unverified (Insufficient Evidence):** {analysis.summary.unverified}",
        f"- 🟣 **Subjective Opinions:** {analysis.summary.not_fact_checkable}",
        f"- 🟠 **Conflicting Sources:** {analysis.summary.conflicting}",
        f"- ⚠️ **Interrupted / Errors:** {analysis.summary.verification_errors}",
        "",
        "---",
        "### 🔍 Detailed Claims Analysis",
    ]

    for c in analysis.claims:
        badge = verdict_emojis.get(c.verdict.value, c.verdict.value)
        suff_badge = f" `[{c.evidence_sufficiency.value}]`" if getattr(c, "evidence_sufficiency", None) else ""
        role_badge = f" `[{c.causal_role}]`" if getattr(c, "causal_role", None) and c.causal_role != "STANDALONE" else ""
        lines.append(f"#### Claim #{c.id}: \"{c.text}\"{role_badge}")
        lines.append(f"- **Verdict:** {badge}{suff_badge} (Confidence: `{int(c.confidence * 100)}%`)")
        lines.append(f"- **Type:** `{c.type.value}`")
        lines.append(f"- **Explanation:** {c.explanation}")
        if c.why_verdict:
            lines.append(f"- **Why / Reasoning:** {c.why_verdict}")
        if c.sources:
            lines.append("- **Sources & Evidence Relevance:**")
            for s in c.sources:
                quality_badge = f"[{s.quality.value}]"
                stance_badge = f"({s.stance.value})" if s.stance else ""
                rel_badge = relevance_emojis.get(getattr(s, "relevance", "RELATED"), "🟡 Related Context")
                reason_suffix = f" — *{s.relevance_reason}*" if getattr(s, "relevance_reason", None) else ""
                freshness = f" • {s.published_date}" if s.published_date else ""
                lines.append(f"  - [{s.title}]({s.url}) `{s.domain}` {quality_badge} {stance_badge} | {rel_badge}{reason_suffix}{freshness}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by SenimAI — Evidence-Based AI Fact-Checking Pipeline*")

    md_content = "\n".join(lines)
    return {"markdown": md_content, "analysis_id": analysis.analysis_id}
