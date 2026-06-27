"""Deterministic strategy optimizer for Ghost Negotiator.

Ranks simulated strategies by Expected Value and selects a winner.
All reasoning is generated from data — **no LLM, no AI**.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.negotiation_scorer import NegotiationScorer
from app.core.config_layer import NegotiationConfig
from app.schemas.simulation import (
    OptimizationMode,
    OptimizerResult,
    SimulationOutput,
)

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """Select the optimal negotiation strategy from simulation results.

    The optimizer uses a composite scoring function to rank strategies.
    All outputs, including ``optimizer_reasoning``, are built
    deterministically from the numeric data.
    """

    @staticmethod
    def optimize(
        simulations: list[SimulationOutput],
        mode: OptimizationMode = OptimizationMode.BALANCED,
        stock_quantity: int = 50,
        history: list[dict[str, Any]] | None = None,
        has_pricing_request: bool = True,
        context_json: dict[str, Any] | None = None,
        dynamic_ceiling: float = 0.0,
        list_price: float = 0.0,
        requested_discount_percent: float = 0.0,
        last_discount_offered: float = 0.0,
    ) -> OptimizerResult:
        """Rank strategies and return the winner.

        Parameters
        ----------
        simulations:
            One :class:`SimulationOutput` per strategy, each containing
            aggregated rollout results.
        mode:
            Optimization objective (balanced, profit, margin, close rate).
        stock_quantity:
            Current stock quantity of the product.
        history:
            Conversation turns history to evaluate repeated demands.
        dynamic_ceiling:
            The maximum ceiling for discounts based on business rules.
        list_price:
            The original selling price of the product under negotiation.
        requested_discount_percent:
            The discount percentage currently requested by the customer.

        Returns
        -------
        OptimizerResult
            The winning strategy with full reasoning, rankings, and
            confidence metadata.
        """

        if not simulations:
            raise ValueError("Cannot optimise an empty list of simulations.")

        logger.info(
            "[DIAGNOSTICS - STRATEGY OPTIMIZATION] Starting optimization. Mode: %s, Stock: %d, Has Pricing Request: %s, Dynamic Ceiling: %.2f%%, List Price: %.2f, Requested Discount: %.2f%%",
            mode.value if hasattr(mode, "value") else str(mode),
            stock_quantity,
            has_pricing_request,
            dynamic_ceiling,
            list_price,
            requested_discount_percent
        )

        # Determine repeated discount demands from history or context_json
        discount_demands = 0
        if context_json:
            discount_demands = context_json.get("customer_persistence", 0)
        elif history:
            discount_demands = sum(
                1 for h in history 
                if h.get("role") == "user" 
                and any(kw in h.get("message", "").lower() for kw in ["discount", "%", "off", "cheaper", "lower", "price", "cut"])
            )

        # ------------------------------------------------------------------
        # 1. Score every strategy
        # ------------------------------------------------------------------
        rankings: list[dict[str, Any]] = []

        for sim in simulations:
            expected_value: float = (
                sim.average_close_probability * sim.average_expected_profit
            )

            # Compute per-rollout scores for confidence calculation.
            rollout_fits: list[float] = [r.strategy_fit for r in sim.rollouts]
            rollout_risks: list[float] = [r.risk_score for r in sim.rollouts]

            confidence: float = NegotiationScorer.calculate_confidence_score(
                rollout_fits, rollout_risks,
            )

            optimizer_score: float = (
                StrategyOptimizer._calculate_strategy_score(
                    sim,
                    confidence,
                    mode,
                    context_json,
                    requested_discount_percent=requested_discount_percent,
                )
            )

            # Apply repeated demand penalties/boosts to protect margins and guide bundles
            if discount_demands >= NegotiationConfig.REPEATED_DEMAND_THRESHOLD:
                if sim.strategy_name == "discount":
                    optimizer_score += NegotiationConfig.REPEATED_DEMAND_DISCOUNT_PENALTY
                elif sim.strategy_name == "bundle":
                    optimizer_score += NegotiationConfig.REPEATED_DEMAND_BUNDLE_BOOST

            # Detailed simulation logging as requested by user
            logger.info(
                "Simulation log: strategy=%s, score=%.2f, discount=%.2f%%, bundle_items=%.2f, "
                "quantity concessions=%s, close_probability=%.4f, revenue=%.2f, margin retention=%.4f",
                sim.strategy_name,
                optimizer_score,
                sim.discount_percent,
                sim.bundle_value,
                sim.concessions,
                sim.average_close_probability,
                sim.average_expected_value,
                sim.average_gross_margin_retention
            )

            rankings.append({
                "strategy_name": sim.strategy_name,
                "expected_value": round(expected_value, 2),
                "optimizer_score": round(optimizer_score, 2),
                "optimization_mode": mode.value,
                "average_close_probability": round(sim.average_close_probability, 4),
                "average_expected_profit": round(sim.average_expected_profit, 2),
                "average_risk_score": round(sim.average_risk_score, 4),
                "confidence_score": round(confidence, 4),
                "average_expected_value": round(sim.average_expected_value, 2),
                "average_gross_margin_retention": round(sim.average_gross_margin_retention, 4),
                "reasoning_summary": sim.reasoning,
            })

        # ------------------------------------------------------------------
        # 2. Sort descending by optimizer_score
        # ------------------------------------------------------------------
        rankings.sort(
            key=lambda r: r["optimizer_score"],
            reverse=True,
        )

        # Determine inventory explanation dynamically based on stock levels
        if stock_quantity < NegotiationConfig.STOCK_CRITICAL:
            inventory_explanation = "Discount flexibility reduced due to critical inventory levels."
        elif stock_quantity < NegotiationConfig.STOCK_LOW:
            inventory_explanation = "Discount flexibility reduced due to limited inventory."
        elif stock_quantity >= NegotiationConfig.STOCK_MEDIUM:
            inventory_explanation = "Additional concessions possible due to excess inventory."
        else:
            inventory_explanation = "Standard discount flexibility applied under normal stock levels."

        # Extract current customer requested discount for offer-price clamping.
        # The clamping ceiling is the persisted requested discount from context_json
        # (which may differ from the live requested_discount_percent parameter used for
        # gap-penalty scoring).  Priority: context_json keys > live parameter.
        current_customer_requested_discount = 0.0
        if context_json:
            current_customer_requested_discount = (
                context_json.get("current_customer_requested_discount", 0.0)
                or context_json.get("requested_discount", 0.0)
                or requested_discount_percent
            )
        elif requested_discount_percent > 0.0:
            current_customer_requested_discount = requested_discount_percent


        if not has_pricing_request:
            winning_factors = ["Initial State"]
            optimizer_reasoning = "No pricing or discount request has been made yet. Initial B2B offering stands at list price."
            
            raw_optimizer_discount = 0.0
            actual_offer_discount = 0.0
            actual_offer_price = list_price

            if list_price > 0.0:
                if actual_offer_discount == 0.0:
                    actual_offer_price = list_price
                if actual_offer_price <= 0.0:
                    logger.critical(
                        "[CRITICAL] Offer price calculated as <= 0 (actual_offer_price=%.2f) "
                        "for product with list_price=%.2f. Discount was %.2f%%.",
                        actual_offer_price, list_price, actual_offer_discount
                    )
                    if NegotiationConfig.STRICT_NEGOTIATION_VALIDATION:
                        raise ValueError(
                            f"Negotiation validation failed: Calculated price {actual_offer_price} "
                            f"is less than or equal to zero for list price {list_price}."
                        )
                    else:
                        actual_offer_price = list_price
                        actual_offer_discount = 0.0

            logger.info(
                f"Requested discount: {requested_discount_percent}%\n"
                f"Current customer requested discount: {current_customer_requested_discount}%\n\n"
                f"Raw optimizer discount: {raw_optimizer_discount}%\n"
                f"Dynamic ceiling: {dynamic_ceiling}%\n\n"
                f"Actual customer-facing offer: {actual_offer_discount}%\n"
                f"Price: ₹{actual_offer_price}\n\n"
                f"Winner strategy: none"
            )

            logger.info(
                "[DIAGNOSTICS - STRATEGY OPTIMIZATION] Optimization complete (No pricing request). Winner: none, Actual Price: %.2f",
                actual_offer_price
            )

            return OptimizerResult(
                winning_strategy="none",
                score=1.0,
                optimization_mode=mode,
                optimizer_reasoning=optimizer_reasoning,
                winning_factors=winning_factors,
                risk_score=0.0,
                confidence_score=1.0,
                all_rankings=rankings,
                inventory_explanation=inventory_explanation,
                actual_offer_discount=actual_offer_discount,
                actual_offer_price=actual_offer_price,
                current_discount_percent=actual_offer_discount,
                current_offer_price=actual_offer_price,
            )

        winner: dict[str, Any] = rankings[0]
        winner_strategy = winner["strategy_name"]

        # Populate explainability variables
        for rank in rankings:
            is_winner = rank["strategy_name"] == winner_strategy
            
            # Retrieve the corresponding simulation for rollout fits
            sim = next(s for s in simulations if s.strategy_name == rank["strategy_name"])
            avg_fit = sum(r.strategy_fit for r in sim.rollouts) / len(sim.rollouts) if sim.rollouts else 0.5
            
            rank["customer_fit_score"] = f"{round(avg_fit * 100, 1)}%"
            rank["risk_score_pct"] = f"{round(rank['average_risk_score'] * 100, 1)}%"
            rank["margin_impact"] = f"{round(rank['average_gross_margin_retention'] * 100, 1)}% margin retention"
            rank["revenue_impact"] = f"₹{rank['expected_value']:,.2f} expected value"
            
            if stock_quantity < NegotiationConfig.STOCK_CRITICAL:
                rank["inventory_impact"] = "Conserves critical inventory"
            elif stock_quantity < NegotiationConfig.STOCK_LOW:
                rank["inventory_impact"] = "Conserves low stock"
            elif stock_quantity >= NegotiationConfig.STOCK_MEDIUM:
                rank["inventory_impact"] = "Liquidates excess stock"
            else:
                rank["inventory_impact"] = "Standard stock velocity"

            if is_winner:
                rank["why_selected"] = f"Highest composite optimizer score ({rank['optimizer_score']}) under {mode.value} objective."
                rank["loss_reason"] = "N/A (Winning Strategy)"
            else:
                rank["why_selected"] = "N/A"
                if rank["average_risk_score"] > winner["average_risk_score"] * NegotiationConfig.OPTIMIZER_RISK_MULTIPLIER:
                    rank["loss_reason"] = "Rejected: Excess margin risk profile exposes deal to low profitability."
                elif rank["average_close_probability"] < winner["average_close_probability"] * NegotiationConfig.OPTIMIZER_CLOSE_PROB_MULTIPLIER:
                    rank["loss_reason"] = "Rejected: Weak close probability increases churn risk significantly."
                else:
                    rank["loss_reason"] = f"Rejected: Yields lower expected B2B contract value compared to the winning strategy."

        # ------------------------------------------------------------------
        # 3. Build deterministic reasoning
        # ------------------------------------------------------------------
        winning_factors: list[str] = StrategyOptimizer._identify_winning_factors(
            winner, rankings,
        )
        optimizer_reasoning: str = StrategyOptimizer._build_reasoning(
            winner, rankings, winning_factors,
        )

        winning_sim = next((s for s in simulations if s.strategy_name == winner_strategy), None)
        raw_optimizer_discount = winning_sim.discount_percent if winning_sim else 0.0

        # -- Monotonicity enforcement: never retract a previously offered discount --
        pre_monotonicity_discount = raw_optimizer_discount
        effective_discount = max(
            raw_optimizer_discount,
            last_discount_offered
        )
        if effective_discount > raw_optimizer_discount:
            logger.info(
                "[DIAGNOSTICS - MONOTONICITY] Monotonicity guard applied: "
                "raw_optimizer_discount=%.2f%% would retract last_discount_offered=%.2f%%. "
                "Enforced effective_discount=%.2f%%.",
                pre_monotonicity_discount,
                last_discount_offered,
                effective_discount,
            )
        else:
            logger.info(
                "[DIAGNOSTICS - MONOTONICITY] No retraction detected: "
                "raw_optimizer_discount=%.2f%%, last_discount_offered=%.2f%%, effective=%.2f%%.",
                raw_optimizer_discount,
                last_discount_offered,
                effective_discount,
            )

        # --------------------------------------------
        # Progressive Discount Unlocking
        # --------------------------------------------
        persistence = 0
        walkaway_risk = False
        competitor_pressure = False
        quantity = 1

        max_allowed_discount = dynamic_ceiling

        if context_json:
            persistence = context_json.get("customer_persistence", 0) or 0
            walkaway_risk = context_json.get("walkaway_risk", False)
            competitor_pressure = context_json.get("competitor_pressure", False)
            quantity = context_json.get("mentioned_quantity", 1) or 1

            # Early stage negotiation
            if persistence <= 1:
                max_allowed_discount = min(dynamic_ceiling, 5.0)

            # Mid stage negotiation
            elif persistence <= 3:
                max_allowed_discount = min(dynamic_ceiling, 10.0)

            # Serious negotiation
            elif persistence <= 5:
                max_allowed_discount = min(dynamic_ceiling, 15.0)

            # High concessions require business justification
            else:
                approval_score = 0

                if walkaway_risk:
                    approval_score += 1

                if competitor_pressure:
                    approval_score += 1
        
                if quantity >= 5:
                    approval_score += 1

                # Require at least three commercial signals
                if approval_score >= 3:
                    max_allowed_discount = min(dynamic_ceiling, 25.0)
                else:
                    max_allowed_discount = min(dynamic_ceiling, 15.0)

        if current_customer_requested_discount > 0.0:
            effective_discount = max(
                last_discount_offered,
                min(effective_discount, current_customer_requested_discount)
            )

        effective_discount = min(
            effective_discount,
            max_allowed_discount
        )
        effective_discount = max(
            effective_discount,
            last_discount_offered
        )
        logger.info(
            "[NEGOTIATION STAGE] persistence=%d, max_allowed_discount=%.2f%%, "
            "effective_discount_before_cap=%.2f%%, final_discount=%.2f%%",
            persistence,
            max_allowed_discount,
            effective_discount,
            min(effective_discount, max_allowed_discount)
        )
        actual_offer_discount = max(0.0, effective_discount)
        actual_offer_price = list_price * (1.0 - actual_offer_discount / 100.0)

        if list_price > 0.0:
            if actual_offer_discount == 0.0:
                actual_offer_price = list_price
            if actual_offer_price <= 0.0:
                logger.critical(
                    "[CRITICAL] Offer price calculated as <= 0 (actual_offer_price=%.2f) "
                    "for product with list_price=%.2f. Discount was %.2f%%.",
                    actual_offer_price, list_price, actual_offer_discount
                )
                if NegotiationConfig.STRICT_NEGOTIATION_VALIDATION:
                    raise ValueError(
                        f"Negotiation validation failed: Calculated price {actual_offer_price} "
                        f"is less than or equal to zero for list price {list_price}."
                    )
                else:
                    actual_offer_price = list_price
                    actual_offer_discount = 0.0

        logger.info(
            f"Requested discount: {requested_discount_percent}%\n"
            f"Current customer requested discount: {current_customer_requested_discount}%\n\n"
            f"Raw optimizer discount: {raw_optimizer_discount}%\n"
            f"Dynamic ceiling: {dynamic_ceiling}%\n\n"
            f"Actual customer-facing offer: {actual_offer_discount}%\n"
            f"Price: ₹{actual_offer_price}\n\n"
            f"Winner strategy: {winner_strategy}"
        )

        logger.info(
            "[DIAGNOSTICS - STRATEGY OPTIMIZATION] Optimization complete. Winner: %s, Raw Discount: %.2f%%, Dynamic Ceiling: %.2f%%, Actual Discount: %.2f%%, Actual Price: %.2f",
            winner_strategy,
            raw_optimizer_discount,
            dynamic_ceiling,
            actual_offer_discount,
            actual_offer_price
        )

        return OptimizerResult(
            winning_strategy=winner_strategy,
            score=winner["optimizer_score"],
            optimization_mode=mode,
            optimizer_reasoning=optimizer_reasoning,
            winning_factors=winning_factors,
            risk_score=winner["average_risk_score"],
            confidence_score=winner["confidence_score"],
            all_rankings=rankings,
            inventory_explanation=inventory_explanation,
            actual_offer_discount=actual_offer_discount,
            actual_offer_price=actual_offer_price,
            current_discount_percent=actual_offer_discount,
            current_offer_price=actual_offer_price,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_strategy_score(
        simulation: SimulationOutput,
        confidence: float,
        mode: OptimizationMode,
        context_json: dict[str, Any] | None = None,
        requested_discount_percent: float = 0.0,
    ) -> float:

        if mode == OptimizationMode.MAX_PROFIT:
            base_score = simulation.average_expected_profit
        elif mode == OptimizationMode.MAX_CLOSE_RATE:
            base_score = simulation.average_close_probability
        elif mode == OptimizationMode.MAX_MARGIN:
            base_score = simulation.average_gross_margin_retention
        elif mode == OptimizationMode.MINIMIZE_DISCOUNT_GAP:
            # Primary objective: minimise the absolute gap between the customer's
            # requested discount and this strategy's offered discount.
            gap = abs(requested_discount_percent - simulation.discount_percent)
            # Normalise gap to [0, 1] over a 100pp range; invert so smaller gap -> higher score.
            normalised_gap = min(gap / 100.0, 1.0)
            base_score = (
                (1.0 - normalised_gap) * 0.60
                + simulation.average_close_probability * 0.25
                + (1.0 - simulation.average_risk_score) * 0.15
            )
        else:
            w = NegotiationConfig.SCORING_WEIGHTS
            scale = NegotiationConfig.SCORING_SCALE_FACTOR

            # Normalize expected value to a [0, 1] scale: close_probability * gross_margin_retention
            normalized_ev = simulation.average_close_probability * simulation.average_gross_margin_retention

            base_score = (
                normalized_ev * scale * w["expected_value"]
                + simulation.average_close_probability * scale * w["close_probability"]
                + (1.0 - simulation.average_risk_score) * scale * w["risk_score"]
                + confidence * scale * w["confidence"]
            )

            # ------------------------------------------------------------------
            # Negotiation Gap Penalty (BALANCED mode only)
            # Penalise strategies whose offered discount deviates significantly
            # from the customer's requested discount.  When the customer has made
            # repeated demands (persistence >= 2), the alignment weight is
            # boosted to honour the pressure signal.
            # ------------------------------------------------------------------
            if requested_discount_percent > 0.0:
                persistence = (context_json or {}).get("customer_persistence", 0) or 0
                gap_pp = abs(requested_discount_percent - simulation.discount_percent)
                # Normalise over the requested discount itself so the penalty is
                # proportional to the magnitude of the customer's ask.
                normalised_gap = min(gap_pp / max(requested_discount_percent, 1.0), 1.0)
                gap_penalty_weight = NegotiationConfig.DISCOUNT_GAP_PENALTY_WEIGHT
                max_penalty = NegotiationConfig.DISCOUNT_GAP_MAX_PENALTY

                # Extra alignment boost when customer_persistence >= 2
                if persistence >= 5:
                    gap_penalty_weight += NegotiationConfig.DISCOUNT_GAP_PERSISTENCE_ALIGNMENT_BOOST

                gap_penalty = normalised_gap * gap_penalty_weight * max_penalty * scale
                base_score -= gap_penalty

                logger.debug(
                    "[DISCOUNT_GAP] strategy=%s, requested=%.2f%%, offered=%.2f%%, "
                    "gap_pp=%.2f, normalised_gap=%.4f, gap_penalty_weight=%.4f, "
                    "gap_penalty=%.4f, base_score_after=%.4f, persistence=%d",
                    simulation.strategy_name,
                    requested_discount_percent,
                    simulation.discount_percent,
                    gap_pp,
                    normalised_gap,
                    gap_penalty_weight,
                    gap_penalty,
                    base_score,
                    persistence,
                )

        # Apply progressive negotiation flexibility boost & repeated strategy penalty
        if context_json:
            persistence = context_json.get("customer_persistence", 0) or 0
            quantity = context_json.get("mentioned_quantity", 1) or 1
            competitor_pressure = context_json.get("competitor_pressure", False)
            walkaway_risk = context_json.get("walkaway_risk", False)
            price_objection = context_json.get("price_objection", False)
            previous_strategies = context_json.get("previous_strategies", [])

            # Intermediate scoring trackers for diagnostics
            qty_boost = 0.0
            price_obj_boost = 0.0
            comp_boost = 0.0
            walkaway_boost = 0.0
            persist_boost = 0.0

            qty_penalty = 0.0
            price_obj_penalty = 0.0
            comp_penalty = 0.0
            walkaway_penalty = 0.0
            repetition_penalty = 0.0
            hardline_fatigue_penalty = 0.0
            bundle_fatigue_penalty = 0.0
            personalized_fatigue_penalty = 0.0
            
            # Volume concessions boost (square-root scaled, score-relative)
            import math
            if quantity > 1:
                volume_factor = (math.sqrt(quantity) - 1.0) * NegotiationConfig.VOLUME_BOOST_COEFFICIENT
                if simulation.strategy_name == "discount":
                    qty_boost += base_score * volume_factor * NegotiationConfig.VOLUME_BOOST_DISCOUNT_SCALE
                elif simulation.strategy_name == "personalized":
                    qty_boost += base_score * volume_factor * NegotiationConfig.VOLUME_BOOST_PERSONALIZED_SCALE
                elif simulation.strategy_name == "bundle":
                    qty_boost += base_score * volume_factor * NegotiationConfig.VOLUME_BOOST_BUNDLE_SCALE
                elif simulation.strategy_name == "hardline":
                    qty_penalty += base_score * volume_factor * NegotiationConfig.VOLUME_BOOST_HARDLINE_SCALE

            # Persistence boost
            if persistence >= 4:
                # Strong pressure signals favor discount/personalized over bundle/hardline
                if simulation.strategy_name == "discount":
                    persist_boost += base_score * NegotiationConfig.PERSISTENCE_PRESSURE_DISCOUNT_BOOST
                elif simulation.strategy_name == "personalized":
                    persist_boost += base_score * NegotiationConfig.PERSISTENCE_PRESSURE_PERSONALIZED_BOOST
                elif simulation.strategy_name == "bundle":
                    price_obj_penalty += base_score * NegotiationConfig.PERSISTENCE_PRESSURE_BUNDLE_PENALTY
                elif simulation.strategy_name == "hardline":
                    price_obj_penalty += base_score * NegotiationConfig.PERSISTENCE_PRESSURE_HARDLINE_PENALTY
            elif persistence > 0:
                if simulation.strategy_name == "discount":
                    persist_boost += base_score * (persistence * NegotiationConfig.PERSISTENCE_DISCOUNT_BOOST_FACTOR)
                elif simulation.strategy_name == "bundle":
                    persist_boost += base_score * (persistence * NegotiationConfig.PERSISTENCE_BUNDLE_BOOST_FACTOR)
                elif simulation.strategy_name == "personalized":
                    persist_boost += base_score * 0.05

            # Competitor pressure
            if competitor_pressure:
                if simulation.strategy_name == "discount":
                    comp_boost += base_score * NegotiationConfig.COMPETITOR_PRESSURE_DISCOUNT_BOOST
                elif simulation.strategy_name == "personalized":
                    comp_boost += base_score * NegotiationConfig.COMPETITOR_PRESSURE_PERSONALIZED_BOOST
                elif simulation.strategy_name == "bundle":
                    comp_penalty += base_score * NegotiationConfig.COMPETITOR_PRESSURE_BUNDLE_PENALTY
                elif simulation.strategy_name == "hardline":
                    comp_penalty += base_score * NegotiationConfig.COMPETITOR_PRESSURE_HARDLINE_PENALTY

            # Walkaway risk
            if walkaway_risk:
                if simulation.strategy_name == "discount":
                    walkaway_boost += base_score * NegotiationConfig.WALKAWAY_RISK_DISCOUNT_BOOST
                elif simulation.strategy_name == "personalized":
                    walkaway_boost += base_score * NegotiationConfig.WALKAWAY_RISK_PERSONALIZED_BOOST
                elif simulation.strategy_name == "bundle":
                    walkaway_penalty += base_score * NegotiationConfig.WALKAWAY_RISK_BUNDLE_PENALTY
                elif simulation.strategy_name == "hardline":
                    walkaway_penalty += base_score * NegotiationConfig.WALKAWAY_RISK_HARDLINE_PENALTY

            # Price objection
            if price_objection:
                if simulation.strategy_name == "discount":
                    price_obj_boost += base_score * NegotiationConfig.PRICE_OBJECTION_DISCOUNT_BOOST
                elif simulation.strategy_name == "personalized":
                    price_obj_boost += base_score * NegotiationConfig.PRICE_OBJECTION_PERSONALIZED_BOOST
                elif simulation.strategy_name == "bundle":
                    price_obj_penalty += base_score * NegotiationConfig.PRICE_OBJECTION_BUNDLE_PENALTY
                elif simulation.strategy_name == "hardline":
                    price_obj_penalty += base_score * NegotiationConfig.PRICE_OBJECTION_HARDLINE_PENALTY

            # Repeated strategy penalties
            if previous_strategies:
                repetition_factor = NegotiationConfig.STRATEGY_REPETITION_FACTOR
                occurrence_count = previous_strategies.count(simulation.strategy_name)
                if occurrence_count > 0:
                    factor_multiplier = NegotiationConfig.IMMEDIATE_PREDECESSOR_MULTIPLIER if previous_strategies[-1] == simulation.strategy_name else 1.0
                    persistence_mult = 1.0 + (persistence * 0.1)
                    repetition_penalty += base_score * repetition_factor * occurrence_count * factor_multiplier * persistence_mult

            # Repeated bundle exposures penalty (progressive exhaustion)
            if simulation.strategy_name == "bundle":
                bundle_offer_count = context_json.get("bundle_offer_count", 0) or 0
                bundle_factor = bundle_offer_count
                if persistence > 0:
                    bundle_factor += persistence * 1.0
                if bundle_factor > 0:
                    bundle_fatigue_penalty += (
                        base_score
                        * NegotiationConfig.BUNDLE_REPETITION_FACTOR
                        * (bundle_factor ** 1.8)
                    )

            # Personalized strategy fatigue penalties
            if simulation.strategy_name == "personalized":
                personalized_offer_count = context_json.get("personalized_offer_count", 0) or 0
                personalized_factor = personalized_offer_count
                if persistence > 0:
                    personalized_factor += persistence * 0.5
                if personalized_factor > 0:
                    personalized_fatigue_penalty += (
                        base_score
                        * NegotiationConfig.PERSONALIZED_REPETITION_FACTOR
                        * (personalized_factor ** 1.5)
                    )

            # Hardline fatigue penalties
            if simulation.strategy_name == "hardline":
                hardline_count = previous_strategies.count("hardline")
                if hardline_count > 0 or persistence > 0 or competitor_pressure:
                    fatigue_factor = NegotiationConfig.HARDLINE_FATIGUE_BASE * (hardline_count ** 1.3) if hardline_count > 0 else 0.0
                    if persistence > 0:
                        fatigue_factor += persistence * NegotiationConfig.HARDLINE_FATIGUE_PERSISTENCE_MULT
                    if competitor_pressure:
                        fatigue_factor += NegotiationConfig.HARDLINE_FATIGUE_COMPETITOR_MULT
                    if quantity > 1:
                        fatigue_factor += (math.sqrt(quantity) - 1.0) * NegotiationConfig.HARDLINE_FATIGUE_QUANTITY_MULT
                    hardline_fatigue_penalty += base_score * fatigue_factor

            # Combine all boosts and penalties
            boost = qty_boost + price_obj_boost + comp_boost + walkaway_boost + persist_boost
            penalty = qty_penalty + price_obj_penalty + comp_penalty + walkaway_penalty + repetition_penalty + hardline_fatigue_penalty + bundle_fatigue_penalty + personalized_fatigue_penalty

            final_score = base_score + boost - penalty

            # Detailed diagnostics logging for debugging optimizer rankings
            last_discount_offered = context_json.get("last_discount_offered", 0.0) or 0.0
            logger.info(
                "Ranking Diagnostics:\n"
                "  strategy_name: %s\n"
                "  base_score: %.4f\n"
                "  boost: %.4f\n"
                "  penalty: %.4f\n"
                "  final_score: %.4f\n"
                "  quantity: %d\n"
                "  customer_persistence: %d\n"
                "  competitor_pressure: %s\n"
                "  walkaway_risk: %s\n"
                "  last_discount_offered: %.2f%%\n"
                "  details: qty_boost=%.4f, price_obj_boost=%.4f, comp_boost=%.4f, walkaway_boost=%.4f, persist_boost=%.4f\n"
                "  penalties: qty_penalty=%.4f, price_obj_penalty=%.4f, comp_penalty=%.4f, walkaway_penalty=%.4f, repetition_penalty=%.4f, bundle_fatigue=%.4f, hardline_fatigue=%.4f, personalized_fatigue=%.4f",
                simulation.strategy_name,
                base_score,
                boost,
                penalty,
                final_score,
                quantity,
                persistence,
                competitor_pressure,
                walkaway_risk,
                last_discount_offered,
                qty_boost, price_obj_boost, comp_boost, walkaway_boost, persist_boost,
                qty_penalty, price_obj_penalty, comp_penalty, walkaway_penalty, repetition_penalty, bundle_fatigue_penalty, hardline_fatigue_penalty, personalized_fatigue_penalty
            )

            base_score = final_score

        return base_score
    
    @staticmethod
    def _identify_winning_factors(
        winner: dict[str, Any],
        rankings: list[dict[str, Any]],
    ) -> list[str]:
        """Identify the key factors that made the winner stand out."""

        factors: list[str] = []

        factors.append(
            f"Highest optimizer_score ({winner['optimizer_score']:,.2f})"
        )

        if winner["average_close_probability"] >= 0.5:
            factors.append(
                f"Strong close probability ({winner['average_close_probability']:.1%})"
            )
        elif winner["average_close_probability"] >= 0.3:
            factors.append(
                f"Moderate close probability ({winner['average_close_probability']:.1%})"
            )

        if winner["average_risk_score"] <= 0.3:
            factors.append(
                f"Low risk profile ({winner['average_risk_score']:.1%})"
            )
        elif winner["average_risk_score"] <= 0.5:
            factors.append(
                f"Acceptable risk level ({winner['average_risk_score']:.1%})"
            )
        else:
            factors.append(
                f"Elevated risk ({winner['average_risk_score']:.1%}) offset by high return"
            )

        if winner["confidence_score"] >= 0.8:
            factors.append(
                f"High rollout consistency (confidence {winner['confidence_score']:.1%})"
            )

        if len(rankings) >= 2:
            runner_up = rankings[1]
            margin = (
                winner["optimizer_score"]
                - runner_up["optimizer_score"]
            )
            if margin > 0:
                factors.append(
                    f"{margin:,.2f} advantage over runner-up "
                    f"({runner_up['strategy_name']})"
                )

        return factors

    @staticmethod
    def _build_reasoning(
        winner: dict[str, Any],
        rankings: list[dict[str, Any]],
        winning_factors: list[str] | None = None,
    ) -> str:
        """Build a deterministic, human-readable explanation."""

        lines: list[str] = [
            f"The '{winner['strategy_name']}' strategy is recommended with an "
            f"optimizer score of {winner['optimizer_score']:,.2f}.",
        ]

        lines.append(
            f"Expected profit of ₹{winner['average_expected_profit']:,.2f} "
            f"combined with a {winner['average_close_probability']:.1%} close "
            f"probability yields a raw expected value of "
            f"₹{winner['expected_value']:,.2f}."
        )

        if winner["confidence_score"] >= 0.8:
            lines.append(
                f"Rollout simulations showed high consistency "
                f"(confidence {winner['confidence_score']:.1%}), reinforcing "
                f"the reliability of this recommendation."
            )
        else:
            lines.append(
                f"Rollout consistency was moderate "
                f"(confidence {winner['confidence_score']:.1%}); consider "
                f"monitoring negotiation dynamics closely."
            )

        if winner["average_risk_score"] <= 0.3:
            lines.append(
                f"Risk is low ({winner['average_risk_score']:.1%}), indicating "
                f"the offer preserves healthy margins."
            )
        elif winner["average_risk_score"] <= 0.5:
            lines.append(
                f"Risk is moderate ({winner['average_risk_score']:.1%}) but "
                f"within acceptable bounds given the expected return."
            )
        else:
            lines.append(
                f"Risk is elevated ({winner['average_risk_score']:.1%}); the "
                f"recommendation stands because the expected profit offsets "
                f"the margin exposure."
            )

        if len(rankings) >= 2:
            runner_up = rankings[1]
            lines.append(
                f"Runner-up '{runner_up['strategy_name']}' scored "
                f"{runner_up['optimizer_score']:,.2f}."
            )

        return " ".join(lines)
