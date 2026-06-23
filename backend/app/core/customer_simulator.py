from __future__ import annotations

from typing import Any

from app.schemas.simulation import (
    CustomerReaction,
    DigitalTwinProfile,
    LLMStrategyOutput,
)
from app.schemas.chat import ConversationAnalysis


class CustomerSimulator:
    """
    Deterministic customer reaction simulator.

    Uses Digital Twin attributes and Conversation Analysis to estimate how
    a customer would react to a proposed negotiation strategy.

    No LLM calls.
    No external services.
    Pure deterministic logic.
    """

    @staticmethod
    def simulate_reaction(
        twin: DigitalTwinProfile,
        strategy_output: LLMStrategyOutput,
        analysis: ConversationAnalysis | None = None,
        context_json: dict[str, Any] | None = None,
    ) -> CustomerReaction:
        """
        Simulate customer reaction to a strategy.
        """

        strategy = strategy_output.strategy_name.lower().strip()

        trust_delta = 0.0
        buying_intent_delta = 0.0
        engagement_delta = 0.0
        objection_delta = 0.0

        is_negotiating = False
        if analysis is not None:
            intent = getattr(analysis, "intent_type", "").lower().strip()
            req_discount = getattr(analysis, "requested_discount", 0.0)
            if intent == "negotiation" or req_discount > 0.0:
                is_negotiating = True

        simulated_response = (
            "The customer acknowledges the proposal and continues the discussion."
        )

        if strategy == "discount":
            if is_negotiating:
                trust_delta = 0.15
                buying_intent_delta = 0.25
                objection_delta = -0.15
                engagement_delta = 0.15
                simulated_response = (
                    "The customer responds positively to the discount concession, "
                    "showing increased trust and buying intent."
                )
            else:
                buying_intent_delta += twin.price_sensitivity * 0.20
                engagement_delta += twin.urgency * 0.10
                objection_delta -= twin.price_sensitivity * 0.15
                trust_delta += (1.0 - twin.brand_loyalty) * 0.05
                simulated_response = (
                    "The discount reduces pricing concerns and the customer "
                    "shows increased willingness to continue discussions."
                )

        elif strategy == "hardline":
            if is_negotiating:
                trust_delta = -0.15
                buying_intent_delta = -0.25
                objection_delta = 0.20
                engagement_delta = -0.15
                simulated_response = (
                    "The customer is seeking concessions and is disappointed by the firm price position, "
                    "reducing their trust and intent to buy."
                )
            else:
                trust_delta += twin.brand_loyalty * 0.10
                buying_intent_delta += twin.brand_loyalty * 0.05
                objection_delta += twin.price_sensitivity * 0.10
                engagement_delta -= twin.price_sensitivity * 0.05
                simulated_response = (
                    "The customer respects the firm position but may continue "
                    "to challenge pricing if cost remains a concern."
                )

        elif strategy == "bundle":
            if is_negotiating:
                trust_delta = 0.10
                buying_intent_delta = 0.10
                objection_delta = -0.10
                engagement_delta = 0.10
                simulated_response = (
                    "The customer welcomes the value-add bundle offer, "
                    "improving the outlook of the deal."
                )
            else:
                buying_intent_delta += (1.0 - twin.risk_aversion) * 0.10
                engagement_delta += twin.brand_loyalty * 0.10
                objection_delta -= (1.0 - twin.risk_aversion) * 0.10
                trust_delta += twin.brand_loyalty * 0.05
                simulated_response = (
                    "The customer sees additional value in the offer and "
                    "becomes more engaged in evaluating the proposal."
                )

        elif strategy == "personalized":
            if is_negotiating:
                trust_delta = 0.12
                buying_intent_delta = 0.20
                objection_delta = -0.12
                engagement_delta = 0.12
                simulated_response = (
                    "The customer responds positively to the personalized offer tailoring to their specific situation."
                )
            else:
                trust_delta += 0.10
                buying_intent_delta += 0.10
                engagement_delta += 0.10
                objection_delta -= 0.10
                simulated_response = (
                    "The customer feels understood and responds positively "
                    "to the tailored recommendation."
                )

        elif strategy == "quantity":
            if is_negotiating:
                trust_delta = 0.12
                buying_intent_delta = 0.18
                objection_delta = -0.10
                engagement_delta = 0.10
            else:
                trust_delta = 0.05
                buying_intent_delta = 0.05
            simulated_response = "The customer is receptive to quantity-based concessions."

        elif strategy in ("payment terms", "payment_terms", "payment"):
            if is_negotiating:
                trust_delta = 0.10
                buying_intent_delta = 0.10
                objection_delta = -0.05
                engagement_delta = 0.08
            else:
                trust_delta = 0.03
                buying_intent_delta = 0.03
            simulated_response = "The customer is receptive to payment terms concessions."

        else:
            buying_intent_delta += 0.02
            engagement_delta += 0.02
            simulated_response = (
                "The customer remains engaged but does not show a strong reaction."
            )

        # Apply pressure-based adjustments based on context_json
        persistence = 0
        competitor_pressure = False
        walkaway_risk = False
        if context_json:
            persistence = context_json.get("customer_persistence", 0) or 0
            competitor_pressure = context_json.get("competitor_pressure", False)
            walkaway_risk = context_json.get("walkaway_risk", False)

        pressure_factor = 0.0
        if competitor_pressure:
            pressure_factor += 0.5
        if walkaway_risk:
            pressure_factor += 0.8
        if persistence > 0:
            pressure_factor += persistence * 0.25

        if pressure_factor > 0.0:
            if strategy == "hardline":
                trust_delta -= pressure_factor * 0.15
                buying_intent_delta -= pressure_factor * 0.20
                objection_delta += pressure_factor * 0.15
                engagement_delta -= pressure_factor * 0.10
            elif strategy == "bundle":
                trust_delta -= pressure_factor * 0.05
                buying_intent_delta -= pressure_factor * 0.08
                objection_delta += pressure_factor * 0.05
            elif strategy == "discount":
                trust_delta += pressure_factor * 0.10
                buying_intent_delta += pressure_factor * 0.15
                objection_delta -= pressure_factor * 0.10
                engagement_delta += pressure_factor * 0.05

        return CustomerReaction(
            simulated_response=simulated_response,
            trust_delta=round(max(-1.0, min(1.0, trust_delta)), 4),
            buying_intent_delta=round(
                max(-1.0, min(1.0, buying_intent_delta)),
                4,
            ),
            engagement_delta=round(
                max(-1.0, min(1.0, engagement_delta)),
                4,
            ),
            objection_delta=round(
                max(-1.0, min(1.0, objection_delta)),
                4,
            ),
        )

