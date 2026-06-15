from __future__ import annotations

from app.schemas.simulation import (
    CustomerReaction,
    DigitalTwinProfile,
    LLMStrategyOutput,
)

class CustomerSimulator:
    """
    Deterministic customer reaction simulator.

    Uses Digital Twin attributes to estimate how a customer
    would react to a proposed negotiation strategy.

    No LLM calls.
    No external services.
    Pure deterministic logic.
    """

    @staticmethod
    def simulate_reaction(
        twin: DigitalTwinProfile,
        strategy_output: LLMStrategyOutput,
    ) -> CustomerReaction:
        """
        Simulate customer reaction to a strategy.
        """

        strategy = strategy_output.strategy_name.lower().strip()

        trust_delta = 0.0
        buying_intent_delta = 0.0
        engagement_delta = 0.0
        objection_delta = 0.0

        simulated_response = (
            "The customer acknowledges the proposal and continues the discussion."
        )

        if strategy == "discount":
            buying_intent_delta += twin.price_sensitivity * 0.20
            engagement_delta += twin.urgency * 0.10
            objection_delta -= twin.price_sensitivity * 0.15
            trust_delta += (1.0 - twin.brand_loyalty) * 0.05

            simulated_response = (
                "The discount reduces pricing concerns and the customer "
                "shows increased willingness to continue discussions."
            )

        elif strategy == "hardline":
            trust_delta += twin.brand_loyalty * 0.10
            buying_intent_delta += twin.brand_loyalty * 0.05
            objection_delta += twin.price_sensitivity * 0.10
            engagement_delta -= twin.price_sensitivity * 0.05
    
            simulated_response = (
                "The customer respects the firm position but may continue "
                "to challenge pricing if cost remains a concern."
            )

        elif strategy == "bundle":
            buying_intent_delta += (1.0 - twin.risk_aversion) * 0.10
            engagement_delta += twin.brand_loyalty * 0.10
            objection_delta -= (1.0 - twin.risk_aversion) * 0.10
            trust_delta += twin.brand_loyalty * 0.05

            simulated_response = (
                "The customer sees additional value in the offer and "
                "becomes more engaged in evaluating the proposal."
            )

        elif strategy == "personalized":
            trust_delta += 0.10
            buying_intent_delta += 0.10
            engagement_delta += 0.10
            objection_delta -= 0.10

            simulated_response = (
            "The customer feels understood and responds positively "
            "to the tailored recommendation."
        )

        else:
            buying_intent_delta += 0.02
            engagement_delta += 0.02

            simulated_response = (
                "The customer remains engaged but does not show a strong reaction."
            )

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
