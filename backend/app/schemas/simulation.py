"""Simulation-related Pydantic schemas.

Covers everything from digital-twin profiles and individual rollout
results through to the optimizer's final ranking, plus the request
/ response wrappers for the simulation endpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from enum import Enum
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.schemas.chat import ConversationAnalysis



class DigitalTwinProfile(BaseModel):
    """Normalised behavioural profile of a customer.

    All dimensions are floats clamped to ``[0, 1]``.

    Attributes:
        price_sensitivity: Sensitivity to pricing changes.
        urgency: Perceived urgency to close the deal.
        risk_aversion: Tendency to avoid risky options.
        brand_loyalty: Strength of brand affinity.
        decision_speed: How quickly the customer decides.
    """

    price_sensitivity: float = Field(
        ..., ge=0, le=1, description="Price sensitivity score"
    )
    urgency: float = Field(..., ge=0, le=1, description="Urgency score")
    risk_aversion: float = Field(
        ..., ge=0, le=1, description="Risk-aversion score"
    )
    brand_loyalty: float = Field(
        ..., ge=0, le=1, description="Brand loyalty score"
    )
    decision_speed: float = Field(
        ..., ge=0, le=1, description="Decision-speed score"
    )

class CustomerState(BaseModel):
    """Dynamic customer state during simulations.

    Unlike DigitalTwinProfile (stable traits), this represents
    negotiation state that can evolve throughout a simulation.
    """

    trust_level: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Customer trust in our company"
    )

    buying_intent: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Likelihood customer wants to buy"
    )

    engagement_level: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="How actively customer engages"
    )

    objection_intensity: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Strength of current objections"
    )
class CustomerReaction(BaseModel):
    """Simulated customer reaction to a strategy."""

    simulated_response: str = Field(
        ...,
        description="Predicted customer response"
    )

    trust_delta: float = Field(
        ...,
        ge=-1,
        le=1,
        description="Change in trust level"
    )

    buying_intent_delta: float = Field(
        ...,
        ge=-1,
        le=1,
        description="Change in buying intent"
    )

    engagement_delta: float = Field(
        ...,
        ge=-1,
        le=1,
        description="Change in engagement"
    )

    objection_delta: float = Field(
        ...,
        ge=-1,
        le=1,
        description="Change in objection intensity"
    )

class SimulationRollout(BaseModel):
    """Result of a single Monte-Carlo rollout."""

    rollout_id: str = Field(..., description="Rollout identifier")

    reasoning: str = Field(
        ...,
        description="Reasoning trace for this rollout"
    )

    strategy_fit: float = Field(
        ...,
        ge=0,
        le=1,
        description="Strategy-fit score"
    )

    risk_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="Risk score for this rollout"
    )

    customer_reaction: CustomerReaction | None = Field(
        default=None,
        description="Predicted customer reaction"
    )

    timeline_events: list[str] = Field(
        default_factory=list,
        description="Simulation timeline events"
    )


class LLMStrategyOutput(BaseModel):
    """Raw strategy output from the LLM — no business metrics.

    This is what the LLM generates; financial metrics are computed
    downstream by the simulation engine.

    Attributes:
        strategy_name: Human-readable name for the strategy.
        offer_type: Category of offer – ``discount``, ``hardline``,
            ``bundle``, or ``personalized``.
        discount_percent: Proposed discount ``[0, 100]``.
        bundle_value: Monetary value of bundled extras ``>= 0``.
        reasoning: LLM justification for the strategy.
    """

    strategy_name: str = Field(..., description="Human-readable strategy name")
    offer_type: str = Field(
        ...,
        description="Offer category: discount, hardline, bundle, personalized",
    )
    discount_percent: float = Field(
        ..., ge=0, le=100, description="Discount percentage"
    )
    bundle_value: float = Field(
        ..., ge=0, description="Value of bundled extras"
    )
    reasoning: str = Field(..., description="LLM justification for the strategy")


class SimulationOutput(BaseModel):
    """Aggregated simulation result for a single strategy.

    Combines the LLM's strategy definition with the averaged
    metrics from all Monte-Carlo rollouts.

    Attributes:
        strategy_name: Human-readable strategy name.
        offer_type: Offer category.
        discount_percent: Proposed discount percentage.
        bundle_value: Bundled extras value.
        reasoning: LLM justification.
        rollouts: Individual rollout results.
        average_close_probability: Mean close probability across
            rollouts.
        average_risk_score: Mean risk score across rollouts.
        average_expected_profit: Mean expected profit.
        average_expected_value: Mean expected value / revenue.
    """

    strategy_name: str
    offer_type: str
    discount_percent: float
    bundle_value: float
    reasoning: str
    rollouts: list[SimulationRollout]
    average_close_probability: float = Field(
        ..., description="Mean close probability"
    )
    average_risk_score: float = Field(
        ..., description="Mean risk score"
    )
    average_expected_profit: float = Field(
        ..., description="Mean expected profit"
    )
    average_gross_margin_retention: float = Field(
        default=0.0,
        description="Mean gross margin retention"
    )
    average_expected_value: float = Field(
        ..., description="Mean expected value / revenue"
    )


class FinancialMetrics(BaseModel):
    """Financial impact metrics for a strategy.

    Attributes:
        gross_margin_retention: Fraction of gross margin retained.
        revenue_impact: Absolute revenue impact.
        profit_impact: Absolute profit impact.
        contract_leakage: Estimated contract leakage.
    """

    gross_margin_retention: float = Field(
        ..., description="Fraction of gross margin retained"
    )
    revenue_impact: float = Field(..., description="Absolute revenue impact")
    profit_impact: float = Field(..., description="Absolute profit impact")
    contract_leakage: float = Field(
        ..., description="Estimated contract leakage"
    )
    minimum_price_closeness: float = Field(
        default=0.0, description="Closeness to minimum price threshold (0 to 1)"
    )

class OptimizationMode(str, Enum):
    """Business objective used by the strategy optimizer."""

    BALANCED = "balanced"
    MAX_PROFIT = "max_profit"
    MAX_MARGIN = "max_margin"
    MAX_CLOSE_RATE = "max_close_rate"

class OptimizerResult(BaseModel):
    """The optimizer's final strategy selection.

    Attributes:
        winning_strategy: Name of the selected strategy.
        score: Composite score assigned by the optimizer.
        optimizer_reasoning: Explanation for the selection.
        winning_factors: Key factors that drove the decision.
        risk_score: Overall risk score of the winning strategy.
        confidence_score: Optimizer's confidence in the pick.
        all_rankings: Full ranked list of all strategies with
            their scores (list of dicts).
    """

    winning_strategy: str = Field(
        ..., description="Name of the winning strategy"
    )
    score: float = Field(..., description="Composite optimizer score")
    optimization_mode: OptimizationMode = Field(
        ...,
        description="Business objective used for optimization"
    )
    optimizer_reasoning: str = Field(
        ..., description="Explanation for the selection"
    )
    winning_factors: list[str] = Field(
        ..., description="Factors that drove the decision"
    )
    risk_score: float = Field(
        ..., description="Risk score of the winning strategy"
    )
    confidence_score: float = Field(
        ..., description="Optimizer confidence in the selection"
    )
    all_rankings: list[dict[str, Any]] = Field(
        ..., description="Full ranked list of all strategies"
    )


class SimulateRequest(BaseModel):
    """Request payload for the standalone simulation endpoint.

    Attributes:
        message: Customer message to simulate against.
        customer_id: UUID of the customer.
        deal_value: Total deal value (must be > 0).
        cost_basis: Cost basis for margin calculations (must be > 0).
    """

    message: str = Field(..., min_length=1, description="Customer message text")
    customer_id: str = Field(..., description="UUID of the customer")
    deal_value: float | None = Field(default=None, description="Total deal value. Inferred if product_id is provided.")
    cost_basis: float | None = Field(default=None, description="Cost basis. Inferred if product_id is provided.")
    product_id: str | None = Field(default=None, description="UUID or external ID of product under negotiation")
    quantity: int = Field(default=1, ge=1, description="Quantity of products being negotiated")
    
    optimization_mode: OptimizationMode = Field(
        default=OptimizationMode.BALANCED,
        description="Business objective used for optimization",
    )

class SimulateResponse(BaseModel):
    """Response payload from the standalone simulation endpoint.

    Attributes:
        digital_twin: Customer's behavioural profile.
        analysis: Conversation analysis of the input message.
        simulations: All strategy simulation outputs.
        winner: The optimizer's selected best strategy.
    """

    digital_twin: DigitalTwinProfile
    analysis: ConversationAnalysis  # Resolved at runtime via model_rebuild
    simulations: list[SimulationOutput]
    winner: OptimizerResult


# Deferred import to avoid circular dependency — rebuild model after
# ConversationAnalysis is importable.
def _rebuild_simulate_response() -> None:
    """Rebuild SimulateResponse to resolve forward references."""
    from app.schemas.chat import ConversationAnalysis
    globals()["ConversationAnalysis"] = ConversationAnalysis
    SimulateResponse.model_rebuild()


_rebuild_simulate_response()
