import asyncio
import html
import logging
import re
from typing import List, Optional
from app.providers.llm import LLMProvider
from app.providers.search import SearchProvider, SearchResult, classify_source_tier
from app.schemas.claim import Claim, ClaimType, Source, SourceTier
from app.services.evidence import EvidenceProcessor

logger = logging.getLogger("senimai.search_service")

QUERY_GENERATOR_SYSTEM_PROMPT = """You are a high-precision search query formulation & claim decomposition engine for an AI fact-checking system.
Your mission is to analyze an atomic claim along with its parent context and generate 2-4 targeted, disambiguated search queries that retrieve official documentation and authoritative primary sources.

CRITICAL DECOMPOSITION & TARGETING RULES:
1. TARGET OFFICIAL DOCUMENTATION FIRST:
   - For PostgreSQL: generate queries targeting `site:postgresql.org/docs` or `postgresql.org docs` (e.g. "site:postgresql.org/docs B-tree index LIKE pattern matching wildcard").
   - For Python & CPython: generate queries targeting `site:docs.python.org` (e.g. "site:docs.python.org asyncio cooperative event loop single thread CPU bound", "site:docs.python.org CPython integer caching small integers", "site:docs.python.org is operator identity vs equality").
   - For Web/HTTP: generate queries targeting `site:ietf.org` or `developer.mozilla.org` (e.g. "site:ietf.org RFC HTTP stateless protocol session state").
2. DECOMPOSE COMPOUND MECHANICS (Multi-Hop):
   - If a claim asserts a cause-and-effect or programming behavior (e.g. "Modifying list elements inside a function does not affect the original list"), decompose into atomic search queries:
     * Query 1: "site:docs.python.org list mutable sequence"
     * Query 2: "site:docs.python.org function argument passing object reference sharing"
3. DISAMBIGUATE ENTITY: ALWAYS include the specific subject (e.g. "Python", "PostgreSQL", "JavaScript") in every query.
4. PRESERVE SHORT KEYWORDS: Avoid long complex conversational sentences. Use search engine-friendly keyword queries.

JSON OUTPUT FORMAT:
{
  "primary_entity": "PostgreSQL",
  "domain": "programming | database | science | history | general",
  "sub_premises": [
    "PostgreSQL B-tree indexes support LIKE with leading constant",
    "PostgreSQL B-tree indexes cannot accelerate LIKE '%pattern' with leading wildcard"
  ],
  "queries": [
    "site:postgresql.org/docs B-tree index LIKE pattern matching",
    "PostgreSQL docs indexes types B-tree LIKE wildcard prefix",
    "site:postgresql.org/docs indexes-types.html"
  ]
}
"""


class RelevanceReranker:
    """Filters irrelevant noise and ranks evidence by semantic alignment and source tier."""

    NOISE_KEYWORDS = [
        "bittorrent", "torrent", "printf", "youtube", "callback", "iterator",
        "путин", "кадыров", "донбасс", "война", "москва", "лимузин", "казино",
    ]

    @staticmethod
    def is_noisy(snippet: str, title: str, domain: str, primary_entity: str) -> bool:
        full_text = f"{title} {snippet}".lower()
        entity_lower = (primary_entity or "").lower()

        # If primary entity is specific (e.g. Python)
        if entity_lower in ["python", "javascript", "c++", "golang", "rust", "sql"]:
            # If the snippet does not contain the primary entity and contains noisy words, drop it
            if entity_lower not in full_text and any(nk in full_text for nk in RelevanceReranker.NOISE_KEYWORDS):
                return True
        return False

    @staticmethod
    def score_snippet(result: SearchResult, claim: Claim, primary_entity: str) -> float:
        text = f"{result.title} {result.snippet}".lower()
        claim_words = [w.lower() for w in re.findall(r"\w+", claim.text) if len(w) > 3]
        
        score = 0.0
        # Tier bonus
        tier = classify_source_tier(result.domain)
        if tier == SourceTier.HIGH:
            score += 3.0
        elif tier == SourceTier.MEDIUM:
            score += 1.5

        # Primary entity presence
        if primary_entity and primary_entity.lower() in text:
            score += 3.0

        # Overlap with claim keywords
        overlap = sum(1 for w in claim_words if w in text)
        score += overlap * 0.5

        return score

    @classmethod
    def rerank(
        cls,
        candidates: List[SearchResult],
        claim: Claim,
        primary_entity: str = "",
        limit: int = 4,
    ) -> List[SearchResult]:
        filtered = []
        for c in candidates:
            if not cls.is_noisy(c.snippet, c.title, c.domain, primary_entity):
                filtered.append(c)

        if not filtered and candidates:
            filtered = candidates

        # Sort by score descending
        filtered.sort(key=lambda s: cls.score_snippet(s, claim, primary_entity), reverse=True)
        return filtered[:limit]


class SearchService:
    def __init__(self, provider: SearchProvider, llm: Optional[LLMProvider] = None):
        self.provider = provider
        self.llm = llm

    async def generate_queries(self, claim: Claim, context_text: Optional[str] = None) -> tuple[List[str], str]:
        """Generates disambiguated search queries using LLM if available, otherwise heuristic."""
        if self.llm:
            try:
                user_prompt = (
                    f"Parent Context: \"{context_text[:400] if context_text else claim.text}\"\n"
                    f"Claim #{claim.id} ({claim.type.value}): \"{claim.text}\"\n\n"
                    f"Decompose the claim and generate 2-4 targeted, disambiguated search queries."
                )
                res = await self.llm.generate_json(
                    system_prompt=QUERY_GENERATOR_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.0,
                )
                queries = res.get("queries", [])
                primary_entity = res.get("primary_entity", "")
                if queries and isinstance(queries, list):
                    clean_queries = [str(q).strip() for q in queries if str(q).strip()]
                    if clean_queries:
                        return clean_queries, primary_entity
            except Exception as e:
                logger.warning(f"LLM query generation failed, using heuristic: {e}")

        # Heuristic fallback
        return self._heuristic_queries(claim, context_text)

    def _heuristic_queries(self, claim: Claim, context_text: Optional[str] = None) -> tuple[List[str], str]:
        text = claim.text.strip()
        cleaned = re.sub(r'["\';:]', "", text)
        lower_context = (context_text or "").lower()
        lower_claim = cleaned.lower()

        queries = []
        primary_entity = ""

        if "python" in lower_context or "python" in lower_claim or "asyncio" in lower_claim or "cpython" in lower_claim:
            primary_entity = "Python"
            if "asyncio" in lower_claim:
                queries.append("site:docs.python.org asyncio cooperative event loop single thread CPU bound blocking")
                queries.append("Python asyncio non-blocking event loop CPU bound concurrency")
            if "256" in lower_claim or "целые числа" in lower_claim or "кэш" in lower_claim:
                queries.append("site:docs.python.org CPython small integer caching -5 to 256 identity")
                queries.append("CPython small integer caching implementation detail language specification")
            if "кортеж" in lower_claim or "tuple" in lower_claim:
                queries.append("site:docs.python.org tuple immutable sequence data model")
                queries.append("Python tuple immutable object reference")
            if "список" in lower_claim or "списк" in lower_claim or "list" in lower_claim:
                queries.append("site:docs.python.org list mutable sequence in place")
                queries.append("Python function argument passing mutable list reference")
            if "переда" in lower_claim or "значени" in lower_claim or "ссылк" in lower_claim:
                queries.append("site:docs.python.org FAQ argument passing assignment object sharing")
            if "is" in lower_claim or "равенств" in lower_claim or "сравнен" in lower_claim:
                queries.append("site:docs.python.org/3/reference/expressions.html is operator identity vs equality")
            if not queries:
                queries.append(f"site:docs.python.org {cleaned}")
        elif "postgres" in lower_context or "postgres" in lower_claim or "b-tree" in lower_claim or "like" in lower_claim:
            primary_entity = "PostgreSQL"
            queries.append("site:postgresql.org/docs B-tree index operator LIKE leading wildcard %")
            queries.append("PostgreSQL documentation B-tree pattern matching LIKE '%pattern' anchor")
        elif "http" in lower_context or "http" in lower_claim or "stateless" in lower_claim:
            primary_entity = "HTTP"
            queries.append("site:ietf.org RFC HTTP stateless protocol session state cookies")
            queries.append("developer.mozilla.org HTTP stateless session state")
        else:
            queries.append(cleaned)

        return queries, primary_entity

    async def find_evidence(
        self,
        claim: Claim,
        context_text: Optional[str] = None,
        limit: int = 4,
    ) -> List[Source]:
        queries, primary_entity = await self.generate_queries(claim, context_text)
        logger.info(f"Searching for claim #{claim.id} with queries: {queries}")

        candidates: List[SearchResult] = []
        seen_urls = set()

        for q in queries:
            try:
                results = await self.provider.search(query=q, limit=limit + 2)
                for r in results:
                    if r.url not in seen_urls and len(r.snippet.strip()) > 20:
                        seen_urls.add(r.url)
                        candidates.append(r)
            except Exception as e:
                logger.error(f"Search provider error on query '{q}': {e}")

            if len(candidates) >= limit * 3:
                break

        # Rerank and filter noise
        top_candidates = RelevanceReranker.rerank(
            candidates=candidates,
            claim=claim,
            primary_entity=primary_entity,
            limit=limit,
        )

        return EvidenceProcessor.to_sources(top_candidates)
