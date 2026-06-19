from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product


class ProductSpecification(Base):
    """Stores key-value specifications for catalog products.

    Attributes:
        id: Unique identifier (UUID v4).
        product_id: Foreign key reference to products table.
        specification_name: Label of the specification (e.g. Warranty).
        specification_value: Value of the specification (e.g. 2 Years).
        created_at: Creation timestamp.
    """

    __tablename__ = "product_specifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    specification_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )
    specification_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped[Product] = relationship(back_populates="specifications")

    def __repr__(self) -> str:
        return f"<ProductSpecification id={self.id!s} product_id={self.product_id!s} name={self.specification_name!r}>"
