"""SimulationResult ORM model.

Captures the output of a Monte-Carlo-style strategy simulation run,
including per-rollout data, financial metrics, and the optimizer's
ranking decision.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.customer import Customer

from app.db.base import Base


class SimulationResult(Base):
    """Persisted result of a single strategy simulation.

    Attributes:
        id: Unique identifier (UUID v4).
        conversation_id: Foreign key to :class:`Conversation`.
        customer_id: Foreign key to :class:`Customer`.
        strategy_name: Human-readable strategy label.
        offer_type: Category of the offer (discount, bundle, etc.).
        discount_percent: Discount offered as a percentage ``[0–100]``.
        bundle_value: Monetary value of any bundled extras.
        reasoning: LLM-generated justification for this strategy.
        close_probability: Estimated probability of closing the deal.
        expected_profit: Expected profit in currency units.
        expected_value: Expected revenue / value metric.
        risk_score: Composite risk score ``[0–1]``.
        confidence_score: Model confidence in the prediction ``[0–1]``.
        optimizer_reasoning: Explanation from the optimizer about
            why this strategy was or wasn't selected.
        winning_factors: JSON list of factors that contributed to
            this strategy's ranking.
        rollout_count: Number of Monte-Carlo rollouts executed.
        rollouts: JSON list of individual rollout result dicts.
        is_winner: Whether the optimizer selected this strategy.
        created_at: Row-creation timestamp (server-side default).
        conversation: Parent :class:`Conversation` relationship.
        customer: Parent :class:`Customer` relationship.
    """

    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    offer_type: Mapped[str] = mapped_column(String(100), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False)
    bundle_value: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    close_probability: Mapped[float] = mapped_column(Float, nullable=False)
    expected_profit: Mapped[float] = mapped_column(Float, nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    optimizer_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    winning_factors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    rollout_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rollouts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        back_populates="simulation_results",
    )
    customer: Mapped[Customer] = relationship(
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<SimulationResult id={self.id!s} "
            f"strategy={self.strategy_name!r} winner={self.is_winner}>"
        )
