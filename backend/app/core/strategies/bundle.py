"""Bundle negotiation strategy.

Offers value-add bundles (e.g., extended support, training, premium
features) instead of reducing the price.  No percentage discounts are
applied — the customer receives *more* rather than paying *less*.
"""

from __future__ import annotations

from typing import Any

from app.core.strategies.base import Strategy
from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile


class BundleStrategy(Strategy):
    """Offer value-add bundles instead of price concessions.

    Best suited for customers with **moderate price sensitivity** who value
    features and are **not overly risk-averse** (bundles add complexity).
    High brand loyalty also helps — loyal customers are open to expanding
    their investment in a trusted vendor.
    """

    name: str = "bundle"
    offer_type: str = "value_bundle"

    def build_prompt(
        self,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        rollout_index: int,
    ) -> str:
        """Build a prompt instructing the LLM to craft a bundle-based offer.

        The LLM proposes value-add components (training, support, premium
        features) with an associated internal cost.  The prompt ensures no
        discount is offered — only incremental value.

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

        max_bundle = deal_value * 0.20  # Cap bundle cost at 20% of deal value

        variance_hints: list[str] = [
            "Propose a lean bundle with minimal cost that adds clear customer value.",
            "Propose a moderate bundle that demonstrates significant added value.",
            "Propose a premium bundle package that makes the offer feel like a VIP experience.",
        ]
        hint = variance_hints[rollout_index % len(variance_hints)]

        return (
            f"You are a negotiation strategist specialising in value-add bundling.\n\n"
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
            f"- Maximum Bundle Cost: ${max_bundle:,.2f}\n\n"
            f"## Your Task\n"
            f"Propose a **value-add bundle** (e.g., extended support, training, "
            f"premium features) instead of any discount.\n"
            f"Do NOT propose any percentage discount (discount_percent must be 0).\n"
            f"The bundle_value represents your INTERNAL COST to provide the bundle "
            f"(not the customer-facing value).  Keep it between $1 and ${max_bundle:,.2f}.\n"
            f"{hint}\n\n"
            f"Provide detailed reasoning explaining what the bundle includes, "
            f"why it addresses the customer's concerns, and how it creates "
            f"perceived value greater than its cost.\n\n"
            f"Return your response as:\n"
            f"- strategy_name: 'bundle'\n"
            f"- offer_type: 'value_bundle'\n"
            f"- discount_percent: 0\n"
            f"- bundle_value: <your proposed bundle cost>\n"
            f"- reasoning: <your detailed reasoning>\n"
        )

    def get_constraints(self, context_json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return bundle strategy constraints.

        Parameters
        ----------
        context_json:
            Optional negotiation session state context.

        Returns
        -------
        dict
            No discount allowed.  Bundle value must be positive (the
            upper bound is enforced dynamically in
            :meth:`SimulationEngine._clamp_output`).
        """

        return {
            "min_discount_percent": 0.0,
            "max_discount_percent": 0.0,
            "min_bundle_value": 1.0,
            "max_bundle_value": float("inf"),  # Dynamic cap applied at runtime
        }
