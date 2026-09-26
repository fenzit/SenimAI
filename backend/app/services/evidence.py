import re
from typing import List
from app.providers.search import SearchResult, classify_source_tier
from app.schemas.claim import Source


class EvidenceProcessor:
    """Prepares and sanitizes external evidence for LLM verification."""

    @staticmethod
    def sanitize_snippet(text: str, max_chars: int = 500) -> str:
        if not text:
            return ""

        # Remove HTML tags if any remain
        cleaned = re.sub(r"<[^>]+>", " ", text)

        # Prompt injection neutralization: replace obvious jailbreak instructions in snippets
        injection_patterns = [
            r"(?i)ignore\s+previous\s+instructions",
            r"(?i)system\s*prompt",
            r"(?i)you\s+are\s+now\s+in\s+dan\s+mode",
            r"(?i)say\s+that\s+this\s+claim\s+is\s+true",
            r"(?i)always\s+return\s+supported",
        ]
        for pat in injection_patterns:
            cleaned = re.sub(pat, "[FILTERED_INSTRUCTION]", cleaned)

        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars] + "..."
        return cleaned

    @staticmethod
    def to_sources(search_results: List[SearchResult]) -> List[Source]:
        sources: List[Source] = []
        for r in search_results:
            clean_snip = EvidenceProcessor.sanitize_snippet(r.snippet)
            quality = classify_source_tier(r.domain)
            freshness = None
            if r.published_date:
                freshness = f"Published: {r.published_date}"
            sources.append(
                Source(
                    title=r.title or f"Source from {r.domain}",
                    url=r.url or "https://example.com",
                    domain=r.domain or "web",
                    snippet=clean_snip,
                    quality=quality,
                    published_date=r.published_date,
                    freshness_label=freshness,
                )
            )
        return sources

    @staticmethod
    def format_evidence_for_prompt(sources: List[Source]) -> str:
        if not sources:
            return "No external evidence found."

        evidence_blocks = []
        for i, src in enumerate(sources, start=1):
            date_info = f"\nPublished Date: {src.published_date}" if src.published_date else ""
            evidence_blocks.append(
                f"[Source {i}]\n"
                f"Domain: {src.domain} (Quality: {src.quality.value}){date_info}\n"
                f"Title: {src.title}\n"
                f"URL: {src.url}\n"
                f"Excerpt: {src.snippet}"
            )
        return "\n\n".join(evidence_blocks)
