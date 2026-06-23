from __future__ import annotations

import pytest
import uuid
from unittest.mock import MagicMock, AsyncMock

from app.core.intent_classifier import classify_intent, IntentClassification
from app.core.sales_response_formatter import SalesResponseFormatter
from app.models.product import Product
from app.models.product_specification import ProductSpecification
from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile, SimulationOutput, OptimizerResult

@pytest.mark.asyncio
async def test_intent_classifier_competitor() -> None:
    # Test message with competitor keywords
    res = await classify_intent("Your competitor is offering 20% discount. Can you match?")
    assert res.intent == "negotiation"
    assert res.sub_intent == "competitor_leverage"

    res_alt = await classify_intent("other vendor offers a cheaper alternative quote on amazon")
    assert res_alt.intent == "negotiation"
    assert res_alt.sub_intent == "competitor_leverage"

@pytest.mark.asyncio
async def test_intent_classifier_warranty() -> None:
    # Test message with warranty/commercial keywords
    res = await classify_intent("How much warranty coverage do I get?")
    assert res.intent == "commercial_terms"
    assert res.sub_intent is None

    res_alt = await classify_intent("is there any support service or replacement guarantee?")
    assert res_alt.intent == "commercial_terms"
    assert res_alt.sub_intent is None

def test_sales_response_formatter_competitor() -> None:
    # Competitor leverage with extracted percentage
    res = SalesResponseFormatter.format_response(
        winning_strategy="discount",
        discount_percent=5.0,
        bundle_concessions=["Extended 12-Month Support SLA Upgrade", "Flexible Net-60 Payment Terms"],
        runner_ups=[],
        list_price=79900.0,
        sub_intent="competitor_leverage",
        customer_message="Competitor offers 20% cheaper."
    )
    assert "reach 20% directly" in res
    assert "₹75,905" in res
    assert "extended support and flexible payment terms" in res

    # Competitor leverage without extracted percentage
    res_no_pct = SalesResponseFormatter.format_response(
        winning_strategy="discount",
        discount_percent=5.0,
        bundle_concessions=["Extended 12-Month Support SLA Upgrade", "Flexible Net-60 Payment Terms"],
        runner_ups=[],
        list_price=79900.0,
        sub_intent="competitor_leverage",
        customer_message="They are selling it cheaper."
    )
    assert "reach that pricing directly" in res_no_pct
    assert "₹75,905" in res_no_pct

def test_sales_response_formatter_warranty() -> None:
    res = SalesResponseFormatter.format_response(
        winning_strategy="commercial_terms",
        discount_percent=0.0,
        bundle_concessions=[],
        runner_ups=[],
        list_price=100.0,
        sub_intent="commercial_terms"
    )
    assert "Standard manufacturer warranty applies" in res

def test_sales_response_formatter_discount() -> None:
    res = SalesResponseFormatter.format_response(
        winning_strategy="discount",
        discount_percent=5.0,
        bundle_concessions=[],
        runner_ups=["bundle"],
        list_price=79900.0
    )
    assert "List Price: ₹79,900" in res
    assert "Revised Price: ₹75,905" in res
    assert "Total Savings: ₹3,995" in res
    assert "All standard support, quality guarantees" in res

def test_sales_response_formatter_bundle() -> None:
    # Bundle only (no discount)
    res = SalesResponseFormatter.format_response(
        winning_strategy="bundle",
        discount_percent=0.0,
        bundle_concessions=["Extended 12-Month Support SLA Upgrade", "Flexible Net-60 Payment Terms"],
        runner_ups=[],
        list_price=79900.0
    )
    assert "improve the overall commercial package" in res
    assert "• Extended support" in res
    assert "• Flexible payment terms" in res
    assert "$1" not in res

    # Bundle with discount (Combined)
    res_combined = SalesResponseFormatter.format_response(
        winning_strategy="bundle",
        discount_percent=5.0,
        bundle_concessions=["Extended 12-Month Support SLA Upgrade", "Flexible Net-60 Payment Terms"],
        runner_ups=[],
        list_price=79900.0
    )
    assert "saving of ₹3,995" in res_combined
    assert "In addition, I can include:" in res_combined
    assert "• Extended support" in res_combined

def test_quantity_extraction() -> None:
    from app.api.chat import extract_quantity
    assert extract_quantity("I want to buy 50 units") == 50
    assert extract_quantity("need 75 pieces of dishwasher") == 75
    assert extract_quantity("let's buy 20") == 20
    assert extract_quantity("quantity 100 is what I need") == 100
    assert extract_quantity("no quantity mentioned") is None

def test_walkaway_and_competitor_detectors() -> None:
    from app.api.chat import detect_walkaway, detect_competitor_pressure
    assert detect_walkaway("If you don't give discount I will cancel order") is True
    assert detect_walkaway("I will go elsewhere") is True
    assert detect_walkaway("standard message") is False
    
    assert detect_competitor_pressure("competitor is matching price") is True
    assert detect_competitor_pressure("other vendor quote") is True
    assert detect_competitor_pressure("standard query") is False

def test_sales_response_formatter_progression() -> None:
    # 1st objection / level 1
    res1 = SalesResponseFormatter.format_response(
        winning_strategy="discount",
        discount_percent=10.0,
        bundle_concessions=[],
        runner_ups=[],
        list_price=1000.0,
        customer_persistence=1
    )
    assert "I can immediately secure a better commercial price." in res1
    assert "List Price: ₹1,000" in res1
    assert "Revised Price: ₹900" in res1
    assert "Total Savings: ₹100" in res1
    
    # 2nd objection / level 2
    res2 = SalesResponseFormatter.format_response(
        winning_strategy="discount",
        discount_percent=10.0,
        bundle_concessions=[],
        runner_ups=[],
        list_price=1000.0,
        customer_persistence=2
    )
    assert "Given your continued interest, I can improve the pricing further." in res2

    # 3rd objection / level 3
    res3 = SalesResponseFormatter.format_response(
        winning_strategy="discount",
        discount_percent=10.0,
        bundle_concessions=[],
        runner_ups=[],
        list_price=1000.0,
        customer_persistence=3
    )
    assert "Given your continued interest, I can improve the pricing further." in res3

    # 4th objection / level 4
    res4 = SalesResponseFormatter.format_response(
        winning_strategy="discount",
        discount_percent=10.0,
        bundle_concessions=[],
        runner_ups=[],
        list_price=1000.0,
        customer_persistence=4
    )
    assert "Given your continued interest, I can improve the pricing further." in res4

def test_strategy_optimizer_progression_and_penalties() -> None:
    from app.schemas.simulation import SimulationOutput, SimulationRollout
    from app.core.strategy_optimizer import StrategyOptimizer
    
    sims = [
        SimulationOutput(
            strategy_name="hardline",
            offer_type="hardline",
            discount_percent=0.0,
            bundle_value=0.0,
            reasoning="mock",
            rollouts=[SimulationRollout(rollout_id="r1", reasoning="1", strategy_fit=0.5, risk_score=0.1)],
            average_close_probability=0.5,
            average_risk_score=0.1,
            average_expected_profit=1000.0,
            average_expected_value=500.0,
            average_gross_margin_retention=1.0,
        ),
        SimulationOutput(
            strategy_name="bundle",
            offer_type="bundle",
            discount_percent=0.0,
            bundle_value=100.0,
            reasoning="mock",
            rollouts=[SimulationRollout(rollout_id="r2", reasoning="2", strategy_fit=0.5, risk_score=0.2)],
            average_close_probability=0.6,
            average_risk_score=0.2,
            average_expected_profit=900.0,
            average_expected_value=540.0,
            average_gross_margin_retention=0.9,
        ),
        SimulationOutput(
            strategy_name="discount",
            offer_type="discount",
            discount_percent=10.0,
            bundle_value=0.0,
            reasoning="mock",
            rollouts=[SimulationRollout(rollout_id="r3", reasoning="3", strategy_fit=0.5, risk_score=0.3)],
            average_close_probability=0.7,
            average_risk_score=0.3,
            average_expected_profit=800.0,
            average_expected_value=560.0,
            average_gross_margin_retention=0.8,
        )
    ]
    
    # Without context, discount has highest expected value/fit/score
    res_default = StrategyOptimizer.optimize(sims)
    assert res_default.winning_strategy == "discount"

    # If previous strategy was discount, discount gets penalized, forcing another strategy to win
    context = {"previous_strategies": ["discount", "discount"], "customer_persistence": 1}
    res_penalized = StrategyOptimizer.optimize(sims, context_json=context)
    assert res_penalized.winning_strategy == "bundle"


def test_quantity_influence_optimizer() -> None:
    from app.core.strategy_optimizer import StrategyOptimizer
    from app.schemas.simulation import SimulationOutput, SimulationRollout

    sims = [
        SimulationOutput(
            strategy_name="hardline",
            offer_type="hardline",
            discount_percent=0.0,
            bundle_value=0.0,
            reasoning="mock",
            rollouts=[SimulationRollout(rollout_id="r1", reasoning="1", strategy_fit=0.5, risk_score=0.1)],
            average_close_probability=0.5,
            average_risk_score=0.1,
            average_expected_profit=1000.0,
            average_expected_value=500.0,
            average_gross_margin_retention=1.0,
        ),
        SimulationOutput(
            strategy_name="discount",
            offer_type="discount",
            discount_percent=10.0,
            bundle_value=0.0,
            reasoning="mock",
            rollouts=[SimulationRollout(rollout_id="r2", reasoning="2", strategy_fit=0.5, risk_score=0.2)],
            average_close_probability=0.6,
            average_risk_score=0.2,
            average_expected_profit=900.0,
            average_expected_value=540.0,
            average_gross_margin_retention=0.9,
        )
    ]

    # At quantity=1, discount wins
    res_q1 = StrategyOptimizer.optimize(sims, context_json={"mentioned_quantity": 1})
    assert res_q1.winning_strategy == "discount"

    # At quantity=100, volume boost makes discount win with a larger margin, and hardline becomes heavily penalized
    res_q100 = StrategyOptimizer.optimize(sims, context_json={"mentioned_quantity": 100})
    assert res_q100.winning_strategy == "discount"
    
    # Check that hardline score dropped relative to discount
    rank_q1 = {r["strategy_name"]: r["optimizer_score"] for r in res_q1.all_rankings}
    rank_q100 = {r["strategy_name"]: r["optimizer_score"] for r in res_q100.all_rankings}
    
    # Hardline score should be significantly lower under quantity=100 than quantity=1
    assert rank_q100["hardline"] < rank_q1["hardline"]


def test_hardline_fatigue_penalty() -> None:
    from app.core.strategy_optimizer import StrategyOptimizer
    from app.schemas.simulation import SimulationOutput, SimulationRollout

    sims = [
        SimulationOutput(
            strategy_name="hardline",
            offer_type="hardline",
            discount_percent=0.0,
            bundle_value=0.0,
            reasoning="mock",
            rollouts=[SimulationRollout(rollout_id="r1", reasoning="1", strategy_fit=0.5, risk_score=0.1)],
            average_close_probability=0.6,
            average_risk_score=0.1,
            average_expected_profit=1000.0,
            average_expected_value=600.0,
            average_gross_margin_retention=1.0,
        ),
        SimulationOutput(
            strategy_name="discount",
            offer_type="discount",
            discount_percent=5.0,
            bundle_value=0.0,
            reasoning="mock",
            rollouts=[SimulationRollout(rollout_id="r2", reasoning="2", strategy_fit=0.5, risk_score=0.2)],
            average_close_probability=0.5,
            average_risk_score=0.2,
            average_expected_profit=950.0,
            average_expected_value=475.0,
            average_gross_margin_retention=0.95,
        )
    ]

    # Without repetition, hardline wins due to higher EV
    res_first = StrategyOptimizer.optimize(sims, context_json={"previous_strategies": []})
    assert res_first.winning_strategy == "hardline"

    # With repeated hardline usage, fatigue penalty makes discount win
    res_fatigued = StrategyOptimizer.optimize(sims, context_json={"previous_strategies": ["hardline", "hardline"]})
    assert res_fatigued.winning_strategy == "discount"


@pytest.mark.asyncio
async def test_negotiation_priority_intent() -> None:
    # A query mentioning features but asking for a discount should prioritize negotiation
    res = await classify_intent("you already offered these features now give me 10%")
    assert res.intent == "negotiation"
    
    res_alt = await classify_intent("I want a bulk deal of 50 units for cheap price")
    assert res_alt.intent == "negotiation"


def test_concession_diversity_memory() -> None:
    from app.core.simulation_engine import generate_concessions

    # Initial concessions
    c1 = generate_concessions(None, "bundle", None, {})
    assert len(c1) == 3
    assert "Extended 12-Month Support SLA Upgrade" in c1

    # Concessions when support and payment terms were already offered
    context = {"offered_concessions": ["Extended 12-Month Support SLA Upgrade", "Flexible Net-60 Payment Terms"]}
    c2 = generate_concessions(None, "bundle", None, context)
    assert len(c2) == 3
    # Shuffled/prioritized new concessions should be at the front
    assert "Priority Express Delivery Logistics" in c2
    assert "Complementary Installation & Setup Assistance" in c2
    assert "On-Demand Team Onboarding & Training Session" in c2


