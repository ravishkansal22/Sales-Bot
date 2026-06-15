"""Conversation ORM model.

Stores individual messages in a customer conversation, along with
optional AI-generated analysis metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.simulation import SimulationResult

from app.db.base import Base


class Conversation(Base):
    """A single message within a customer conversation.

    Attributes:
        id: Unique identifier (UUID v4).
        customer_id: Foreign key to :class:`Customer`.
        message: The textual content of the message.
        role: Either ``"customer"`` or ``"assistant"``.
        analysis: Optional JSON blob storing a serialised
            :class:`ConversationAnalysis`.
        created_at: Row-creation timestamp (server-side default).
        customer: Parent :class:`Customer` relationship.
        simulation_results: Related :class:`SimulationResult` records.
    """

    __tablename__ = "conversations"

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
    message: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Either 'customer' or 'assistant'",
    )
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    customer: Mapped[Customer] = relationship(
        back_populates="conversations",
    )
    simulation_results: Mapped[list[SimulationResult]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id!s} role={self.role!r} "
            f"customer_id={self.customer_id!s}>"
        )
