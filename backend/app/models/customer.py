"""Customer and DigitalTwinSnapshot ORM models.

Defines the ``customers`` table for tracking customers and the
``digital_twin_snapshots`` table for point-in-time behavioural profiles
used by the simulation engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.conversation import Conversation

from app.db.base import Base


class Customer(Base):
    """A customer record.

    Attributes:
        id: Unique identifier (UUID v4).
        name: Display name of the customer.
        email: Optional email address.
        metadata_: Arbitrary JSON metadata (column name ``metadata``).
        created_at: Row-creation timestamp (server-side default).
        updated_at: Timestamp of the most recent update.
        twin_snapshots: Related :class:`DigitalTwinSnapshot` records.
        conversations: Related :class:`Conversation` records.
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    twin_snapshots: Mapped[list[DigitalTwinSnapshot]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id!s} name={self.name!r}>"


class DigitalTwinSnapshot(Base):
    """A point-in-time snapshot of a customer's behavioural profile.

    Each dimension is a normalised float in the range ``[0, 1]``.

    Attributes:
        id: Unique identifier (UUID v4).
        customer_id: Foreign key to :class:`Customer`.
        price_sensitivity: How sensitive the customer is to pricing.
        urgency: How urgently the customer needs a resolution.
        risk_aversion: Degree of risk-averse behaviour.
        brand_loyalty: Strength of loyalty to the brand.
        decision_speed: How quickly the customer reaches a decision.
        created_at: Row-creation timestamp (server-side default).
        customer: Parent :class:`Customer` relationship.
    """

    __tablename__ = "digital_twin_snapshots"

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
    price_sensitivity: Mapped[float] = mapped_column(Float, nullable=False)
    urgency: Mapped[float] = mapped_column(Float, nullable=False)
    risk_aversion: Mapped[float] = mapped_column(Float, nullable=False)
    brand_loyalty: Mapped[float] = mapped_column(Float, nullable=False)
    decision_speed: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    customer: Mapped[Customer] = relationship(back_populates="twin_snapshots")

    def __repr__(self) -> str:
        return (
            f"<DigitalTwinSnapshot id={self.id!s} "
            f"customer_id={self.customer_id!s}>"
        )
