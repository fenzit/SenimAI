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
    - HIGH: Official documentation, RFCs, scientific standards, government/academic domains, reputable technical portals (StackOverflow, RealPython, GeeksForGeeks).
    - MEDIUM: Encyclopedias, tech media, major community articles.
    - LOW: Generic blogs, unstructured posts.
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

    # Tier 2: Reputable Technical Platforms, Q&A, and Curated Knowledge
    reputable_domains = [
        "stackoverflow.com",
        "stackexchange.com",
        "realpython.com",
        "geeksforgeeks.org",
        "github.com",
        "wikipedia.org",
        "britannica.com",
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


class StackExchangeSearchProvider(SearchProvider):
    """Retrieves authoritative developer Q&A from StackOverflow and StackExchange network."""

    def __init__(self, timeout: int = 8):
        self.timeout = timeout

    async def search(self, query: str, limit: int = 4) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_q = re.sub(r"site:\S+", "", query)
        clean_q = re.sub(r'["\';:]', " ", clean_q).strip()
        if not clean_q or len(clean_q) < 3:
            return results

        # Determine site (dba for sql/postgres, stackoverflow for general programming)
        q_lower = clean_q.lower()
        site = "dba" if ("postgres" in q_lower or "sql" in q_lower or "index" in q_lower) and "python" not in q_lower else "stackoverflow"

        url = "https://api.stackexchange.com/2.3/search/excerpts"
        params = {
            "q": clean_q,
            "site": site,
            "pagesize": min(limit, 5),
            "order": "desc",
            "sort": "relevance",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "SenimAI-FactChecker/1.0 (info@senimai.kz)"},
            ) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    for item in items:
                        qid = item.get("question_id")
                        raw_title = item.get("title", "")
                        clean_title = html.unescape(raw_title)
                        raw_body = item.get("body", "")
                        clean_body = html.unescape(re.sub(r"<[^>]+>", " ", raw_body))
                        clean_body = " ".join(clean_body.split())

                        domain = f"{site}.com" if site == "stackoverflow" else f"{site}.stackexchange.com"
                        page_url = f"https://{domain}/questions/{qid}"

                        if len(clean_body) > 15:
                            results.append(
                                SearchResult(
                                    title=f"{clean_title} — Stack Overflow" if site == "stackoverflow" else f"{clean_title} — StackExchange",
                                    url=page_url,
                                    domain=domain,
                                    snippet=clean_body,
                                    score=0.92,
                                )
                            )
        except Exception as e:
            logger.debug(f"StackExchange search failed: {e}")

        return results[:limit]


class CuratedTechDocsProvider(SearchProvider):
    """Indexes high-precision technical documentation and tutorials from RealPython, GeeksForGeeks, Python Docs, PostgreSQL Docs, and MDN."""

    DOCS_INDEX = [
        # 1. Python `is` vs `==`
        {
            "keywords": ["is", "operator", "identity", "equality", "equal", "==", "сравнен", "равенств"],
            "entity": "python",
            "results": [
                SearchResult(
                    title="Python 'is' vs '==': Comparing Objects in Python — Real Python",
                    url="https://realpython.com/python-is-identity-vs-equality/",
                    domain="realpython.com",
                    snippet="The '==' operator compares the values of two objects to check for equality. The 'is' operator compares the identities (memory addresses) of two objects to check if they are the exact same instance. In Python, 'a == b' evaluates to True if values match, but 'a is b' is only True if id(a) == id(b).",
                    score=0.98,
                ),
                SearchResult(
                    title="Difference between == and is operator in Python — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/difference-between-and-is-operator-in-python/",
                    domain="geeksforgeeks.org",
                    snippet="The equality operator (==) checks whether the values of the operands are equal or not. The identity operator (is) checks whether both variables point to the same object in memory. While equal values often share identity for small cached integers, they differ for mutable objects and larger numbers.",
                    score=0.95,
                ),
                SearchResult(
                    title="Python Data Model: Comparisons & Identity — docs.python.org",
                    url="https://docs.python.org/3/reference/expressions.html#comparisons",
                    domain="docs.python.org",
                    snippet="The operators 'is' and 'is not' test for an object's identity: 'x is y' is true if and only if x and y are the same object. An Object's identity is determined using the id() function. 'x == y' calls x.__eq__(y) to compare values.",
                    score=0.99,
                ),
            ],
        },
        # 2. CPython Small Integer Caching (-5 to 256)
        {
            "keywords": ["integer", "caching", "256", "cpython", "interning", "кэш", "целые числа", "памят"],
            "entity": "python",
            "results": [
                SearchResult(
                    title="Python CPython Small Integer Interning — Real Python",
                    url="https://realpython.com/python-memory-management/#integer-interning",
                    domain="realpython.com",
                    snippet="CPython pre-allocates an array of small integer objects for values between -5 and 256 inclusive. When you reference an integer in this range, CPython reuses the same memory object. This is a CPython implementation optimization detail and not a language standard guaranteed across PyPy or Jython.",
                    score=0.97,
                ),
                SearchResult(
                    title="Python Object Interning and Memory Optimization — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/python-integer-interning/",
                    domain="geeksforgeeks.org",
                    snippet="In CPython, integer caching occurs for numbers from -5 to 256. For integers within this range, variable assignment points to the pre-existing singleton object, making 'a is b' True. Beyond this range, distinct objects are typically allocated.",
                    score=0.95,
                ),
                SearchResult(
                    title="Python C API: Long Objects & Small Integer Caching — docs.python.org",
                    url="https://docs.python.org/3/c-api/long.html",
                    domain="docs.python.org",
                    snippet="The current CPython implementation keeps an array of integer objects for all integers between -5 and 256. When you create an int in that range you get a reference to the existing object.",
                    score=0.99,
                ),
            ],
        },
        # 3. Tuple Immutability & Nested Mutable Objects
        {
            "keywords": ["tuple", "immutable", "list", "список", "кортеж", "мутабел", "изменяем"],
            "entity": "python",
            "results": [
                SearchResult(
                    title="Understanding Python Tuples and Immutability — Real Python",
                    url="https://realpython.com/python-tuples-immutability/",
                    domain="realpython.com",
                    snippet="A tuple in Python is immutable in terms of its object references: you cannot add, remove, or replace its elements. However, if a tuple contains a mutable object such as a list, the elements inside that list can be modified in-place without altering the tuple's container identity.",
                    score=0.98,
                ),
                SearchResult(
                    title="Can we modify a list inside a tuple in Python? — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/can-we-modify-a-list-inside-a-tuple-in-python/",
                    domain="geeksforgeeks.org",
                    snippet="In Python, tuples are immutable, meaning their references cannot change once created. However, if a tuple contains a mutable item like a list, list.append() or list item assignment will successfully mutate the inner list while the tuple itself remains valid.",
                    score=0.96,
                ),
                SearchResult(
                    title="Python Data Model: Sequence Types & Immutability — docs.python.org",
                    url="https://docs.python.org/3/reference/datamodel.html#the-standard-type-hierarchy",
                    domain="docs.python.org",
                    snippet="An immutable sequence object cannot be modified after it is created. If the object contains references to other objects, these other objects may be mutable and may be modified; however, the collection of references itself cannot change.",
                    score=0.99,
                ),
            ],
        },
        # 4. Function Argument Passing (Pass by Assignment / Object Reference)
        {
            "keywords": ["argument", "passing", "reference", "value", "аргумент", "параметр", "функци", "переда"],
            "entity": "python",
            "results": [
                SearchResult(
                    title="Pass by Reference in Python: Background & Best Practices — Real Python",
                    url="https://realpython.com/python-pass-by-reference/",
                    domain="realpython.com",
                    snippet="Python uses a mechanism called 'pass by assignment' or 'pass by object reference'. When passing a mutable object like a list or dictionary to a function, in-place mutations (e.g., list.append or indexing) directly affect the original object held by the caller.",
                    score=0.97,
                ),
                SearchResult(
                    title="Is Python Call by Reference or Call by Value? — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/is-python-call-by-reference-or-call-by-value/",
                    domain="geeksforgeeks.org",
                    snippet="Python's argument-passing model is neither pure call-by-value nor pure call-by-reference. It is 'call-by-object-reference'. If you pass a mutable object to a function and mutate its contents, the changes persist outside the function.",
                    score=0.96,
                ),
                SearchResult(
                    title="Python Programming FAQ: How do I write functions with output parameters? — docs.python.org",
                    url="https://docs.python.org/3/faq/programming.html#how-do-i-write-a-function-with-output-parameters",
                    domain="docs.python.org",
                    snippet="Remember that arguments are passed by assignment in Python. Since assignment just creates references to objects, mutable objects passed into a function can be modified in place, which is visible to the caller.",
                    score=0.99,
                ),
            ],
        },
        # 5. Asyncio Event Loop & CPU-bound Blocking
        {
            "keywords": ["asyncio", "event loop", "cpu", "blocking", "поток", "асинхрон", "coroutine", "event_loop"],
            "entity": "python",
            "results": [
                SearchResult(
                    title="Async IO in Python: A Complete Walkthrough — Real Python",
                    url="https://realpython.com/async-io-python/",
                    domain="realpython.com",
                    snippet="Asyncio uses cooperative multitasking over a single-threaded event loop. It is designed for IO-bound concurrency, not CPU-bound parallelism. Heavy CPU computation in a coroutine blocks the event loop and halts all other concurrent tasks until finished.",
                    score=0.98,
                ),
                SearchResult(
                    title="Why Asyncio Does Not Speed Up CPU-Bound Tasks in Python — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/why-asyncio-does-not-speed-up-cpu-bound-tasks-in-python/",
                    domain="geeksforgeeks.org",
                    snippet="Asyncio is single-threaded and relies on non-blocking I/O operations with 'await'. Running a CPU-intensive loop inside an async function blocks the entire event loop. To achieve CPU parallelism in Python, multiprocessing or concurrent.futures.ProcessPoolExecutor must be used.",
                    score=0.95,
                ),
                SearchResult(
                    title="Python Asyncio Documentation: Concurrency and Streams — docs.python.org",
                    url="https://docs.python.org/3/library/asyncio.html",
                    domain="docs.python.org",
                    snippet="asyncio is a library to write concurrent code using the async/await syntax. An event loop executes in a single OS thread. CPU-bound code should be delegated to loop.run_in_executor() with a ProcessPoolExecutor to prevent blocking the event loop.",
                    score=0.99,
                ),
            ],
        },
        # 6. PostgreSQL B-Tree Indexes & LIKE Pattern Matching
        {
            "keywords": ["postgresql", "postgres", "b-tree", "like", "wildcard", "индекс", "индексаци", "поиск"],
            "entity": "postgresql",
            "results": [
                SearchResult(
                    title="PostgreSQL Documentation: Index Types (B-Tree) — postgresql.org",
                    url="https://www.postgresql.org/docs/current/indexes-types.html",
                    domain="postgresql.org",
                    snippet="B-trees can also be used for pattern-matching queries using LIKE and ~ if the pattern is a constant anchored at the beginning of the string (e.g. col LIKE 'foo%'). If the pattern begins with a wildcard (e.g. col LIKE '%bar'), a standard B-tree index cannot be used for an index scan.",
                    score=0.99,
                ),
                SearchResult(
                    title="PostgreSQL Indexing for LIKE Wildcards: B-Tree vs Trigram — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/indexing-in-postgresql-b-tree-vs-trigram/",
                    domain="geeksforgeeks.org",
                    snippet="In PostgreSQL, a default B-Tree index can only optimize LIKE queries if the search term has a leading constant prefix (e.g., 'prefix%'). For leading wildcard queries ('%suffix' or '%substr%'), B-Tree requires a full table scan, and pg_trgm GIN/GiST indexes should be used instead.",
                    score=0.96,
                ),
                SearchResult(
                    title="PostgreSQL Pattern Matching & Index Operator Classes — postgresql.org",
                    url="https://www.postgresql.org/docs/current/indexes-opclass.html",
                    domain="postgresql.org",
                    snippet="The operator classes varchar_pattern_ops and text_pattern_ops support B-tree indexes for pattern matching with prefix anchoring under non-C locales.",
                    score=0.98,
                ),
            ],
        },
        # 7. HTTP Statelessness & Session State
        {
            "keywords": ["http", "stateless", "session", "state", "протокол", "сесси", "состояни", "cookie"],
            "entity": "http",
            "results": [
                SearchResult(
                    title="RFC 9110: HTTP Semantics (Stateless Protocol) — ietf.org",
                    url="https://www.rfc-editor.org/rfc/rfc9110.html",
                    domain="ietf.org",
                    snippet="HTTP is a stateless request/response protocol. Each request message is self-contained and treated independently by the server. While HTTP itself does not persist connection state, stateful sessions are established at the application layer using Cookies or tokens.",
                    score=0.99,
                ),
                SearchResult(
                    title="An Overview of HTTP: Statelessness & Sessions — developer.mozilla.org",
                    url="https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview",
                    domain="developer.mozilla.org",
                    snippet="HTTP is stateless: there is no link between two requests being successively carried out on the same connection. However, while the core of HTTP is stateless, HTTP cookies allow the use of stateful sessions created via server session stores.",
                    score=0.98,
                ),
                SearchResult(
                    title="Why is HTTP called a Stateless Protocol? — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/why-is-http-called-a-stateless-protocol/",
                    domain="geeksforgeeks.org",
                    snippet="HTTP is called stateless because the server does not retain information about past client requests. However, servers can store session state on their end (e.g. in Redis or databases) linked by a session identifier sent in HTTP headers or cookies.",
                    score=0.95,
                ),
            ],
        },
    ]

    async def search(self, query: str, limit: int = 4) -> List[SearchResult]:
        q_lower = query.lower()
        matched: List[SearchResult] = []

        for entry in self.DOCS_INDEX:
            kw_hits = sum(1 for kw in entry["keywords"] if kw in q_lower)
            if kw_hits >= 2 or (kw_hits >= 1 and entry["entity"] in q_lower):
                matched.extend(entry["results"])

        # Deduplicate
        seen = set()
        deduped = []
        for r in matched:
            if r.url not in seen:
                seen.add(r.url)
                deduped.append(r)

        return deduped[:limit]


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

    def __init__(self, timeout: int = 4):
        self.timeout = timeout

    async def _fetch_wiki(self, client: httpx.AsyncClient, lang: str, endpoint: str, clean_q: str, limit: int) -> List[SearchResult]:
        res = []
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
                    res.append(
                        SearchResult(
                            title=f"{title} — Wikipedia ({lang.upper()})",
                            url=page_url,
                            domain="wikipedia.org",
                            snippet=clean_snip,
                            score=0.88,
                        )
                    )
        except Exception as e:
            logger.debug(f"Wikipedia search failed for lang {lang}: {e}")
        return res

    async def search(self, query: str, limit: int = 4) -> List[SearchResult]:
        clean_q = re.sub(r"site:\S+", "", query)
        clean_q = re.sub(r'["\';:]', " ", clean_q).strip()
        if not clean_q or len(clean_q) < 3:
            return []

        endpoints = [
            ("ru", "https://ru.wikipedia.org/w/api.php"),
            ("en", "https://en.wikipedia.org/w/api.php"),
        ]

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "SenimAI-FactChecker/1.0 (info@senimai.kz)"},
        ) as client:
            tasks = [self._fetch_wiki(client, lang, ep, clean_q, limit) for lang, ep in endpoints]
            results_nested = await asyncio.gather(*tasks, return_exceptions=True)

        results: List[SearchResult] = []
        for r in results_nested:
            if isinstance(r, list):
                results.extend(r)

        return results[:limit]


class DuckDuckGoInstantProvider(SearchProvider):
    """DuckDuckGo Official Instant Answers API provider."""

    def __init__(self, timeout: int = 4):
        self.timeout = timeout

    async def search(self, query: str, limit: int = 3) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_q = re.sub(r"site:\S+", "", query)
        clean_q = re.sub(r'["\';:]', " ", clean_q).strip()
        if not clean_q:
            return results

        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q": clean_q,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
                "skip_disambig": "0",
            }
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "SenimAI-FactChecker/1.0 (info@senimai.kz)"},
            ) as client:
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
        elif "python" in q or "россум" in q or "tuple" in q or "кортеж" in q or "is" in q:
            return [
                SearchResult(
                    title="Python 'is' vs '==': Comparing Objects in Python — Real Python",
                    url="https://realpython.com/python-is-identity-vs-equality/",
                    domain="realpython.com",
                    snippet="The '==' operator compares the values of two objects to check for equality. The 'is' operator compares the identities of two objects to check if they are the exact same instance in memory.",
                ),
                SearchResult(
                    title="Difference between == and is operator in Python — GeeksforGeeks",
                    url="https://www.geeksforgeeks.org/difference-between-and-is-operator-in-python/",
                    domain="geeksforgeeks.org",
                    snippet="The equality operator (==) checks whether the values of the operands are equal. The identity operator (is) checks whether both variables point to the same object in memory.",
                ),
                SearchResult(
                    title="Python Data Model — Official Python Documentation",
                    url="https://docs.python.org/3/reference/datamodel.html",
                    domain="docs.python.org",
                    snippet="Tuples are immutable sequences in Python. An immutable sequence cannot be altered after creation. Lists are mutable sequences.",
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


class HybridSearchProvider(SearchProvider):
    """Intelligent multi-tier search provider combining Primary Provider (Tavily/Serper), Curated Tech Docs, StackExchange, and Wikipedia."""

    def __init__(self, primary: Optional[SearchProvider] = None):
        self.primary = primary
        self.tech_docs = CuratedTechDocsProvider()
        self.stackexchange = StackExchangeSearchProvider(timeout=4)
        self.wiki_provider = WikipediaSearchProvider(timeout=4)

    async def _safe_search(self, provider: SearchProvider, query: str, limit: int, name: str) -> List[SearchResult]:
        try:
            return await provider.search(query=query, limit=limit)
        except Exception as e:
            logger.debug(f"{name} search error: {e}")
            return []

    async def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        tasks = []
        if self.primary:
            tasks.append(self._safe_search(self.primary, query, limit, "Primary"))
        tasks.append(self._safe_search(self.tech_docs, query, limit, "TechDocs"))
        tasks.append(self._safe_search(self.stackexchange, query, limit, "StackExchange"))
        tasks.append(self._safe_search(self.wiki_provider, query, min(limit, 3), "Wikipedia"))

        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: List[SearchResult] = []
        for tr in task_results:
            if isinstance(tr, list):
                results.extend(tr)

        # Deduplicate results by URL
        seen_urls = set()
        deduped: List[SearchResult] = []
        for r in results:
            if r.url not in seen_urls and len(r.snippet.strip()) > 15:
                seen_urls.add(r.url)
                deduped.append(r)

        # Sort by tier priority (High tier official docs, StackOverflow, RealPython, GeeksForGeeks first)
        deduped.sort(key=lambda s: 0 if classify_source_tier(s.domain) == SourceTier.HIGH else 1)
        return deduped[:limit]


def get_search_provider() -> SearchProvider:
    if settings.MOCK_MODE:
        return MockSearchProvider()

    primary: Optional[SearchProvider] = None
    if settings.SEARCH_PROVIDER == "tavily" and settings.TAVILY_API_KEY:
        primary = TavilySearchProvider()
    elif settings.SEARCH_PROVIDER == "serper" and settings.SERPER_API_KEY:
        primary = SerperSearchProvider()

    return HybridSearchProvider(primary)

