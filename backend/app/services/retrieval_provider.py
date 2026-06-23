import logging
from abc import ABC, abstractmethod
import httpx
from app.services.llm_service import settings

logger = logging.getLogger(__name__)

class RetrievalProvider(ABC):
    @abstractmethod
    async def retrieve(self, query: str) -> list[str]:
        """Perform search and return a list of text document/snippets."""
        pass

class TavilyProvider(RetrievalProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.url = "https://api.tavily.com/search"

    async def retrieve(self, query: str) -> list[str]:
        if not self.api_key:
            logger.warning("Tavily API key not set. Skipping retrieval.")
            return []
        
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                }
                res = await client.post(self.url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    snippets = [r.get("content", "") for r in results if r.get("content")]
                    logger.info("Tavily search retrieved %d results for query: %s", len(snippets), query)
                    return snippets
                else:
                    logger.error("Tavily search failed with status %d: %s", res.status_code, res.text)
        except Exception as e:
            logger.error("Tavily search error: %s", e)
            
        return []

class BraveSearchProvider(RetrievalProvider):
    async def retrieve(self, query: str) -> list[str]:
        logger.warning("BraveSearchProvider placeholder called. Returning empty.")
        return []

class SerpApiProvider(RetrievalProvider):
    async def retrieve(self, query: str) -> list[str]:
        logger.warning("SerpApiProvider placeholder called. Returning empty.")
        return []

class FirecrawlProvider(RetrievalProvider):
    async def retrieve(self, query: str) -> list[str]:
        logger.warning("FirecrawlProvider placeholder called. Returning empty.")
        return []

def get_retrieval_provider() -> RetrievalProvider:
    prov_name = settings.RETRIEVAL_PROVIDER.lower().strip()
    if prov_name == "tavily":
        return TavilyProvider(api_key=settings.TAVILY_API_KEY)
    elif prov_name == "brave":
        return BraveSearchProvider()
    elif prov_name == "serpapi":
        return SerpApiProvider()
    elif prov_name == "firecrawl":
        return FirecrawlProvider()
    else:
        logger.warning("Unknown retrieval provider %s. Using Tavily.", prov_name)
        return TavilyProvider(api_key=settings.TAVILY_API_KEY)
