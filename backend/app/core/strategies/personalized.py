"""Personalized negotiation strategy.

Tailors the offer based on the complete digital-twin customer profile.
Unlike the single-axis strategies (discount, hardline, bundle), this
strategy can use *any* combination of discounts and bundles.
"""

from __future__ import annotations

from typing import Any

from app.core.strategies.base import Strategy
from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile


class PersonalizedStrategy(Strategy):
    """Craft a fully tailored offer using all digital-twin dimensions.

    This strategy has the widest constraint window — it can combine a
    moderate discount with a value-add bundle, offer just one, or even
    hold firm if the twin profile warrants it.  It is the most flexible
    strategy and typically produces the most creative LLM outputs.
    """

    name: str = "personalized"
    offer_type: str = "tailored_offer"

    def build_prompt(
        self,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        rollout_index: int,
    ) -> str:
        """Build a prompt for a fully personalised offer.

        The LLM is given full latitude to mix and match discounts and
        bundles.  The prompt stresses that the response must be uniquely
        adapted to the customer's behavioural profile.

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

        max_bundle = deal_value * 0.15  # Slightly tighter cap for mixed offers

        variance_hints: list[str] = [
            (
                "Lean towards the customer's dominant trait.  If they are "
                "price-sensitive, favour a discount.  If they value features, "
                "favour a bundle."
            ),
            (
                "Craft a balanced hybrid: a small discount combined with a "
                "targeted value-add that addresses the customer's primary objection."
            ),
            (
                "Think creatively — consider non-traditional concessions such "
                "as flexible payment terms, phased delivery, or outcome-based "
                "guarantees that align with the customer's risk profile."
            ),
        ]
        hint = variance_hints[rollout_index % len(variance_hints)]

        # Summarise dominant traits for the LLM to key off of.
        traits: dict[str, float] = {
            "Price Sensitivity": twin.price_sensitivity,
            "Urgency": twin.urgency,
            "Risk Aversion": twin.risk_aversion,
            "Brand Loyalty": twin.brand_loyalty,
            "Decision Speed": twin.decision_speed,
        }
        dominant_trait: str = max(traits, key=traits.get)  # type: ignore[arg-type]
        weakest_trait: str = min(traits, key=traits.get)  # type: ignore[arg-type]

        return (
            f"You are a senior negotiation strategist crafting a PERSONALISED offer.\n\n"
            f"## Customer Profile\n"
            f"- Price Sensitivity: {twin.price_sensitivity:.2f} (0=low, 1=high)\n"
            f"- Urgency: {twin.urgency:.2f}\n"
            f"- Risk Aversion: {twin.risk_aversion:.2f}\n"
            f"- Brand Loyalty: {twin.brand_loyalty:.2f}\n"
            f"- Decision Speed: {twin.decision_speed:.2f}\n"
            f"- **Dominant Trait**: {dominant_trait} ({traits[dominant_trait]:.2f})\n"
            f"- **Weakest Trait**: {weakest_trait} ({traits[weakest_trait]:.2f})\n\n"
            f"## Conversation Analysis\n"
            f"- Objection Type: {analysis.objection_type}\n"
            f"- Negotiation Intent: {analysis.negotiation_intent}\n"
            f"- Urgency: {analysis.urgency:.2f}\n"
            f"- Sentiment: {analysis.sentiment}\n"
            f"- Stage: {analysis.stage}\n\n"
            f"## Deal Economics\n"
            f"- Deal Value: ${deal_value:,.2f}\n"
            f"- Cost Basis: ${cost_basis:,.2f}\n"
            f"- Available Margin: ${deal_value - cost_basis:,.2f}\n"
            f"- Max Bundle Cost: ${max_bundle:,.2f}\n\n"
            f"## Your Task\n"
            f"Design a **personalised offer** uniquely adapted to this customer.\n"
            f"You may use any combination of:\n"
            f"  - Percentage discount (0–25%)\n"
            f"  - Value-add bundle ($0–${max_bundle:,.2f} internal cost)\n"
            f"  - Or hold firm with no concessions if warranted\n\n"
            f"{hint}\n\n"
            f"Your reasoning MUST explicitly reference the customer's traits "
            f"and explain how the offer is tailored to their profile.\n\n"
            f"Return your response as:\n"
            f"- strategy_name: 'personalized'\n"
            f"- offer_type: 'tailored_offer'\n"
            f"- discount_percent: <0–25>\n"
            f"- bundle_value: <0–{max_bundle:,.2f}>\n"
            f"- reasoning: <your detailed, personalised reasoning>\n"
        )

    def get_constraints(self, context_json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return personalized strategy constraints.

        Parameters
        ----------
        context_json:
            Optional negotiation session state context.

        Returns
        -------
        dict
            Wide window: discount 0–25%, bundle 0–∞ (capped dynamically).
        """

        return {
            "min_discount_percent": 0.0,
            "max_discount_percent": 25.0,
            "min_bundle_value": 0.0,
            "max_bundle_value": float("inf"),  # Dynamic cap applied at runtime
        }
