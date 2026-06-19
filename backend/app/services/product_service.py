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
        """Fuzzy/text search products by name or category.

        Args:
            db: Active database session.
            query: Text query to search for.
            limit: Maximum number of search results to return.

        Returns:
            A list of matching Product records.
        """
        if not query or not query.strip():
            # Return popular products if search is empty
            result = await db.execute(
                select(Product)
                .order_by(Product.popularity_index.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

        terms = [t.strip() for t in query.split() if len(t.strip()) > 1]
        if not terms:
            terms = [query.strip()]

        conditions = []
        for term in terms:
            conditions.append(Product.name.ilike(f"%{term}%"))
            conditions.append(Product.category.ilike(f"%{term}%"))
            conditions.append(Product.description.ilike(f"%{term}%"))

        stmt = select(Product).where(or_(*conditions)).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

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
