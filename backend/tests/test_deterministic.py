"""Unit tests for the deterministic modules of Ghost Negotiator.

Verifies:
- FinancialEvaluator
- NegotiationScorer
- StrategyOptimizer
"""

from __future__ import annotations

from app.core.financial_evaluator import FinancialEvaluator
from app.core.negotiation_scorer import NegotiationScorer
from app.core.strategy_optimizer import StrategyOptimizer
from app.schemas.simulation import (
    DigitalTwinProfile,
    FinancialMetrics,
    SimulationOutput,
    SimulationRollout,
)


def test_financial_evaluator_basic() -> None:
    """Test standard deal values and expected financial impacts."""
    # List price: 10,000, cost basis: 6,000 (40% margin)
    # Offer: 10% discount, no bundle
    # Discounted revenue: 9,000, new margin: 3,000, original margin: 4,000
    # Margin retention: 3,000 / 4,000 = 0.75
    # Revenue impact: -0.10
    # Profit impact: -1,000
    metrics = FinancialEvaluator.evaluate(
        deal_value=10000.0,
        cost_basis=6000.0,
        discount_percent=10.0,
        bundle_value=0.0,
    )
    assert metrics.gross_margin_retention == 0.75
    assert metrics.revenue_impact == -0.10
    assert metrics.profit_impact == -1000.0
    assert metrics.contract_leakage == 0.25


def test_financial_evaluator_degenerate() -> None:
    """Test boundary conditions and degenerate values."""
    # Zero deal value
    metrics = FinancialEvaluator.evaluate(
        deal_value=0.0,
        cost_basis=100.0,
        discount_percent=10.0,
        bundle_value=10.0,
    )
    assert metrics.gross_margin_retention == 0.0
    assert metrics.revenue_impact == 0.0
    assert metrics.profit_impact == 0.0
    assert metrics.contract_leakage == 1.0

    # Negative deal value
    metrics = FinancialEvaluator.evaluate(
        deal_value=-500.0,
        cost_basis=100.0,
        discount_percent=10.0,
        bundle_value=10.0,
    )
    assert metrics.gross_margin_retention == 0.0


def test_financial_evaluator_low_margin() -> None:
    """Test when the original deal margin is zero or negative."""
    metrics = FinancialEvaluator.evaluate(
        deal_value=1000.0,
        cost_basis=1200.0,
        discount_percent=5.0,
        bundle_value=50.0,
    )
    assert metrics.gross_margin_retention == 0.0
    assert metrics.profit_impact == -100.0  # (950 - 1250) - (1000 - 1200) = -300 - (-200) = -100


def test_negotiation_scorer_strategy_fit() -> None:
    """Test deterministic strategy fit scoring against customer profile."""
    twin = DigitalTwinProfile(
        price_sensitivity=0.8,
        urgency=0.6,
        risk_aversion=0.4,
        brand_loyalty=0.3,
        decision_speed=0.5,
    )

    # 1. Discount strategy fit
    # 0.40 * price_sensitivity + 0.25 * urgency + 0.20 * (1 - brand_loyalty) + 0.15 * decision_speed
    # 0.40 * 0.8 + 0.25 * 0.6 + 0.20 * 0.7 + 0.15 * 0.5
    # = 0.32 + 0.15 + 0.14 + 0.075 = 0.685
    fit_discount = NegotiationScorer.calculate_strategy_fit(
        twin=twin,
        strategy_name="discount",
        offer_type="percentage_discount",
        discount_percent=10.0,
        bundle_value=0.0,
    )
    assert abs(fit_discount - 0.685) < 1e-6

    # 2. Hardline strategy fit
    # 0.35 * brand_loyalty + 0.30 * (1 - price_sensitivity) + 0.20 * risk_aversion + 0.15 * (1 - urgency)
    # 0.35 * 0.3 + 0.30 * 0.2 + 0.20 * 0.4 + 0.15 * 0.4
    # = 0.105 + 0.06 + 0.08 + 0.06 = 0.305
    fit_hardline = NegotiationScorer.calculate_strategy_fit(
        twin=twin,
        strategy_name="Hardline",
        offer_type="hardline",
        discount_percent=0.0,
        bundle_value=0.0,
    )
    assert abs(fit_hardline - 0.305) < 1e-6

    # 3. Unknown strategy fit (fallback blend)
    # Even blend: 0.20 * (0.8 + 0.6 + 0.3 + (1 - 0.4) + 0.5) = 0.20 * 2.8 = 0.56
    fit_unknown = NegotiationScorer.calculate_strategy_fit(
        twin=twin,
        strategy_name="wildcard",
        offer_type="unknown",
        discount_percent=5.0,
        bundle_value=100.0,
    )
    assert abs(fit_unknown - 0.56) < 1e-6


def test_negotiation_scorer_close_probability() -> None:
    """Test deterministic close probability calculation."""
    twin = DigitalTwinProfile(
        price_sensitivity=0.5,
        urgency=0.8,
        risk_aversion=0.5,
        brand_loyalty=0.5,
        decision_speed=0.6,
    )
    fin_metrics = FinancialMetrics(
        gross_margin_retention=0.8,
        revenue_impact=-0.05,
        profit_impact=-50.0,
        contract_leakage=0.2,
    )

    # strategy_fit = 0.70
    # base = 0.70 * 0.50 = 0.35
    # urgency = 0.8 * 0.20 = 0.16
    # speed = 0.6 * 0.15 = 0.09
    # margin = 0.8 * 0.15 = 0.12
    # Total = 0.35 + 0.16 + 0.09 + 0.12 = 0.72
    prob = NegotiationScorer.calculate_close_probability(
        strategy_fit=0.70,
        twin=twin,
        financial_metrics=fin_metrics,
    )
    assert abs(prob - 0.72) < 1e-6


def test_negotiation_scorer_risk_score() -> None:
    """Test deterministic risk score calculation."""
    fin_metrics = FinancialMetrics(
        gross_margin_retention=0.8,
        revenue_impact=-0.10,
        profit_impact=-100.0,
        contract_leakage=0.2,
    )

    # discount_risk = (10 / 100) * 0.35 = 0.035
    # bundle_risk = (500 / 10000) * 0.20 = 0.05 * 0.20 = 0.01
    # leakage_risk = 0.2 * 0.30 = 0.06
    # margin_risk = (1.0 - 0.8) * 0.15 = 0.03
    # Total = 0.035 + 0.01 + 0.06 + 0.03 = 0.135
    risk = NegotiationScorer.calculate_risk_score(
        discount_percent=10.0,
        bundle_value=500.0,
        deal_value=10000.0,
        financial_metrics=fin_metrics,
    )
    assert abs(risk - 0.135) < 1e-6


def test_negotiation_scorer_confidence_score() -> None:
    """Test deterministic confidence scoring based on rollout variance."""
    # Case 1: Identical rollouts (zero variance)
    conf_1 = NegotiationScorer.calculate_confidence_score(
        rollout_strategy_fits=[0.7, 0.7, 0.7],
        rollout_risk_scores=[0.2, 0.2, 0.2],
    )
    assert conf_1 == 1.0

    # Case 2: Some variance
    # fit variance for [0.6, 0.7, 0.8] -> mean=0.7. pvariance = ((0.1)^2 + 0 + (-0.1)^2)/3 = 0.02 / 3 = 0.0066667
    # risk variance for [0.1, 0.2, 0.3] -> mean=0.2. pvariance = 0.02 / 3 = 0.0066667
    # avg_var = 0.0066667
    # normalised_var = 0.0066667 / 0.25 = 0.0266668
    # confidence = 1 - 0.0266668 = 0.973333
    conf_2 = NegotiationScorer.calculate_confidence_score(
        rollout_strategy_fits=[0.6, 0.7, 0.8],
        rollout_risk_scores=[0.1, 0.2, 0.3],
    )
    assert abs(conf_2 - 0.973333) < 1e-5


def test_strategy_optimizer() -> None:
    """Test strategy ranking, EV adjustment, and winning strategy pick."""
    sims = [
        SimulationOutput(
            strategy_name="discount",
            offer_type="discount",
            discount_percent=10.0,
            bundle_value=0.0,
            reasoning="Reasoning for discount",
            rollouts=[
                SimulationRollout(rollout_id="r1", reasoning="1", strategy_fit=0.7, risk_score=0.2),
                SimulationRollout(rollout_id="r2", reasoning="2", strategy_fit=0.7, risk_score=0.2),
            ],
            average_close_probability=0.8,
            average_risk_score=0.2,
            average_expected_profit=4000.0,
            average_expected_value=3200.0,
            average_gross_margin_retention=0.9,
        ),
        SimulationOutput(
            strategy_name="hardline",
            offer_type="hardline",
            discount_percent=0.0,
            bundle_value=0.0,
            reasoning="Reasoning for hardline",
            rollouts=[
                SimulationRollout(rollout_id="r3", reasoning="3", strategy_fit=0.4, risk_score=0.1),
                SimulationRollout(rollout_id="r4", reasoning="4", strategy_fit=0.4, risk_score=0.1),
            ],
            average_close_probability=0.4,
            average_risk_score=0.1,
            average_expected_profit=5000.0,
            average_expected_value=2000.0,
            average_gross_margin_retention=1.0,
        ),
    ]

    # EV:
    # discount: 0.8 * 0.9 = 0.72 normalized EV
    # confidence: 1.0 (zero variance in rollout strategy_fit/risk)
    # score = 0.72 * 1000 * 0.20 + 0.8 * 1000 * 0.50 + 0.8 * 1000 * 0.20 + 1.0 * 1000 * 0.10 = 144 + 400 + 160 + 100 = 804.0
    #
    # hardline: 0.4 * 1.0 = 0.40 normalized EV
    # confidence: 1.0
    # score = 0.40 * 1000 * 0.20 + 0.4 * 1000 * 0.50 + 0.9 * 1000 * 0.20 + 1.0 * 1000 * 0.10 = 80 + 200 + 180 + 100 = 560.0
    result = StrategyOptimizer.optimize(sims)
    assert result.winning_strategy == "discount"
    assert result.score == 804.0
    assert result.confidence_score == 1.0
    assert result.risk_score == 0.2
    assert len(result.all_rankings) == 2
    assert result.all_rankings[0]["strategy_name"] == "discount"
    assert result.all_rankings[1]["strategy_name"] == "hardline"
    assert "Highest optimizer_score" in result.winning_factors[0]


def test_config_overrides() -> None:
    """Test that overrides of config settings are successfully propagated."""
    from app.services.llm_service import settings
    from app.core.config_layer import NegotiationConfig

    # Check original value
    original_coef = NegotiationConfig.VOLUME_COEFFICIENT
    assert original_coef == 3.3

    # Modify settings value
    settings.VOLUME_COEFFICIENT = 5.5
    try:
        assert NegotiationConfig.VOLUME_COEFFICIENT == 5.5
    finally:
        # Restore original value
        settings.VOLUME_COEFFICIENT = original_coef

    # Test segment modifiers
    original_segment_modifiers = settings.SEGMENT_MODIFIERS
    try:
        settings.SEGMENT_MODIFIERS = {"VIP": 10.0, "STRATEGIC": 8.0, "default": 1.0}
        assert NegotiationConfig.SEGMENT_MODIFIERS["VIP"] == 10.0
        assert NegotiationConfig.SEGMENT_MODIFIERS["STRATEGIC"] == 8.0
        assert NegotiationConfig.SEGMENT_MODIFIERS["default"] == 1.0
    finally:
        settings.SEGMENT_MODIFIERS = original_segment_modifiers

    # Test scoring weights
    original_scoring_weights = settings.SCORING_WEIGHTS
    try:
        settings.SCORING_WEIGHTS = {"expected_value": 0.50, "close_probability": 0.50}
        assert NegotiationConfig.SCORING_WEIGHTS["expected_value"] == 0.50
        assert NegotiationConfig.SCORING_WEIGHTS["close_probability"] == 0.50
    finally:
        settings.SCORING_WEIGHTS = original_scoring_weights


def test_dynamic_ceiling_constraints() -> None:
    """Test dynamic ceiling calculation and floor clamping."""
    from app.core.simulation_engine import SimulationEngine
    from app.models.product import Product
    from unittest.mock import MagicMock

    engine = SimulationEngine(llm=MagicMock(), registry=MagicMock())

    # Product with minimum price that allows 64% discount
    prod_high_floor = Product(
        selling_price=1000.0,
        minimum_price=360.0,
        stock_quantity=40,
    )
    # Stage 0: base 5% ceiling, stock=40 triggers min clamp with STOCK_MEDIUM_CEILING (10.0%)
    ceiling_1 = engine.calculate_dynamic_ceiling(
        product=prod_high_floor,
        quantity=1,
        history=[],
    )
    assert ceiling_1 <= 10.0

    # Product with high minimum price that allows only 4% discount
    prod_low_floor = Product(
        selling_price=1000.0,
        minimum_price=960.0,
        stock_quantity=150,
    )
    ceiling_2 = engine.calculate_dynamic_ceiling(
        product=prod_low_floor,
        quantity=1,
        history=[],
    )
    assert round(ceiling_2, 6) == 4.0


