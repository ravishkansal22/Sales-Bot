"""Product resolver service.

Identifies products mentioned in natural language conversation turns using keyword extraction,
SQL matching, and difflib fuzzy scoring, with an LLM-based query extractor as a fallback.
"""

from __future__ import annotations

import difflib
import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.product_service import ProductService

if TYPE_CHECKING:
    from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Common English stop words in sales inquiries to filter out for keyword search
STOP_WORDS = {
    "i", "want", "to", "buy", "a", "an", "the", "looking", "for", "need", "please",
    "can", "you", "show", "me", "find", "search", "get", "product", "item", "we", "us",
    "our", "like", "would", "interested", "in", "about", "inquiring", "have", "any",
    "some", "affordable", "cheap", "expensive", "cost", "price", "negotiate", "deal"
}


class ProductResolver:
    """Fuzzy and keyword resolver for product queries."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        """Initialise resolver with optional LLM fallback.

        Args:
            llm: Optional LLM provider for query extraction fallback.
        """
        self._llm = llm

    async def resolve_products(
        self,
        message: str,
        db: AsyncSession,
    ) -> list[Product]:
        """Resolve a natural language query to matching catalog products.

        Flow:
        1. Tokenize message and extract search keywords.
        2. Query catalog via SQL ILIKE conditions.
        3. Sort and filter results using difflib matching ratios.
        4. If no results, fallback to LLM keyword extraction and retry query.

        Args:
            message: The customer chat message.
            db: Active database session.

        Returns:
            A list of up to 5 matching products, ordered by relevance.
        """
        # Clean and tokenize message
        clean_msg = message.replace(",", " ").replace(".", " ").replace("?", " ").replace("!", " ")
        words = [
            w.strip().lower()
            for w in clean_msg.split()
            if w.strip() and w.strip().lower() not in STOP_WORDS
        ]

        if words:
            query_str = " ".join(words)
            results = await ProductService.search_products(db, query_str, limit=30)

            if results:
                # Rank results using difflib sequence matching
                def score_match(prod: Product) -> float:
                    name_score = difflib.SequenceMatcher(None, query_str, prod.name.lower()).ratio()
                    cat_score = difflib.SequenceMatcher(None, query_str, prod.category.lower()).ratio()
                    return max(name_score, cat_score)

                # Sort descending by match score
                scored_results = [(prod, score_match(prod)) for prod in results]
                # Filter out poor matches (score <= 0.12)
                valid_results = [p for p, score in scored_results if score > 0.12]
                
                if valid_results:
                    valid_results.sort(key=score_match, reverse=True)
                    return valid_results[:5]

        # 4. Fallback to LLM extraction if deterministic matching failed and LLM is configured
        if self._llm:
            try:
                from pydantic import BaseModel, Field

                class SearchExtraction(BaseModel):
                    query: str = Field(..., description="Catalog search keywords (e.g. 'cricket bat')")
                    is_product_related: bool = Field(..., description="True if looking for products")

                system_prompt = (
                    "You are a product search optimizer. Analyze the user's message "
                    "and extract clean keywords for searching a product catalog. "
                    "Example: 'I would like to get a premium cricket bat ASAP' -> 'cricket bat'"
                )

                extraction = await self._llm.generate(
                    prompt=f"User Message: \"{message}\"",
                    system_prompt=system_prompt,
                    response_model=SearchExtraction,
                )

                if extraction.is_product_related and extraction.query.strip():
                    llm_query = extraction.query.strip()
                    llm_results = await ProductService.search_products(db, llm_query, limit=5)
                    if llm_results:
                        return llm_results
            except Exception as e:
                logger.error("LLM fallback product resolution failed: %s", e)

        return []
