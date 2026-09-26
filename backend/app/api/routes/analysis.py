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
        "UNVERIFIED": "⚪ UNVERIFIED",
        "NOT_FACT_CHECKABLE": "🟣 NOT FACT-CHECKABLE",
        "CONFLICTING": "🟠 CONFLICTING",
    }

    score_pct = int(analysis.summary.verification_score * 100)
    lines = [
        f"# 🛡️ AI Trust Verification Report — ID: `{analysis.analysis_id}`",
        f"**Verification Score:** `{score_pct}%` | **Total Claims:** `{analysis.summary.total_claims}`",
        "",
        "### 📊 Summary Breakdown",
        f"- 🟢 **Supported:** {analysis.summary.supported}",
        f"- 🔴 **Contradicted:** {analysis.summary.contradicted}",
        f"- 🟡 **Partially Supported:** {analysis.summary.partially_supported}",
        f"- ⚪ **Unverified:** {analysis.summary.unverified}",
        f"- 🟣 **Opinions:** {analysis.summary.not_fact_checkable}",
        f"- 🟠 **Conflicting:** {analysis.summary.conflicting}",
        "",
        "---",
        "### 🔍 Detailed Claims Analysis",
    ]

    for c in analysis.claims:
        badge = verdict_emojis.get(c.verdict.value, c.verdict.value)
        lines.append(f"#### Claim #{c.id}: \"{c.text}\"")
        lines.append(f"- **Verdict:** {badge} (Confidence: `{int(c.confidence * 100)}%`)")
        lines.append(f"- **Type:** `{c.type.value}`")
        lines.append(f"- **Explanation:** {c.explanation}")
        if c.why_verdict:
            lines.append(f"- **Why:** {c.why_verdict}")
        if c.sources:
            lines.append("- **Sources:**")
            for s in c.sources:
                quality_badge = f"[{s.quality.value}]"
                stance_badge = f"({s.stance.value})" if s.stance else ""
                lines.append(f"  - [{s.title}]({s.url}) `{s.domain}` {quality_badge} {stance_badge}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by SenimAI — Evidence-Based AI Fact-Checking Pipeline*")

    md_content = "\n".join(lines)
    return {"markdown": md_content, "analysis_id": analysis.analysis_id}
