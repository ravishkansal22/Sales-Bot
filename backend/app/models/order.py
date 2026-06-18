"""Order ORM model.

Defines the ``orders`` table for tracking customer purchase history.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.product import Product


class Order(Base):
    """An order transaction record.

    Attributes:
        id: Unique identifier (UUID v4).
        customer_id: ForeignKey reference to Customer.
        product_id: ForeignKey reference to Product.
        purchase_price: Price paid by the customer for this order.
        purchase_date: Timestamp of when the order was placed.
        payment_method: Method used for payment (e.g. Credit Card, UPI).
        delivery_status: Delivery outcome (e.g. Delivered, Returned, Delayed).
        customer: Relationship to the Customer.
        product: Relationship to the Product.
    """

    __tablename__ = "orders"

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
        index=True,
    )
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    purchase_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    payment_method: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    customer: Mapped[Customer] = relationship(
        back_populates="orders",
    )
    product: Mapped[Product] = relationship(
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id!s} customer_id={self.customer_id!s} "
            f"product_id={self.product_id!s}>"
        )
