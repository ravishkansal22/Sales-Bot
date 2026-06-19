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
        from app.core.config_layer import NegotiationConfig

        name_lower = strategy_name.lower().strip()
        weights = NegotiationConfig.STRATEGY_FIT_WEIGHTS
        w = weights.get(name_lower, weights.get("default"))

        score = 0.0
        for key, val in w.items():
            if key == "price_sensitivity":
                score += val * twin.price_sensitivity
            elif key == "price_sensitivity_inv":
                score += val * (1.0 - twin.price_sensitivity)
            elif key == "urgency":
                score += val * twin.urgency
            elif key == "urgency_inv":
                score += val * (1.0 - twin.urgency)
            elif key == "brand_loyalty":
                score += val * twin.brand_loyalty
            elif key == "brand_loyalty_inv":
                score += val * (1.0 - twin.brand_loyalty)
            elif key == "decision_speed":
                score += val * twin.decision_speed
            elif key == "risk_aversion":
                score += val * twin.risk_aversion
            elif key == "risk_aversion_inv":
                score += val * (1.0 - twin.risk_aversion)

        return max(0.0, min(score, 1.0))

    @staticmethod
    def calculate_close_probability(
        strategy_fit: float,
        twin: DigitalTwinProfile,
        financial_metrics: FinancialMetrics,
        customer_reaction: CustomerReaction | None = None,
    ) -> float:
        """Calculate probability of closing the deal."""
        from app.core.config_layer import NegotiationConfig
        w = NegotiationConfig.CLOSE_PROBABILITY_WEIGHTS

        base_component = strategy_fit * w.get("strategy_fit", 0.50)
        urgency_component = twin.urgency * w.get("urgency", 0.20)
        speed_component = twin.decision_speed * w.get("decision_speed", 0.15)
        margin_component = financial_metrics.gross_margin_retention * w.get("margin", 0.15)

        raw_probability = (
            base_component
            + urgency_component
            + speed_component
            + margin_component
        )

        if customer_reaction is not None:
            reaction_bonus = (
                customer_reaction.buying_intent_delta * w.get("buying_intent_delta", 0.15)
                + customer_reaction.trust_delta * w.get("trust_delta", 0.10)
                + customer_reaction.objection_delta * w.get("objection_delta", -0.10)
                + customer_reaction.engagement_delta * w.get("engagement_delta", 0.05)
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
        from app.core.config_layer import NegotiationConfig
        w = NegotiationConfig.RISK_SCORE_WEIGHTS

        if deal_value <= 0:
            return 1.0

        discount_risk = (
            min(max(discount_percent, 0.0), 100.0) / 100.0
        ) * w.get("discount_risk", 0.35)

        bundle_risk = min(bundle_value / deal_value, 1.0) * w.get("bundle_risk", 0.20)
        leakage_risk = financial_metrics.contract_leakage * w.get("leakage_risk", 0.30)
        margin_risk = (1.0 - financial_metrics.gross_margin_retention) * w.get("margin_risk", 0.15)

        raw = discount_risk + bundle_risk + leakage_risk + margin_risk

        return max(0.0, min(round(raw, 6), 1.0))

    @staticmethod
    def calculate_confidence_score(
        rollout_strategy_fits: Sequence[float],
        rollout_risk_scores: Sequence[float],
    ) -> float:
        """Measure consistency across simulation rollouts."""
        from app.core.config_layer import NegotiationConfig

        if len(rollout_strategy_fits) < 2 or len(rollout_risk_scores) < 2:
            return 1.0

        var_fit = statistics.pvariance(rollout_strategy_fits)
        var_risk = statistics.pvariance(rollout_risk_scores)

        avg_var = (var_fit + var_risk) / 2.0
        max_variance = NegotiationConfig.CONFIDENCE_MAX_VARIANCE
        normalized_var = avg_var / max_variance
        confidence = 1.0 - normalized_var

        return max(0.0, min(round(confidence, 6), 1.0))