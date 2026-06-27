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
        logger.info("[DIAGNOSTICS - PRODUCT RESOLUTION] Resolving query: '%s'", message)
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
            
            # Rank results using the custom scoring formula
            def score_match(prod: Product) -> float:
                # Fuzzy similarity on name and description
                name_score = difflib.SequenceMatcher(None, query_str, prod.name.lower()).ratio()
                desc_score = 0.0
                if prod.description:
                    # Check sub-sequence or exact word matching in description
                    desc_lower = prod.description.lower()
                    matching_words = [w for w in words if w in desc_lower]
                    if words:
                        desc_score = len(matching_words) / len(words)
                fuzzy_similarity = max(name_score, desc_score)

                # Category match
                cat_score = difflib.SequenceMatcher(None, query_str, prod.category.lower()).ratio()
                cat_words = set(prod.category.lower().split())
                query_words = set(words)
                if cat_words.intersection(query_words):
                    cat_score = max(cat_score, 1.0)
                category_match = cat_score

                # Popularity index (0-5.0 range, default 0)
                pop_val = getattr(prod, "popularity_index", 0.0) or 0.0
                popularity_index = min(5.0, max(0.0, float(pop_val)))
                normalized_popularity = popularity_index / 5.0

                # 0.5 * fuzzy_similarity + 0.3 * category_match + 0.2 * popularity_index
                return (
                    0.5 * fuzzy_similarity +
                    0.3 * category_match +
                    0.2 * normalized_popularity
                )

            results = await ProductService.search_products(db, query_str, limit=50)

            if results:
                # Sort descending by match score
                scored_results = [(prod, score_match(prod)) for prod in results]
                # Filter out poor matches
                valid_results = [p for p, score in scored_results if score > 0.05]
                
                if valid_results:
                    # Sort by the score_match return value
                    valid_results.sort(key=score_match, reverse=True)
                    resolved = valid_results[:10]
                    logger.info(
                        "[DIAGNOSTICS - PRODUCT RESOLUTION] Primary search resolved: %s",
                        [p.name for p in resolved]
                    )
                    return resolved

        # 4. Fallback to deterministic token-by-token search if the combined search yields nothing.
        # This is a highly robust deterministic alternative that makes 0 LLM calls.
        token_results = []
        for word in words:
            try:
                word_results = await ProductService.search_products(db, word, limit=5)
                token_results.extend(word_results)
            except Exception:
                break
        
        if token_results:
            seen_ids = set()
            unique_results = []
            for prod in token_results:
                if prod.id not in seen_ids:
                    seen_ids.add(prod.id)
                    unique_results.append(prod)
            
            scored_results = [(prod, score_match(prod)) for prod in unique_results]
            valid_results = [p for p, score in scored_results if score > 0.05]
            if valid_results:
                valid_results.sort(key=score_match, reverse=True)
                resolved = valid_results[:10]
                logger.info(
                    "[DIAGNOSTICS - PRODUCT RESOLUTION] Fallback token search resolved: %s",
                    [p.name for p in resolved]
                )
                return resolved

        logger.info("[DIAGNOSTICS - PRODUCT RESOLUTION] Failed to resolve any products.")
        return []
