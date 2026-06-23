"""Chat-related Pydantic schemas.

Defines request/response models for the chat endpoint, including
the :class:`ConversationAnalysis` that captures AI-extracted metadata
about each customer message.
"""

from __future__ import annotations

from typing import Any
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
    intent_type: str = Field(
        default="negotiation",
        description="Intent type: negotiation, product_discovery, etc.",
    )
    sub_intent: str | None = Field(
        default=None,
        description="Optional sub-intent for fine-grained routing, e.g. competitor_leverage",
    )
    requested_discount: float = Field(
        default=0.0,
        description="Parsed requested discount percent",
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
    deal_value: float | None = Field(default=None, description="Total deal value. Inferred if product_id is provided.")
    cost_basis: float | None = Field(default=None, description="Cost basis. Inferred if product_id is provided.")
    product_id: str | None = Field(default=None, description="UUID or external ID of product under negotiation")
    quantity: int = Field(default=1, ge=1, description="Quantity of products being negotiated")
    client_message_id: str | None = Field(default=None, description="Frontend-generated unique ID for message deduplication/merging")


from app.schemas.product import ProductSchema
from app.schemas.simulation import (  # noqa: E402
    DigitalTwinProfile,
    OptimizerResult,
    SimulationOutput,
)


class ChatResponse(BaseModel):
    """Response payload from the chat endpoint."""

    digital_twin: DigitalTwinProfile
    simulations: list[SimulationOutput]
    winner: OptimizerResult
    response: str = Field(..., description="Customer-facing reply")
    internal_reasoning: str = Field(
        ...,
        description="Internal chain-of-thought reasoning for auditing",
    )
    intent_type: str = Field(default="negotiation", description="Intent type")
    recommended_products: list[ProductSchema] | None = Field(default=None, description="Recommended products list")
    inventory_status: str | None = Field(default=None, description="Inventory state")
    near_minimum_price: bool = Field(default=False, description="Near min price floor")
    comparison_results: dict[str, Any] | None = Field(default=None, description="Comparison data if query is a comparison")
    client_message_id: str | None = Field(default=None, description="Frontend-generated unique ID for message deduplication/merging")
    assistant_message_id: str | None = Field(default=None, description="Backend-generated unique ID for assistant response")


class SelectProductRequest(BaseModel):
    customer_id: str = Field(..., description="UUID or external ID of the customer")
    product_id: str = Field(..., description="UUID or external ID of the product")
    quantity: int = Field(default=1, ge=1, description="Quantity of products")


ChatResponse.model_rebuild()
