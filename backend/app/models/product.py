"""Product ORM model.

Defines the ``products`` table for storing the product catalog with details
about description, pricing, target margins, inventory levels, popularity, and return rate.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    """A product record.

    Attributes:
        id: Unique identifier (UUID v4).
        external_product_id: Product ID from external CSV catalog.
        name: Product name.
        category: Product category (e.g. Apparel, Books).
        description: Description of the product.
        selling_price: Retail selling price.
        cost_price: Internal cost price.
        minimum_price: Minimum allowed selling price for negotiation.
        target_margin: Target profit margin percent.
        stock_quantity: Available stock quantity.
        popularity_index: Product popularity score.
        return_rate: Return rate percent.
        created_at: Row-creation timestamp.
        updated_at: Row-update timestamp.
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    external_product_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False)
    minimum_price: Mapped[float] = mapped_column(Float, nullable=False)
    target_margin: Mapped[float] = mapped_column(Float, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    popularity_index: Mapped[float] = mapped_column(Float, nullable=False)
    return_rate: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id!s} name={self.name!r} ext_id={self.external_product_id!r}>"
