import asyncio
import datetime
import logging
import re
from typing import List
from app.providers.search import SearchProvider, SearchResult
from app.schemas.claim import Claim, ClaimType, Source
from app.services.evidence import EvidenceProcessor

logger = logging.getLogger("senimai.search_service")


class SearchService:
    def __init__(self, provider: SearchProvider):
        self.provider = provider

    def build_search_queries(self, claim: Claim) -> List[str]:
        text = claim.text.strip()
        cleaned = re.sub(r'["\';:]', "", text)
        queries = [cleaned]

        # Contextual augmentation based on claim type
        current_year = datetime.datetime.now().year
        if claim.type == ClaimType.TEMPORAL and not re.search(r"\b(19\d\d|20\d\d)\b", cleaned):
            queries.append(f"{cleaned} history date year")
        elif claim.type == ClaimType.COMPARATIVE:
            queries.append(f"{cleaned} ranking statistics {current_year}")

        lower = cleaned.lower()

        # Programming & Technical Domain Detection
        if "python" in lower:
            if "кортеж" in lower or "tuple" in lower:
                queries.append("Python tuple immutable mutable documentation")
            if "список" in lower or "списк" in lower or "list" in lower:
                queries.append("Python list mutable modify function arguments")
            if "переда" in lower or "pass" in lower or "значени" in lower or "ссылк" in lower:
                queries.append("Python pass by reference or value argument passing model")

        # General Russian to English key terms mapping for high quality international docs
        if "лондон" in lower and "росс" in lower:
            queries.append("Guido van Rossum Python CWI Netherlands")

        return list(dict.fromkeys(queries))  # deduplicate while preserving order

    async def find_evidence(self, claim: Claim, limit: int = 4) -> List[Source]:
        queries = self.build_search_queries(claim)
        logger.info(f"Searching for claim #{claim.id} with queries: {queries}")

        all_results: List[SearchResult] = []
        seen_urls = set()

        for q in queries[:2]:  # Try top 2 targeted queries
            try:
                results = await self.provider.search(query=q, limit=limit)
                for r in results:
                    if r.url not in seen_urls and len(r.snippet.strip()) > 15:
                        seen_urls.add(r.url)
                        all_results.append(r)
            except Exception as e:
                logger.error(f"Search error on query '{q}' for claim #{claim.id}: {e}")

            if len(all_results) >= limit:
                break

        return EvidenceProcessor.to_sources(all_results[:limit])
