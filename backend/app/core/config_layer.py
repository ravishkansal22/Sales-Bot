from __future__ import annotations

from typing import Any
from app.services.llm_service import settings

class NegotiationConfigMeta(type):
    @property
    def STAGE_CEILINGS(cls) -> dict[Any, float]:
        ceilings = settings.STAGE_CEILINGS
        result = {}
        for k, v in ceilings.items():
            try:
                result[int(k)] = float(v)
            except ValueError:
                result[k] = float(v)
        return result

    @property
    def SEGMENT_MODIFIERS(cls) -> dict[str, float]:
        return settings.SEGMENT_MODIFIERS

    @property
    def VOLUME_COEFFICIENT(cls) -> float:
        return settings.VOLUME_COEFFICIENT

    @property
    def VOLUME_MAX_ALLOWANCE(cls) -> float:
        return settings.VOLUME_MAX_ALLOWANCE

    @property
    def LOYALTY_HIGH_THRESHOLD(cls) -> float:
        return settings.LOYALTY_HIGH_THRESHOLD

    @property
    def LOYALTY_HIGH_MODIFIER(cls) -> float:
        return settings.LOYALTY_HIGH_MODIFIER

    @property
    def LOYALTY_LOW_THRESHOLD(cls) -> float:
        return settings.LOYALTY_LOW_THRESHOLD

    @property
    def LOYALTY_LOW_MODIFIER(cls) -> float:
        return settings.LOYALTY_LOW_MODIFIER

    @property
    def SPEND_HIGH_THRESHOLD(cls) -> float:
        return settings.SPEND_HIGH_THRESHOLD

    @property
    def SPEND_HIGH_MODIFIER(cls) -> float:
        return settings.SPEND_HIGH_MODIFIER

    @property
    def SPEND_MED_THRESHOLD(cls) -> float:
        return settings.SPEND_MED_THRESHOLD

    @property
    def SPEND_MED_MODIFIER(cls) -> float:
        return settings.SPEND_MED_MODIFIER

    @property
    def STOCK_CRITICAL(cls) -> int:
        return settings.STOCK_CRITICAL

    @property
    def STOCK_CRITICAL_CEILING(cls) -> float:
        return settings.STOCK_CRITICAL_CEILING

    @property
    def STOCK_LOW(cls) -> int:
        return settings.STOCK_LOW

    @property
    def STOCK_LOW_CEILING(cls) -> float:
        return settings.STOCK_LOW_CEILING

    @property
    def STOCK_MEDIUM(cls) -> int:
        return settings.STOCK_MEDIUM

    @property
    def STOCK_MEDIUM_CEILING(cls) -> float:
        return settings.STOCK_MEDIUM_CEILING

    @property
    def STOCK_EXCESS_CEILING_MODIFIER(cls) -> float:
        return settings.STOCK_EXCESS_CEILING_MODIFIER

    @property
    def SCORING_WEIGHTS(cls) -> dict[str, float]:
        return settings.SCORING_WEIGHTS

    @property
    def REPEATED_DEMAND_THRESHOLD(cls) -> int:
        return settings.REPEATED_DEMAND_THRESHOLD

    @property
    def REPEATED_DEMAND_DISCOUNT_PENALTY(cls) -> float:
        return settings.REPEATED_DEMAND_DISCOUNT_PENALTY

    @property
    def REPEATED_DEMAND_BUNDLE_BOOST(cls) -> float:
        return settings.REPEATED_DEMAND_BUNDLE_BOOST

    # Centralized coefficients, scoring, and risk weights
    @property
    def STRATEGY_FIT_WEIGHTS(cls) -> dict[str, dict[str, float]]:
        return settings.STRATEGY_FIT_WEIGHTS

    @property
    def CLOSE_PROBABILITY_WEIGHTS(cls) -> dict[str, float]:
        return settings.CLOSE_PROBABILITY_WEIGHTS

    @property
    def RISK_SCORE_WEIGHTS(cls) -> dict[str, float]:
        return settings.RISK_SCORE_WEIGHTS

    @property
    def CONFIDENCE_MAX_VARIANCE(cls) -> float:
        return settings.CONFIDENCE_MAX_VARIANCE

    @property
    def MAX_BUNDLE_DEAL_VALUE_RATIO(cls) -> float:
        return settings.MAX_BUNDLE_DEAL_VALUE_RATIO

    @property
    def OPTIMIZER_RISK_MULTIPLIER(cls) -> float:
        return settings.OPTIMIZER_RISK_MULTIPLIER

    @property
    def OPTIMIZER_CLOSE_PROB_MULTIPLIER(cls) -> float:
        return settings.OPTIMIZER_CLOSE_PROB_MULTIPLIER

    @property
    def SCORING_SCALE_FACTOR(cls) -> float:
        return settings.SCORING_SCALE_FACTOR


class NegotiationConfig(metaclass=NegotiationConfigMeta):
    """Centralised configuration layer for B2B negotiation logic.
    
    Houses discount coefficients, customer segment modifiers, inventory weights,
    and optimizer scoring constants to prevent hardcoded magic numbers.
    """
    pass
