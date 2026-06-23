"""Hardline negotiation strategy.

Holds the price firm and emphasises the value proposition.  No discounts,
no bundles — the strategy relies on articulating why the product is worth
the asking price.
"""

from __future__ import annotations

from typing import Any

from app.core.strategies.base import Strategy
from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile


class HardlineStrategy(Strategy):
    """Hold price firm and emphasise value over concessions.

    Best suited for customers with **high brand loyalty** and **low price
    sensitivity**.  These buyers care about quality, reputation, and
    long-term outcomes more than short-term savings.
    """

    name: str = "hardline"
    offer_type: str = "hold_firm"

    def build_prompt(
        self,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        rollout_index: int,
    ) -> str:
        """Build a prompt instructing the LLM to craft a value-focused, no-discount response.

        The LLM is told to justify the current price using ROI arguments,
        competitive differentiation, and relationship-building language.
        Rollout variance is introduced through different angles of
        justification.

        Parameters
        ----------
        twin:
            Customer behavioural profile.
        analysis:
            Real-time conversation analysis.
        deal_value:
            Full list-price value of the deal (USD).
        cost_basis:
            Internal cost to fulfil the deal (USD).
        rollout_index:
            Zero-based rollout index for prompt variance.

        Returns
        -------
        str
            A fully-formed prompt string.
        """

        variance_hints: list[str] = [
            "Emphasise long-term ROI and total cost of ownership advantages.",
            "Focus on competitive differentiation and unique capabilities.",
            "Highlight risk reduction and reliability of the proven solution.",
        ]
        hint = variance_hints[rollout_index % len(variance_hints)]

        return (
            f"You are a negotiation strategist specialising in value-based selling.\n\n"
            f"## Customer Profile\n"
            f"- Price Sensitivity: {twin.price_sensitivity:.2f} (0=low, 1=high)\n"
            f"- Urgency: {twin.urgency:.2f}\n"
            f"- Risk Aversion: {twin.risk_aversion:.2f}\n"
            f"- Brand Loyalty: {twin.brand_loyalty:.2f}\n"
            f"- Decision Speed: {twin.decision_speed:.2f}\n\n"
            f"## Conversation Analysis\n"
            f"- Objection Type: {analysis.objection_type}\n"
            f"- Negotiation Intent: {analysis.negotiation_intent}\n"
            f"- Urgency: {analysis.urgency:.2f}\n"
            f"- Sentiment: {analysis.sentiment}\n"
            f"- Stage: {analysis.stage}\n\n"
            f"## Deal Economics\n"
            f"- Deal Value: ${deal_value:,.2f}\n\n"
            f"## Your Task\n"
            f"You must HOLD the price firm.  No discount.  No bundle add-ons.\n"
            f"Your job is to craft compelling reasoning for why the current "
            f"price is justified and represents excellent value.\n"
            f"{hint}\n\n"
            f"Explain why conceding on price would actually hurt the customer "
            f"(e.g., reduced service levels, slower support, fewer features).\n\n"
            f"Return your response as:\n"
            f"- strategy_name: 'hardline'\n"
            f"- offer_type: 'hold_firm'\n"
            f"- discount_percent: 0\n"
            f"- bundle_value: 0\n"
            f"- reasoning: <your detailed reasoning>\n"
        )

    def get_constraints(self, context_json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return hardline strategy constraints.

        Parameters
        ----------
        context_json:
            Optional negotiation session state context.

        Returns
        -------
        dict
            Both discount and bundle are locked to zero.
        """

        return {
            "min_discount_percent": 0.0,
            "max_discount_percent": 0.0,
            "min_bundle_value": 0.0,
            "max_bundle_value": 0.0,
        }
