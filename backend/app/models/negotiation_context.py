from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class NegotiationContext(Base):
    """Stores the persistent negotiation state between messages for active negotiations."""

    __tablename__ = "negotiation_contexts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One active negotiation per customer
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
    current_offer: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    requested_discount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    current_strategy: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    negotiation_stage: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="initiated",
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    context_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    # Relationships
    customer = relationship("Customer")
    product = relationship("Product")

    def __repr__(self) -> str:
        return f"<NegotiationContext customer_id={self.customer_id!s} product_id={self.product_id!s}>"
