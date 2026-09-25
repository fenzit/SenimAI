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

    def build_search_query(self, claim: Claim) -> str:
        text = claim.text.strip()
        # Remove quotes or punctuation that may distort search
        cleaned = re.sub(r'["\';:]', "", text)

        # Contextual augmentation based on claim type
        current_year = datetime.datetime.now().year
        if claim.type == ClaimType.TEMPORAL and not re.search(r"\b(19\d\d|20\d\d)\b", cleaned):
            return f"{cleaned} history date year"
        elif claim.type == ClaimType.COMPARATIVE:
            return f"{cleaned} ranking statistics {current_year}"
        elif claim.type == ClaimType.NUMERICAL:
            return f"{cleaned} statistics data"

        return cleaned

    async def find_evidence(self, claim: Claim, limit: int = 4) -> List[Source]:
        query = self.build_search_query(claim)
        logger.info(f"Searching for claim #{claim.id} with query: '{query}'")

        try:
            results = await self.provider.search(query=query, limit=limit)
            return EvidenceProcessor.to_sources(results)
        except Exception as e:
            logger.error(f"Search provider error on claim #{claim.id}: {e}")
            return []
