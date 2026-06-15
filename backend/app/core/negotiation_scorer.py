from __future__ import annotations

import statistics
from collections.abc import Sequence

from app.schemas.simulation import (
    CustomerReaction,
    DigitalTwinProfile,
    FinancialMetrics,
)


class NegotiationScorer:
    """Score negotiation strategies using deterministic formulae."""

    @staticmethod
    def calculate_strategy_fit(
        twin: DigitalTwinProfile,
        strategy_name: str,
        offer_type: str,
        discount_percent: float,
        bundle_value: float,
    ) -> float:
        """Score how well a strategy aligns with the customer profile."""

        name_lower = strategy_name.lower().strip()

        if name_lower == "discount":
            score = (
                0.40 * twin.price_sensitivity
                + 0.25 * twin.urgency
                + 0.20 * (1.0 - twin.brand_loyalty)
                + 0.15 * twin.decision_speed
            )

        elif name_lower == "hardline":
            score = (
                0.35 * twin.brand_loyalty
                + 0.30 * (1.0 - twin.price_sensitivity)
                + 0.20 * twin.risk_aversion
                + 0.15 * (1.0 - twin.urgency)
            )

        elif name_lower == "bundle":
            score = (
                0.30 * (1.0 - twin.risk_aversion)
                + 0.25 * (1.0 - twin.price_sensitivity)
                + 0.25 * twin.brand_loyalty
                + 0.20 * twin.urgency
            )

        elif name_lower == "personalized":
            score = (
                0.25 * twin.price_sensitivity
                + 0.20 * twin.urgency
                + 0.20 * twin.brand_loyalty
                + 0.20 * (1.0 - twin.risk_aversion)
                + 0.15 * twin.decision_speed
            )

        else:
            score = (
                0.20 * twin.price_sensitivity
                + 0.20 * twin.urgency
                + 0.20 * twin.brand_loyalty
                + 0.20 * (1.0 - twin.risk_aversion)
                + 0.20 * twin.decision_speed
            )

        return max(0.0, min(score, 1.0))

    @staticmethod
    def calculate_close_probability(
        strategy_fit: float,
        twin: DigitalTwinProfile,
        financial_metrics: FinancialMetrics,
        customer_reaction: CustomerReaction | None = None,
    ) -> float:
        """Calculate probability of closing the deal."""

        base_component = strategy_fit * 0.50
        urgency_component = twin.urgency * 0.20
        speed_component = twin.decision_speed * 0.15
        margin_component = financial_metrics.gross_margin_retention * 0.15

        raw_probability = (
            base_component
            + urgency_component
            + speed_component
            + margin_component
        )

        if customer_reaction is not None:
            reaction_bonus = (
                customer_reaction.buying_intent_delta * 0.15
                + customer_reaction.trust_delta * 0.10
                - customer_reaction.objection_delta * 0.10
                + customer_reaction.engagement_delta * 0.05
            )
            raw_probability += reaction_bonus

        return max(0.0, min(round(raw_probability, 6), 1.0))

    @staticmethod
    def calculate_risk_score(
        discount_percent: float,
        bundle_value: float,
        deal_value: float,
        financial_metrics: FinancialMetrics,
    ) -> float:
        """Assess risk of the deal becoming unprofitable."""

        if deal_value <= 0:
            return 1.0

        discount_risk = (
            min(max(discount_percent, 0.0), 100.0) / 100.0
        ) * 0.35

        bundle_risk = min(bundle_value / deal_value, 1.0) * 0.20
        leakage_risk = financial_metrics.contract_leakage * 0.30
        margin_risk = (1.0 - financial_metrics.gross_margin_retention) * 0.15

        raw = discount_risk + bundle_risk + leakage_risk + margin_risk

        return max(0.0, min(round(raw, 6), 1.0))

    @staticmethod
    def calculate_confidence_score(
        rollout_strategy_fits: Sequence[float],
        rollout_risk_scores: Sequence[float],
    ) -> float:
        """Measure consistency across simulation rollouts."""

        if len(rollout_strategy_fits) < 2 or len(rollout_risk_scores) < 2:
            return 1.0

        var_fit = statistics.pvariance(rollout_strategy_fits)
        var_risk = statistics.pvariance(rollout_risk_scores)

        avg_var = (var_fit + var_risk) / 2.0
        max_variance = 0.25
        normalized_var = avg_var / max_variance
        confidence = 1.0 - normalized_var

        return max(0.0, min(round(confidence, 6), 1.0))