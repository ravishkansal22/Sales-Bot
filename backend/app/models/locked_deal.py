from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.product import Product


class LockedDeal(Base):
    """Stores locked negotiation deals in the procurement cart.

    Attributes:
        id: Unique identifier (UUID v4).
        customer_id: Foreign key reference to customers table.
        product_id: Foreign key reference to products table.
        quantity: Quantity of the product.
        negotiated_price: Negotiated unit price of the deal.
        concessions: Value-add concessions (e.g. support, warranty).
        strategy: Winning negotiation strategy used.
        confidence_score: Score rating the negotiation confidence.
        created_at: Creation timestamp.
        updated_at: Update timestamp.
    """

    __tablename__ = "locked_deals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    negotiated_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    concessions: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    strategy: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
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

    # Relationships
    customer: Mapped[Customer] = relationship()
    product: Mapped[Product] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<LockedDeal id={self.id!s} customer_id={self.customer_id!s} product_id={self.product_id!s}>"
