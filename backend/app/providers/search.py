import asyncio
import html
import logging
import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Optional
import httpx
from pydantic import BaseModel, Field
from app.core.config import settings
from app.schemas.claim import Source, SourceTier

logger = logging.getLogger("senimai.search")


class SearchResult(BaseModel):
    title: str
    url: str
    domain: str
    snippet: str
    score: float = 0.0
    published_date: Optional[str] = None


def extract_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or "external"
    except Exception:
        return "external"


def classify_source_tier(domain: str) -> SourceTier:
    """Classifies sources according to the 4-tier hierarchy:
    - HIGH: Official documentation, RFCs, scientific standards, government/academic domains.
    - MEDIUM: Reputable technical portals, major encyclopedias, peer Q&A.
    - LOW: Generic blogs, community posts.
    """
    domain_lower = domain.lower()
    
    # Tier 1: Primary Documentation, Standards, Academic & Gov
    primary_official = [
        "docs.python.org",
        "python.org",
        "postgresql.org",
        "developer.mozilla.org",
        "w3.org",
        "ietf.org",
        "iso.org",
        "ecma-international.org",
        "sqlite.org",
        "redis.io",
        "kernel.org",
        "who.int",
        "nasa.gov",
        "un.org",
        "nature.com",
        "science.org",
        "arxiv.org",
    ]
    if (
        any(po in domain_lower for po in primary_official)
        or domain_lower.endswith(".gov")
        or domain_lower.endswith(".gov.kz")
        or domain_lower.endswith(".edu")
        or domain_lower.endswith(".edu.kz")
    ):
        return SourceTier.HIGH

    # Tier 2: Reputable Technical Platforms, Major News & Encyclopedias
    reputable_domains = [
        "wikipedia.org",
        "britannica.com",
        "stackoverflow.com",
        "github.com",
        "realpython.com",
        "geeksforgeeks.org",
        "habr.com",
        "reuters.com",
        "bbc.com",
        "bbc.co.uk",
        "bloomberg.com",
        "tengrinews.kz",
        "inform.kz",
        "forbes.com",
    ]
    if any(rep in domain_lower for rep in reputable_domains):
        return SourceTier.HIGH

    medium_indicators = [
        "medium.com",
        "dev.to",
        "news",
        "journal",
        "times",
        "post",
        "guide",
    ]
    if any(med in domain_lower for med in medium_indicators):
        return SourceTier.MEDIUM

    return SourceTier.LOW


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Perform external search for query and return top results."""
        pass


class TavilySearchProvider(SearchProvider):
    def __init__(self, api_key: Optional[str] = None, timeout: int = 20):
        self.api_key = api_key or settings.TAVILY_API_KEY
        self.timeout = timeout

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is not configured.")

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": limit,
            "include_raw_content": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            results: List[SearchResult] = []
            for item in data.get("results", []):
                item_url = item.get("url", "")
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item_url,
                        domain=extract_domain(item_url),
                        snippet=item.get("content", ""),
                        score=float(item.get("score", 0.0)),
                        published_date=item.get("published_date"),
                    )
                )
            return results


class SerperSearchProvider(SearchProvider):
    def __init__(self, api_key: Optional[str] = None, timeout: int = 20):
        self.api_key = api_key or settings.SERPER_API_KEY
        self.timeout = timeout

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is not configured.")

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": query, "num": limit}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            results: List[SearchResult] = []
            for item in data.get("organic", []):
                item_url = item.get("link", "")
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item_url,
                        domain=extract_domain(item_url),
                        snippet=item.get("snippet", ""),
                        published_date=item.get("date"),
                    )
                )
            return results


class WikipediaSearchProvider(SearchProvider):
    """Authoritative open encyclopedia search (EN and RU) via official MediaWiki API."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    async def search(self, query: str, limit: int = 4) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_q = re.sub(r'["\';:]', " ", query).strip()
        
        # Search both English and Russian Wikipedia
        endpoints = [
            ("ru", "https://ru.wikipedia.org/w/api.php"),
            ("en", "https://en.wikipedia.org/w/api.php"),
        ]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "SenimAI-FactChecker/1.0 (info@senimai.kz)"},
        ) as client:
            for lang, endpoint in endpoints:
                try:
                    params = {
                        "action": "query",
                        "list": "search",
                        "srsearch": clean_q,
                        "format": "json",
                        "srlimit": limit,
                    }
                    resp = await client.get(endpoint, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        search_items = data.get("query", {}).get("search", [])
                        for item in search_items:
                            title = item.get("title", "")
                            raw_snip = item.get("snippet", "")
                            clean_snip = html.unescape(re.sub(r"<[^>]+>", " ", raw_snip)).strip()
                            page_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                            results.append(
                                SearchResult(
                                    title=f"{title} — Wikipedia ({lang.upper()})",
                                    url=page_url,
                                    domain="wikipedia.org",
                                    snippet=clean_snip,
                                    score=0.9,
                                )
                            )
                except Exception as e:
                    logger.debug(f"Wikipedia search failed for lang {lang}: {e}")

        return results[:limit]


class DuckDuckGoInstantProvider(SearchProvider):
    """DuckDuckGo Official Instant Answers API provider."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    async def search(self, query: str, limit: int = 3) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
                "skip_disambig": "0",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("AbstractText", "")
                    abstract_url = data.get("AbstractURL", "")
                    if abstract and abstract_url:
                        results.append(
                            SearchResult(
                                title=data.get("Heading", "DuckDuckGo Instant Answer"),
                                url=abstract_url,
                                domain=extract_domain(abstract_url),
                                snippet=abstract,
                                score=0.85,
                            )
                        )
                    for topic in data.get("RelatedTopics", [])[:limit]:
                        t_text = topic.get("Text", "")
                        t_url = topic.get("FirstURL", "")
                        if t_text and t_url:
                            results.append(
                                SearchResult(
                                    title=t_text[:50] + "...",
                                    url=t_url,
                                    domain=extract_domain(t_url),
                                    snippet=t_text,
                                    score=0.8,
                                )
                            )
        except Exception as e:
            logger.debug(f"DDG Instant search failed: {e}")
        return results[:limit]


class MockSearchProvider(SearchProvider):
    """Realistic mock search results for hackathon demonstrations and testing."""

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        q = query.lower()
        if "марсе" in q or "mars" in q:
            return [
                SearchResult(
                    title="NASA Human Spaceflight Milestones",
                    url="https://www.nasa.gov/missions/human-exploration",
                    domain="nasa.gov",
                    snippet="No humans have yet landed on Mars. Apollo missions landed 12 American astronauts on the Moon between 1969 and 1972.",
                ),
                SearchResult(
                    title="Mars Exploration Timeline - Space.com",
                    url="https://www.space.com/mars-missions-history",
                    domain="space.com",
                    snippet="Only robotic rovers and orbiters have visited the surface of Mars. Human exploration missions are being planned for the 2030s.",
                ),
            ]
        elif "лондон" in q or "london" in q or "эйфелев" in q or "eiffel" in q:
            return [
                SearchResult(
                    title="Eiffel Tower - Official History & Location",
                    url="https://www.toureiffel.paris/en/the-monument/history",
                    domain="toureiffel.paris",
                    snippet="The Eiffel Tower is a wrought-iron lattice tower located on the Champ de Mars in Paris, France. Constructed in 1889 for the Exposition Universelle.",
                ),
                SearchResult(
                    title="Eiffel Tower - Wikipedia",
                    url="https://en.wikipedia.org/wiki/Eiffel_Tower",
                    domain="wikipedia.org",
                    snippet="The Eiffel Tower is a wrought-iron tower on the Champ de Mars in Paris, France. It was designed by Gustave Eiffel and built from 1887 to 1889.",
                ),
            ]
        elif "python" in q or "россум" in q or "tuple" in q or "кортеж" in q:
            return [
                SearchResult(
                    title="Python Data Model — Official Python Documentation",
                    url="https://docs.python.org/3/reference/datamodel.html",
                    domain="docs.python.org",
                    snippet="Tuples are immutable sequences in Python. An immutable sequence cannot be altered after creation. Lists are mutable sequences.",
                ),
                SearchResult(
                    title="Python FAQ: How are arguments passed in Python?",
                    url="https://docs.python.org/3/faq/programming.html#how-do-i-write-a-function-with-output-parameters",
                    domain="docs.python.org",
                    snippet="Remember that arguments are passed by assignment in Python. Since assignment just creates references to objects, there's no alias between an argument name and caller object, but mutable objects can be modified in place.",
                ),
            ]
        else:
            return [
                SearchResult(
                    title=f"Verified encyclopedia entry: {query}",
                    url="https://en.wikipedia.org/wiki/Search",
                    domain="wikipedia.org",
                    snippet=f"Documented records and facts concerning {query}.",
                ),
                SearchResult(
                    title="Independent news and facts overview",
                    url="https://reuters.com/search",
                    domain="reuters.com",
                    snippet=f"Independent reports regarding {query}.",
                ),
            ]


class DuckDuckGoWebSearchProvider(SearchProvider):
    """Real web search provider using DuckDuckGo HTML endpoint to retrieve official documentation and web sources."""

    def __init__(self, timeout: int = 12):
        self.timeout = timeout

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        results: List[SearchResult] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = "https://html.duckduckgo.com/html/"
        clean_q = re.sub(r'["\';:]', " ", query).strip()

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                resp = await client.post(url, data={"q": clean_q})
                if resp.status_code == 200:
                    pattern = re.compile(
                        r'<a[^>]+class="result__snippet"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        re.DOTALL,
                    )
                    matches = pattern.findall(resp.text)
                    for raw_url, snip in matches[:limit + 2]:
                        if "uddg=" in raw_url:
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                            actual_url = parsed.get("uddg", [raw_url])[0]
                        else:
                            actual_url = raw_url

                        clean_snip = html.unescape(re.sub(r"<[^>]+>", "", snip)).strip()
                        if len(clean_snip) > 20:
                            domain = extract_domain(actual_url)
                            results.append(
                                SearchResult(
                                    title=f"{domain} documentation / web article",
                                    url=actual_url,
                                    domain=domain,
                                    snippet=clean_snip,
                                    score=0.9,
                                )
                            )
        except Exception as e:
            logger.debug(f"DDG Web HTML search failed: {e}")

        return results[:limit]


class HybridSearchProvider(SearchProvider):
    """Intelligent multi-tier search provider that combines configured providers with DDG Web and Wikipedia."""

    def __init__(self, primary: SearchProvider):
        self.primary = primary
        self.ddg_web = DuckDuckGoWebSearchProvider()
        self.wiki_provider = WikipediaSearchProvider()
        self.ddg_instant = DuckDuckGoInstantProvider()

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        results: List[SearchResult] = []

        # 1. Try primary search provider (Tavily, Serper, etc.)
        try:
            primary_results = await self.primary.search(query=query, limit=limit)
            if primary_results:
                results.extend(primary_results)
        except Exception as e:
            logger.warning(f"Primary search failed: {e}. Falling back to DDG Web & Wikipedia.")

        # 2. Augment with DDG Web Search (fetches real technical documentation)
        try:
            ddg_results = await self.ddg_web.search(query=query, limit=limit)
            if ddg_results:
                results.extend(ddg_results)
        except Exception as e:
            logger.debug(f"DDG Web search failed: {e}")

        # 3. If fewer than 2 results found, augment with Wikipedia and DDG Instant
        if len(results) < 2:
            try:
                wiki_results = await self.wiki_provider.search(query=query, limit=limit)
                results.extend(wiki_results)
            except Exception as e:
                logger.debug(f"Wikipedia fallback failed: {e}")

            try:
                instant_results = await self.ddg_instant.search(query=query, limit=2)
                results.extend(instant_results)
            except Exception as e:
                logger.debug(f"DDG Instant fallback failed: {e}")

        # Deduplicate results by URL
        seen_urls = set()
        deduped: List[SearchResult] = []
        for r in results:
            if r.url not in seen_urls and len(r.snippet.strip()) > 15:
                seen_urls.add(r.url)
                deduped.append(r)

        # Sort by tier priority (High tier official docs first)
        deduped.sort(key=lambda s: 0 if classify_source_tier(s.domain) == SourceTier.HIGH else 1)
        return deduped[:limit]


def get_search_provider() -> SearchProvider:
    if settings.MOCK_MODE:
        return MockSearchProvider()

    if settings.SEARCH_PROVIDER == "tavily" and settings.TAVILY_API_KEY:
        primary = TavilySearchProvider()
    elif settings.SEARCH_PROVIDER == "serper" and settings.SERPER_API_KEY:
        primary = SerperSearchProvider()
    elif settings.SEARCH_PROVIDER == "wikipedia":
        primary = WikipediaSearchProvider()
    else:
        # Default robust fallback using DDG Web Search
        primary = DuckDuckGoWebSearchProvider()

    return HybridSearchProvider(primary)
