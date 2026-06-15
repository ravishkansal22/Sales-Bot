"""Chat-related Pydantic schemas.

Defines request/response models for the chat endpoint, including
the :class:`ConversationAnalysis` that captures AI-extracted metadata
about each customer message.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationAnalysis(BaseModel):
    """AI-extracted analysis of a single customer message.

    Attributes:
        objection_type: The category of objection raised by the customer.
            One of ``price``, ``feature``, ``competitor``, ``timing``,
            or ``authority``.
        negotiation_intent: Free-text description of the customer's
            underlying negotiation goal.
        urgency: Normalised urgency score in ``[0, 1]``.
        sentiment: Overall sentiment – ``positive``, ``neutral``, or
            ``negative``.
        stage: Current position in the sales funnel – ``awareness``,
            ``consideration``, ``decision``, or ``retention``.
    """

    objection_type: str = Field(
        ...,
        description="Objection category: price, feature, competitor, timing, authority",
    )
    negotiation_intent: str = Field(
        ...,
        description="Free-text description of the customer's negotiation goal",
    )
    urgency: float = Field(
        ...,
        ge=0,
        le=1,
        description="Normalised urgency score",
    )
    sentiment: str = Field(
        ...,
        description="Overall sentiment: positive, neutral, negative",
    )
    stage: str = Field(
        ...,
        description="Sales funnel stage: awareness, consideration, decision, retention",
    )

class ChatRequest(BaseModel):
    """Incoming payload for the chat endpoint.

    Attributes:
        message: The customer's message text.
        customer_id: Unique identifier for the customer (UUID string).
        deal_value: Total value of the deal in currency units
            (must be > 0).
        cost_basis: Cost basis for margin calculations
            (must be > 0).
    """

    message: str = Field(..., min_length=1, description="Customer message text")
    customer_id: str = Field(..., description="UUID of the customer")
    deal_value: float = Field(..., gt=0, description="Total deal value")
    cost_basis: float = Field(..., gt=0, description="Cost basis for margin calculations")


from app.schemas.simulation import (  # noqa: E402
    DigitalTwinProfile,
    OptimizerResult,
    SimulationOutput,
)


class ChatResponse(BaseModel):
    """Response payload from the chat endpoint.

    Bundles together the digital twin profile, all simulation outputs,
    the optimizer's winning pick, the customer-facing response, and
    the internal chain-of-thought reasoning.

    Attributes:
        digital_twin: Behavioural profile of the customer.
        simulations: Full list of strategy simulations.
        winner: The optimizer's selected best strategy.
        response: The generated customer-facing reply.
        internal_reasoning: Internal chain-of-thought for auditing.
    """

    digital_twin: DigitalTwinProfile
    simulations: list[SimulationOutput]
    winner: OptimizerResult
    response: str = Field(..., description="Customer-facing reply")
    internal_reasoning: str = Field(
        ...,
        description="Internal chain-of-thought reasoning for auditing",
    )
