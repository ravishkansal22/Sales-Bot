"""Multi-rollout simulation engine for Ghost Negotiator.

This is the **central orchestration module**.  For every registered
strategy it:

1. Generates ``rollout_count`` parallel LLM calls (via ``asyncio.gather``).
2. Clamps each LLM output to the strategy's constraints.
3. Deterministically scores each rollout (strategy fit, risk, close
   probability) using :class:`NegotiationScorer` and
   :class:`FinancialEvaluator`.
4. Aggregates rollout-level metrics into a single
   :class:`SimulationOutput` per strategy.

**Key invariant**: the LLM *only* produces
:class:`~app.schemas.simulation.LLMStrategyOutput` (reasoning + offer
parameters).  Every numeric business metric is computed downstream by
deterministic Python code.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any
from app.core.customer_simulator import CustomerSimulator
from app.core.financial_evaluator import FinancialEvaluator
from app.core.negotiation_scorer import NegotiationScorer
from app.core.strategies.base import Strategy
from app.core.strategies.registry import StrategyRegistry
from app.schemas.chat import ConversationAnalysis
from app.models.product import Product
from app.models.customer import Customer
from app.core.config_layer import NegotiationConfig
from app.schemas.simulation import (
    DigitalTwinProfile,
    LLMStrategyOutput,
    SimulationOutput,
    SimulationRollout,
    FinancialMetrics,
)
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# System prompt shared by all strategy rollout calls
# ------------------------------------------------------------------

_ROLLOUT_SYSTEM_PROMPT: str = """\
You are an expert negotiation strategist for a B2B SaaS sales team.
You will receive a detailed prompt describing a customer profile,
conversation context, deal economics, and the strategy you must use.

Return EXACTLY one JSON object matching the LLMStrategyOutput schema:

{
  "strategy_name": "<strategy name>",
  "offer_type": "<offer category>",
  "discount_percent": <float 0-100>,
  "bundle_value": <float >= 0>,
  "reasoning": "<detailed multi-sentence justification>"
}

Rules:
- Do NOT include any financial metrics, probabilities, or scores.
- Focus on REASONING — explain WHY this offer is right for this customer.
- Keep discount_percent and bundle_value within the bounds stated in the prompt.
- Your reasoning should be unique and insightful for each request.
"""


def generate_concessions(
    category: str | None,
    strategy_name: str,
    product_name: str | None = None,
    context_json: dict[str, Any] | None = None,
) -> list[str]:
    if strategy_name != "bundle":
        return []

    concession_pool = [
        "Extended 12-Month Support SLA Upgrade",
        "Flexible Net-60 Payment Terms",
        "Priority Express Delivery Logistics",
        "Complementary Installation & Setup Assistance",
        "On-Demand Team Onboarding & Training Session",
        "Premium Protection Cover Accessory Package"
    ]

    offered = []
    if context_json:
        offered = context_json.get("offered_concessions", [])

    available = [c for c in concession_pool if c not in offered]
    if len(available) < 3:
        available = available + [c for c in concession_pool if c in offered]

    return available[:3]


class SimulationEngine:
    """Orchestrate multi-rollout strategy simulations.

    For each strategy in the registry the engine generates
    ``rollout_count`` parallel LLM calls.  Each raw LLM output is then
    scored deterministically and the results are aggregated into a
    :class:`SimulationOutput`.

    Parameters
    ----------
    llm:
        An :class:`LLMProvider` for structured LLM calls.
    registry:
        The :class:`StrategyRegistry` containing available strategies.
    rollout_count:
        Number of Monte-Carlo rollouts per strategy (default 3).
    """

    def __init__(
        self,
        llm: LLMProvider,
        registry: StrategyRegistry,
        rollout_count: int = 3,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._rollout_count = max(1, rollout_count)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_dynamic_ceiling(
        self,
        product: Product,
        quantity: int,
        history: list[dict[str, Any]] | None = None,
        customer: Customer | None = None,
        brand_loyalty: float = 0.5,
        context_json: dict[str, Any] | None = None,
    ) -> float:
        """Calculate dynamic pricing ceiling incorporating segment, spend, volume, and stock."""
        import math
        from app.core.config_layer import NegotiationConfig

        user_turns_count = sum(1 for h in history if h.get("role") == "user") if history else 0
        
        base_ceiling = NegotiationConfig.STAGE_CEILINGS.get(
            user_turns_count, 
            NegotiationConfig.STAGE_CEILINGS["default"]
        )
        
        ceiling = base_ceiling

        # 1. Volume allowance
        if quantity > 1:
            volume_allowance = min(
                NegotiationConfig.VOLUME_MAX_ALLOWANCE, 
                math.sqrt(quantity) * NegotiationConfig.VOLUME_COEFFICIENT
            )
            ceiling += volume_allowance

        # 2. Customer segment modifiers
        customer_segment = customer.customer_segment if customer else None
        if customer_segment:
            seg_key = customer_segment.upper()
            modifier = NegotiationConfig.SEGMENT_MODIFIERS.get(
                seg_key, 
                NegotiationConfig.SEGMENT_MODIFIERS["default"]
            )
            ceiling += modifier

        # 3. Customer loyalty modifier
        if brand_loyalty > NegotiationConfig.LOYALTY_HIGH_THRESHOLD:
            ceiling += NegotiationConfig.LOYALTY_HIGH_MODIFIER
        elif brand_loyalty < NegotiationConfig.LOYALTY_LOW_THRESHOLD:
            ceiling += NegotiationConfig.LOYALTY_LOW_MODIFIER

        # 4. Historical spend modifier
        total_spend = customer.total_spend if customer else 0.0
        if total_spend > NegotiationConfig.SPEND_HIGH_THRESHOLD:
            ceiling += NegotiationConfig.SPEND_HIGH_MODIFIER
        elif total_spend > NegotiationConfig.SPEND_MED_THRESHOLD:
            ceiling += NegotiationConfig.SPEND_MED_MODIFIER

        # 5. Inventory pressure modifier
        stock = product.stock_quantity if product else 50
        if stock < NegotiationConfig.STOCK_CRITICAL:
            ceiling = min(ceiling, NegotiationConfig.STOCK_CRITICAL_CEILING)
        elif stock < NegotiationConfig.STOCK_LOW:
            ceiling = min(ceiling, NegotiationConfig.STOCK_LOW_CEILING)
        elif stock < NegotiationConfig.STOCK_MEDIUM:
            ceiling = min(ceiling, NegotiationConfig.STOCK_MEDIUM_CEILING)
        else:
            ceiling += NegotiationConfig.STOCK_EXCESS_CEILING_MODIFIER
        
        persistence = 0
        competitor_pressure = False
        walkaway_risk = False

        if context_json:
            persistence = context_json.get("customer_persistence", 0)
            competitor_pressure = context_json.get("competitor_pressure", False)
            walkaway_risk = context_json.get("walkaway_risk", False)

        # Progressive flexibility
        ceiling += persistence * 1.5

        if competitor_pressure:
            ceiling += 2.0

        if walkaway_risk:
            ceiling += 2.0

        # 6. Absolute Floor Clamp
        floor_discount = max(0.0, (1.0 - product.minimum_price / product.selling_price) * 100.0)
        
        return max(0.0, min(ceiling, floor_discount))

    async def simulate_all(
        self,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        product: Product | None = None,
        quantity: int = 1,
        history: list[dict[str, Any]] | None = None,
        customer: Customer | None = None,
        context_json: dict[str, Any] | None = None,
    ) -> list[SimulationOutput]:
        """Run all registered strategies with multi-rollout simulations.

        Strategies are simulated in parallel (one ``asyncio.gather`` per
        strategy, all strategies also gathered together).  This minimises
        total wall-clock time.

        Parameters
        ----------
        twin:
            Customer's digital-twin behavioural profile.
        analysis:
            Structured analysis of the customer's latest message.
        deal_value:
            Full list-price deal value (USD).  Must be > 0.
        cost_basis:
            Internal cost to fulfil the deal (USD).  Must be >= 0.
        product:
            Optional resolved Product ORM model.
        quantity:
            Quantity of products being negotiated.
        history:
            Conversation turn history.
        customer:
            Resolved Customer profile record.

        Returns
        -------
        list[SimulationOutput]
            One :class:`SimulationOutput` per registered strategy, each
            containing aggregated rollout results.
        """

        strategies: list[Strategy] = self._registry.get_all()
        if not strategies:
            logger.warning("No strategies registered — returning empty simulation list.")
            return []

        # Launch all strategies concurrently.
        tasks = [
            self._simulate_strategy(strategy, twin, analysis, deal_value, cost_basis, product, quantity, history, customer, context_json)
            for strategy in strategies
        ]
        results: list[SimulationOutput] = await asyncio.gather(*tasks)
        return results

    # ------------------------------------------------------------------
    # Per-strategy simulation (private)
    # ------------------------------------------------------------------

    async def _simulate_strategy(
        self,
        strategy: Strategy,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        product: Product | None = None,
        quantity: int = 1,
        history: list[dict[str, Any]] | None = None,
        customer: Customer | None = None,
        context_json: dict[str, Any] | None = None,
    ) -> SimulationOutput:
        """Simulate a single strategy with ``rollout_count`` rollouts.

        Parameters
        ----------
        strategy:
            The strategy to simulate.
        twin, analysis, deal_value, cost_basis:
            Simulation context (see :meth:`simulate_all`).
        product:
            Optional resolved Product catalog model.
        quantity:
            Quantity under negotiation.

        Returns
        -------
        SimulationOutput
            Aggregated output for this strategy.
        """

        # 1. Generate rollout prompts and call LLM in parallel.
        rollout_tasks = [
            self._run_single_rollout(strategy, twin, analysis, deal_value, cost_basis, i, product, quantity, history, customer, context_json)
            for i in range(self._rollout_count)
        ]
        raw_outputs: list[LLMStrategyOutput] = await asyncio.gather(*rollout_tasks)

        # 2. Clamp each output to strategy constraints.
        constraints = strategy.get_constraints(context_json)
        if product is not None:
            constraints = dict(constraints)  # Avoid mutating shared class constraints
            dynamic_ceiling = self.calculate_dynamic_ceiling(
                product=product,
                quantity=quantity,
                history=history,
                customer=customer,
                brand_loyalty=twin.brand_loyalty if hasattr(twin, "brand_loyalty") else 0.5,
                context_json=context_json
                )
            
            constraints["max_discount_percent"] = min(constraints.get("max_discount_percent", 100.0), dynamic_ceiling)

        clamped_outputs: list[LLMStrategyOutput] = [
            self._clamp_output(output, constraints, deal_value)
            for output in raw_outputs
        ]

        # 3. Score each rollout deterministically.
        rollouts: list[SimulationRollout] = []
        close_probabilities: list[float] = []
        expected_profits: list[float] = []
        expected_values: list[float] = []
        risk_scores: list[float] = []
        margin_retentions: list[float] = []
        strategy_fits: list[float] = []

        for idx, output in enumerate(clamped_outputs):
            # Financial evaluation (pure arithmetic).
            fin_metrics = FinancialEvaluator.evaluate(
                deal_value=deal_value,
                cost_basis=cost_basis,
                discount_percent=output.discount_percent,
                bundle_value=output.bundle_value,
                product_selling_price=product.selling_price if product else None,
                product_cost_price=product.cost_price if product else None,
                product_minimum_price=product.minimum_price if product else None,
                quantity=quantity,
            )

            # Apply product-aware risk adjustment before calling the Scorer
            if product is not None:
                closeness = fin_metrics.minimum_price_closeness
                if closeness > 0.0:
                    # Nudge margin retention down and leakage up to reflect floor-price pressure
                    adjusted_retention = max(0.0, fin_metrics.gross_margin_retention * (1.0 - closeness * 0.6))
                    fin_metrics = FinancialMetrics(
                        gross_margin_retention=adjusted_retention,
                        contract_leakage=1.0 - adjusted_retention,
                        revenue_impact=fin_metrics.revenue_impact,
                        profit_impact=fin_metrics.profit_impact,
                        minimum_price_closeness=fin_metrics.minimum_price_closeness,
                    )

            margin_retentions.append(
                fin_metrics.gross_margin_retention
            )

            # Strategy fit (deterministic scoring).
            strategy_fit = NegotiationScorer.calculate_strategy_fit(
                twin=twin,
                strategy_name=output.strategy_name,
                offer_type=output.offer_type,
                discount_percent=output.discount_percent,
                bundle_value=output.bundle_value,
            )

            # Risk score (deterministic).
            risk_score = NegotiationScorer.calculate_risk_score(
                discount_percent=output.discount_percent,
                bundle_value=output.bundle_value,
                deal_value=deal_value,
                financial_metrics=fin_metrics,
            )

            # Simulate customer reaction.
            customer_reaction = CustomerSimulator.simulate_reaction(
                twin=twin,
                strategy_output=output,
                analysis=analysis,
                context_json=context_json,
            )

            # Close probability using reaction-aware scoring.
            close_prob = NegotiationScorer.calculate_close_probability(
                strategy_fit=strategy_fit,
                twin=twin,
                financial_metrics=fin_metrics,
                customer_reaction=customer_reaction,
            )

            # Derived financial metrics using product prices if present.
            s_price = product.selling_price if product else deal_value
            c_price = product.cost_price if product else cost_basis
            discounted_revenue = (s_price * quantity) * (1.0 - output.discount_percent / 100.0)
            total_cost = (c_price * quantity) + output.bundle_value
            expected_profit = discounted_revenue - total_cost
            expected_value = close_prob * expected_profit

            # Accumulate for averaging.
            strategy_fits.append(strategy_fit)
            risk_scores.append(risk_score)
            close_probabilities.append(close_prob)
            expected_profits.append(expected_profit)
            expected_values.append(expected_value)

            rollouts.append(
                  SimulationRollout(
                      rollout_id=f"{strategy.name}-rollout-{idx}-{uuid.uuid4().hex[:8]}",
                     reasoning=output.reasoning,
                      strategy_fit=round(strategy_fit, 6),
                      risk_score=round(risk_score, 6),
                      customer_reaction=customer_reaction,
                      timeline_events=[
                          "Strategy generated",
                          "Customer reaction simulated",
                          f"Trust delta: {customer_reaction.trust_delta}",
                          f"Buying intent delta: {customer_reaction.buying_intent_delta}",
                          "Close probability recalculated",
                       ],
                   )
            )

        # 4. Aggregate across rollouts.
        n = len(rollouts)
        avg_close_prob = sum(close_probabilities) / n
        avg_risk = sum(risk_scores) / n
        avg_profit = sum(expected_profits) / n
        avg_ev = sum(expected_values) / n
        avg_margin = sum(margin_retentions) / n

        # Use the first rollout's offer params as the "representative"
        # offer (they should be similar after clamping).  The reasoning
        # from the first rollout is used as the headline reasoning.
        if strategy.name == "discount":
            best_idx = 0
            best_score = float("-inf")
            for idx in range(len(clamped_outputs)):
                ev = expected_values[idx]
                cp = close_probabilities[idx]
                rs = risk_scores[idx]
                norm_ev = ev / deal_value if deal_value > 0 else 0.0
                score = norm_ev * 0.5 + cp * 0.3 + (1.0 - rs) * 0.2
                if score > best_score:
                    best_score = score
                    best_idx = idx
            representative = clamped_outputs[best_idx]
        else:
            representative = max(
                clamped_outputs,
                key=lambda o: o.discount_percent
            )

        return SimulationOutput(
            strategy_name=strategy.name,
            offer_type=strategy.offer_type,
            discount_percent=round(representative.discount_percent, 2),
            bundle_value=round(representative.bundle_value, 2),
            reasoning=representative.reasoning,
            rollouts=rollouts,
            average_close_probability=round(avg_close_prob, 6),
            average_risk_score=round(avg_risk, 6),
            average_expected_profit=round(avg_profit, 2),
            average_gross_margin_retention=round(
                avg_margin,
                6,
            ),
            average_expected_value=round(avg_ev, 2),
            concessions=generate_concessions(product.category if product else None, strategy.name, product.name if product else None, context_json)
        )

    # ------------------------------------------------------------------
    # Single rollout execution (private)
    # ------------------------------------------------------------------

    async def _run_single_rollout(
        self,
        strategy: Strategy,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        rollout_index: int,
        product: Product | None = None,
        quantity: int = 1,
        history: list[dict[str, Any]] | None = None,
        customer: Customer | None = None,
        context_json: dict[str, Any] | None = None,
    ) -> LLMStrategyOutput:
        """Execute a single rollout for a strategy (deterministic, no LLM call)."""
        # Get base constraints
        constraints = dict(strategy.get_constraints(context_json))
        
        # Calculate dynamic maximum discount ceiling if product is present
        if product is not None:
            brand_loyalty = getattr(twin, "brand_loyalty", 0.5) or 0.5
            dynamic_ceiling = self.calculate_dynamic_ceiling(
                product=product,
                quantity=quantity,
                history=history,
                customer=customer,
                brand_loyalty=brand_loyalty,
                context_json=context_json,
            )
            constraints["max_discount_percent"] = min(constraints.get("max_discount_percent", 100.0), dynamic_ceiling)

        min_disc = constraints.get("min_discount_percent", 0.0)
        max_disc = constraints.get("max_discount_percent", 100.0)
        min_bund = constraints.get("min_bundle_value", 0.0)
        max_bund = constraints.get("max_bundle_value", float("inf"))

        # Cap bundle cost dynamically at 25% of deal value
        effective_max_bund = min(max_bund, deal_value * NegotiationConfig.MAX_BUNDLE_DEAL_VALUE_RATIO)

        # Safety rail: ensure min bounds do not exceed max bounds
        if min_disc > max_disc:
            min_disc = max_disc
        if min_bund > effective_max_bund:
            min_bund = effective_max_bund

        # Interpolate based on rollout_index to introduce variation across Monte-Carlo rollouts
        if self._rollout_count > 1:
            ratio = rollout_index / (self._rollout_count - 1)
        else:
            ratio = 0.5

        ratio = max(0.0, min(ratio, 1.0))

        discount_percent = min_disc + ratio * (max_disc - min_disc)
        bundle_value = min_bund + ratio * (effective_max_bund - min_bund)

        # Generate a descriptive reasoning string based on the profile traits and parameters
        reasoning = (
            f"Deterministic simulation rollout for strategy '{strategy.name}'. "
            f"Fitted for customer price sensitivity {twin.price_sensitivity:.2f} and urgency {twin.urgency:.2f}. "
            f"Proposed offer: {discount_percent:.2f}% discount and bundle value of {bundle_value:.2f}."
        )

        return LLMStrategyOutput(
            strategy_name=strategy.name,
            offer_type=strategy.offer_type,
            discount_percent=round(discount_percent, 2),
            bundle_value=round(bundle_value, 2),
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Output clamping (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp_output(
        output: LLMStrategyOutput,
        constraints: dict[str, Any],
        deal_value: float,
    ) -> LLMStrategyOutput:
        """Clamp LLM output values to the strategy's constraints.

        Ensures the LLM cannot propose values outside the allowed ranges
        — an essential safety rail since LLMs are non-deterministic.

        Parameters
        ----------
        output:
            Raw LLM output.
        constraints:
            The strategy's constraint dictionary (from
            :meth:`Strategy.get_constraints`).
        deal_value:
            Deal value used to dynamically cap bundle values.

        Returns
        -------
        LLMStrategyOutput
            A new output with clamped values (original is not mutated).
        """

        min_disc = constraints.get("min_discount_percent", 0.0)
        max_disc = constraints.get("max_discount_percent", 100.0)
        min_bund = constraints.get("min_bundle_value", 0.0)
        max_bund = constraints.get("max_bundle_value", float("inf"))

        # Dynamic cap: bundle cost should never exceed 25% of deal value.
        effective_max_bund = min(max_bund, deal_value * NegotiationConfig.MAX_BUNDLE_DEAL_VALUE_RATIO)

        # Safety rail: ensure min bounds do not exceed max bounds
        if min_disc > max_disc:
            min_disc = max_disc
        if min_bund > effective_max_bund:
            min_bund = effective_max_bund

        clamped_discount = max(min_disc, min(output.discount_percent, max_disc))
        clamped_bundle = max(min_bund, min(output.bundle_value, effective_max_bund))

        return LLMStrategyOutput(
            strategy_name=output.strategy_name,
            offer_type=output.offer_type,
            discount_percent=round(clamped_discount, 2),
            bundle_value=round(clamped_bundle, 2),
            reasoning=output.reasoning,
        )
