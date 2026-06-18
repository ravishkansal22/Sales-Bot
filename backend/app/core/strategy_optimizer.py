"""Deterministic strategy optimizer for Ghost Negotiator.

Ranks simulated strategies by Expected Value and selects a winner.
All reasoning is generated from data — **no LLM, no AI**.
"""

from __future__ import annotations

from typing import Any

from app.core.negotiation_scorer import NegotiationScorer
from app.schemas.simulation import (
    OptimizationMode,
    OptimizerResult,
    SimulationOutput,
)


class StrategyOptimizer:
    """Select the optimal negotiation strategy from simulation results.

    The optimizer uses a single metric — **Expected Value** — to rank
    strategies.  Expected Value combines close probability with expected
    profit so that a strategy must be *both* likely to close *and*
    profitable to win.

    All outputs, including ``optimizer_reasoning``, are built
    deterministically from the numeric data.
    """

    @staticmethod
    def optimize(
       simulations: list[SimulationOutput],
       mode: OptimizationMode = OptimizationMode.BALANCED,
    ) -> OptimizerResult:
        """Rank strategies and return the winner.

        Parameters
        ----------
        simulations:
            One :class:`SimulationOutput` per strategy, each containing
            aggregated rollout results.

        Returns
        -------
        OptimizerResult
            The winning strategy with full reasoning, rankings, and
            confidence metadata.

        Raises
        ------
        ValueError
            If *simulations* is empty.

        Algorithm
        ---------
        ::

            For each simulation:
                expected_value = average_close_probability × average_expected_profit
                confidence     = NegotiationScorer.calculate_confidence_score(
                                     rollout_strategy_fits, rollout_risk_scores)
                # Confidence-adjusted EV penalises inconsistent rollouts:
                optimizer_score = StrategyOptimizer._calculate_strategy_score(
                   sim,
                   confidence,
                   mode,
                )

            Winner = strategy with highest optimizer_score.
        """

        if not simulations:
            raise ValueError("Cannot optimise an empty list of simulations.")

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

            # Confidence-adjusted EV: a strategy that is consistent
            # across rollouts is rewarded; an erratic one is penalised.
            optimizer_score: float = (
                StrategyOptimizer._calculate_strategy_score(
                    sim,
                    confidence,
                    mode,
                )
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
            })

        # ------------------------------------------------------------------
        # 2. Sort descending by optimizer_score
        # ------------------------------------------------------------------
        rankings.sort(
            key=lambda r: r["optimizer_score"],
            reverse=True,
        )

        winner: dict[str, Any] = rankings[0]

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

        balanced_score = (
            simulation.average_expected_value * 0.40
            + simulation.average_close_probability * 1000 * 0.30
            + (1.0 - simulation.average_risk_score) * 1000 * 0.20
            + confidence * 1000 * 0.10
        )

        return balanced_score
    
    @staticmethod
    def _identify_winning_factors(
        winner: dict[str, Any],
        rankings: list[dict[str, Any]],
    ) -> list[str]:
        """Identify the key factors that made the winner stand out.

        Returns
        -------
        list[str]
            Human-readable factor descriptions.
        """

        factors: list[str] = []

        # 1. Highest EV
        factors.append(
            f"Highest optimizer_score ({winner['optimizer_score']:,.2f})"
        )

        # 2. Close probability
        if winner["average_close_probability"] >= 0.5:
            factors.append(
                f"Strong close probability ({winner['average_close_probability']:.1%})"
            )
        elif winner["average_close_probability"] >= 0.3:
            factors.append(
                f"Moderate close probability ({winner['average_close_probability']:.1%})"
            )

        # 3. Risk
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

        # 4. Confidence
        if winner["confidence_score"] >= 0.8:
            factors.append(
                f"High rollout consistency (confidence {winner['confidence_score']:.1%})"
            )

        # 5. Margin vs. runner-up
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
            f"Expected profit of ${winner['average_expected_profit']:,.2f} "
            f"combined with a {winner['average_close_probability']:.1%} close "
            f"probability yields a raw expected value of "
            f"${winner['expected_value']:,.2f}."
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
