"""Discount negotiation strategy.

Focuses on offering percentage-based discounts to close price-sensitive
customers.  The LLM is instructed to reason about optimal discount levels
within the ``5–30%`` constraint window.
"""

from __future__ import annotations

from typing import Any

from app.core.strategies.base import Strategy
from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile


class DiscountStrategy(Strategy):
    """Offer a direct percentage discount to the customer.

    Best suited for customers with **high price sensitivity** and
    **high urgency** — they respond well to immediate monetary savings.
    Bundle value is always zero because this strategy relies solely on
    price reduction.
    """

    name: str = "discount"
    offer_type: str = "percentage_discount"

    def build_prompt(
        self,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        rollout_index: int,
    ) -> str:
        """Build a prompt instructing the LLM to craft a discount-oriented offer.

        The prompt provides the customer profile, conversation analysis, and
        deal economics so the LLM can reason about the *right* discount
        level.  Each rollout uses a slightly different framing to produce
        diverse reasoning paths.

        Parameters
        ----------
        twin:
            Customer behavioural profile (price sensitivity, urgency, etc.).
        analysis:
            Real-time conversation analysis (objection type, sentiment, etc.).
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
            "Consider the minimum effective discount that could close this deal.",
            "Explore a moderate discount level that balances margin and close probability.",
            "Consider the upper end of the discount range to maximise close probability.",
        ]
        hint = variance_hints[rollout_index % len(variance_hints)]

        return (
            f"You are a negotiation strategist specialising in discount-based offers.\n\n"
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
            f"- Deal Value: ${deal_value:,.2f}\n"
            f"- Cost Basis: ${cost_basis:,.2f}\n"
            f"- Available Margin: ${deal_value - cost_basis:,.2f}\n\n"
            f"## Your Task\n"
            f"Propose a **percentage discount** between 5% and 30%.\n"
            f"Do NOT propose any bundle add-ons (bundle_value must be 0).\n"
            f"{hint}\n\n"
            f"Provide detailed reasoning explaining why this discount level is "
            f"optimal for this customer profile and conversation context.\n\n"
            f"Return your response as:\n"
            f"- strategy_name: 'discount'\n"
            f"- offer_type: 'percentage_discount'\n"
            f"- discount_percent: <your proposed discount between 5 and 30>\n"
            f"- bundle_value: 0\n"
            f"- reasoning: <your detailed reasoning>\n"
        )

    def get_constraints(self) -> dict[str, Any]:
        """Return discount strategy constraints.

        Returns
        -------
        dict
            Enforced bounds: discount 5–30%, no bundles.
        """

        return {
            "min_discount_percent": 5.0,
            "max_discount_percent": 30.0,
            "min_bundle_value": 0.0,
            "max_bundle_value": 0.0,
        }
