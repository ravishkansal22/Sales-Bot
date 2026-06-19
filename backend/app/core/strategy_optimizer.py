"""Deterministic strategy optimizer for Ghost Negotiator.

Ranks simulated strategies by Expected Value and selects a winner.
All reasoning is generated from data — **no LLM, no AI**.
"""

from __future__ import annotations

from typing import Any

from app.core.negotiation_scorer import NegotiationScorer
from app.core.config_layer import NegotiationConfig
from app.schemas.simulation import (
    OptimizationMode,
    OptimizerResult,
    SimulationOutput,
)


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

        Returns
        -------
        OptimizerResult
            The winning strategy with full reasoning, rankings, and
            confidence metadata.
        """

        if not simulations:
            raise ValueError("Cannot optimise an empty list of simulations.")

        # Determine repeated discount demands from history
        discount_demands = 0
        if history:
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
                )
            )

            # Apply repeated demand penalties/boosts to protect margins and guide bundles
            if discount_demands >= NegotiationConfig.REPEATED_DEMAND_THRESHOLD:
                if sim.strategy_name == "discount":
                    optimizer_score += NegotiationConfig.REPEATED_DEMAND_DISCOUNT_PENALTY
                elif sim.strategy_name == "bundle":
                    optimizer_score += NegotiationConfig.REPEATED_DEMAND_BUNDLE_BOOST

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

        winner: dict[str, Any] = rankings[0]

        # Determine inventory explanation dynamically based on stock levels
        if stock_quantity < NegotiationConfig.STOCK_CRITICAL:
            inventory_explanation = "Discount flexibility reduced due to critical inventory levels."
        elif stock_quantity < NegotiationConfig.STOCK_LOW:
            inventory_explanation = "Discount flexibility reduced due to limited inventory."
        elif stock_quantity >= NegotiationConfig.STOCK_MEDIUM:
            inventory_explanation = "Additional concessions possible due to excess inventory."
        else:
            inventory_explanation = "Standard discount flexibility applied under normal stock levels."

        # Populate explainability variables
        for rank in rankings:
            is_winner = rank["strategy_name"] == winner["strategy_name"]
            
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

        return OptimizerResult(
            winning_strategy=winner["strategy_name"],
            score=winner["optimizer_score"],
            optimization_mode=mode,
            optimizer_reasoning=optimizer_reasoning,
            winning_factors=winning_factors,
            risk_score=winner["average_risk_score"],
            confidence_score=winner["confidence_score"],
            all_rankings=rankings,
            inventory_explanation=inventory_explanation,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_strategy_score(
        simulation: SimulationOutput,
        confidence: float,
        mode: OptimizationMode,
    ) -> float:

        if mode == OptimizationMode.MAX_PROFIT:
            return simulation.average_expected_profit

        if mode == OptimizationMode.MAX_CLOSE_RATE:
            return simulation.average_close_probability

        if mode == OptimizationMode.MAX_MARGIN:
            return simulation.average_gross_margin_retention

        w = NegotiationConfig.SCORING_WEIGHTS
        scale = NegotiationConfig.SCORING_SCALE_FACTOR
        balanced_score = (
            simulation.average_expected_value * w["expected_value"]
            + simulation.average_close_probability * scale * w["close_probability"]
            + (1.0 - simulation.average_risk_score) * scale * w["risk_score"]
            + confidence * scale * w["confidence"]
        )

        return balanced_score
    
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
