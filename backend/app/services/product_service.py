"""Product catalog service.

Provides services for retrieving products, searching the catalog, looking up inventory levels,
and fetching pricing constraints.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


class ProductService:
    """Service class for product catalog operations."""

    @staticmethod
    async def get_product_by_id(
        db: AsyncSession,
        product_id: uuid.UUID,
    ) -> Product | None:
        """Retrieve a product by its database UUID.

        Args:
            db: Active database session.
            product_id: Product's UUID.

        Returns:
            The Product ORM instance, or None if not found.
        """
        result = await db.execute(select(Product).where(Product.id == product_id))
        return result.scalars().first()

    @staticmethod
    async def get_product_by_external_id(
        db: AsyncSession,
        external_id: str,
    ) -> Product | None:
        """Retrieve a product by its external catalog product ID (e.g. 'P1000').

        Args:
            db: Active database session.
            external_id: The external product ID string.

        Returns:
            The Product ORM instance, or None if not found.
        """
        result = await db.execute(
            select(Product).where(Product.external_product_id == external_id)
        )
        return result.scalars().first()

    @staticmethod
    async def search_products(
        db: AsyncSession,
        query: str,
        limit: int = 20,
    ) -> list[Product]:
        """Fuzzy/text search products by name or category, with category-sticky logic and deduplication."""
        if not query or not query.strip():
            # Return popular products if search is empty, but deduplicate them
            result = await db.execute(
                select(Product)
                .order_by(Product.popularity_index.desc())
                .limit(limit * 3)
            )
            products = list(result.scalars().all())
            seen_names = set()
            deduped = []
            for p in products:
                name_lower = p.name.strip().lower()
                if name_lower not in seen_names:
                    seen_names.add(name_lower)
                    deduped.append(p)
            return deduped[:limit]

        terms = [t.strip().lower() for t in query.split() if len(t.strip()) > 1]
        if not terms:
            terms = [query.strip().lower()]

        conditions = []
        for term in terms:
            conditions.append(Product.name.ilike(f"%{term}%"))
            conditions.append(Product.category.ilike(f"%{term}%"))
            conditions.append(Product.description.ilike(f"%{term}%"))

        # Fetch a larger pool of raw matches to allow scoring, deduplication, and category stickiness
        stmt = select(Product).where(or_(*conditions)).limit(200)
        result = await db.execute(stmt)
        raw_products = list(result.scalars().all())

        if not raw_products:
            return []

        # Python-based generic ranking and scoring
        def score_product(p: Product) -> float:
            score = 0.0
            p_name_lower = p.name.lower()
            p_cat_lower = p.category.lower()
            p_desc_lower = (p.description or "").lower()
            for term in terms:
                # Direct word matches in name have high weight
                if term in p_name_lower:
                    score += 10.0
                # Matches in category
                if term in p_cat_lower:
                    score += 5.0
                # Matches in description
                if term in p_desc_lower:
                    score += 1.0
            return score

        scored_products = [(p, score_product(p)) for p in raw_products]
        scored_products.sort(key=lambda x: x[1], reverse=True)

        # Deduplicate by lowercase product name to resolve duplicate listing products
        seen_names = set()
        unique_scored = []
        for p, score in scored_products:
            p_name = p.name.strip().lower()
            if p_name not in seen_names:
                seen_names.add(p_name)
                unique_scored.append((p, score))

        if not unique_scored:
            return []

        # Category stickiness: infer category from the top ranked result
        top_product, top_score = unique_scored[0]
        final_products = [x[0] for x in unique_scored]
        
        if top_score > 0:
            target_category = top_product.category
            # Filter all search results to only return products matching the target category
            final_products = [p for p in final_products if p.category == target_category]

        return final_products[:limit]

    @staticmethod
    async def get_inventory(
        db: AsyncSession,
        product_id: uuid.UUID,
    ) -> int:
        """Lookup available stock level for a product.

        Args:
            db: Active database session.
            product_id: Product database UUID.

        Returns:
            Available stock quantity (integer), or 0 if product doesn't exist.
        """
        product = await ProductService.get_product_by_id(db, product_id)
        return product.stock_quantity if product else 0

    @staticmethod
    async def get_pricing(
        db: AsyncSession,
        product_id: uuid.UUID,
    ) -> dict[str, float]:
        """Fetch pricing and margin parameters for a product.

        Args:
            db: Active database session.
            product_id: Product database UUID.

        Returns:
            A dict containing:
                - selling_price
                - cost_price
                - minimum_price
                - target_margin
        """
        product = await ProductService.get_product_by_id(db, product_id)
        if not product:
            return {
                "selling_price": 0.0,
                "cost_price": 0.0,
                "minimum_price": 0.0,
                "target_margin": 0.0,
            }
        return {
            "selling_price": product.selling_price,
            "cost_price": product.cost_price,
            "minimum_price": product.minimum_price,
            "target_margin": product.target_margin,
        }
