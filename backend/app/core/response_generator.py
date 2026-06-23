"""Response generator for Ghost Negotiator.

Produces customer-facing natural-language responses and internal
reasoning notes using an LLM.  Called **after** the strategy optimizer
has selected a winner — the LLM never sees raw simulation data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import (
    DigitalTwinProfile,
    OptimizerResult,
    SimulationOutput,
)
from app.services.llm.base import LLMProvider

# ------------------------------------------------------------------
# Internal response model (not exposed in schemas)
# ------------------------------------------------------------------

class _LLMResponseOutput(BaseModel):
    """Structured output from the response-generation LLM call."""

    customer_response: str = Field(
        ...,
        description=(
            "A natural, persuasive message to send to the customer.  "
            "Must NOT contain any internal data, scores, or simulation "
            "details."
        ),
    )
    internal_reasoning: str = Field(
        ...,
        description=(
            "Internal-only reasoning explaining the response approach, "
            "what signals were addressed, and what the next best step is."
        ),
    )


_SYSTEM_PROMPT: str = """\
You are a senior B2B sales representative crafting a response to a
customer during an active negotiation.  You have been given a
recommended strategy, alternative runner-up strategies, and context about the customer.

### Rules

1. **Never reveal** internal scores, simulation data, probabilities,
   profit margins, cost basis, or any backend metrics.
2. The customer-facing response must be **natural, professional, and
   persuasive** — like a real salesperson would write.
3. Align your response with the winning strategy, but also **use the alternative runner-up strategies** to construct a creative and helpful counter-offer.
4. If the customer's request cannot be met by the winning strategy (e.g., they ask for a discount that exceeds what the winning strategy offers):
   - Never end the conversation with only a rejection. If the request exceeds limits, explain the constraint and then offer the best available alternative (discount, bundles, quantity pricing, payment terms, accessories, etc.).
   - All proposed concessions and alternatives MUST come from the simulation details and runner-up strategies provided in your prompt. Do NOT make up or hardcode unapproved concessions.
5. Keep the customer response concise (2–4 paragraphs max).
6. The internal reasoning should explain your thinking for the sales
   team — what you addressed, what you intentionally avoided, and
   your recommended next step.
"""


class ResponseGenerator:
    """Generate customer responses aligned with the optimised strategy.

    The generator receives only high-level strategy metadata (strategy
    name, reasoning, winning factors) — it **never** sees raw rollout
    scores, financial metrics, or close probabilities.

    Parameters
    ----------
    llm:
        An :class:`LLMProvider` instance capable of returning structured
        Pydantic models.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def generate(
        self,
        winner: OptimizerResult,
        simulation: SimulationOutput,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        runner_ups: list[SimulationOutput] | None = None,
        list_price: float | None = None,
        customer_message: str | None = None,
        customer_persistence: int = 0,
        last_topic: str | None = None,
        previous_strategy: str | None = None,
        quantity: int = 1,
    ) -> tuple[str, str]:
        """Generate a customer-facing response and internal reasoning.

        Parameters
        ----------
        winner:
            The optimizer's selected strategy and reasoning.
        simulation:
            The simulation output for the winning strategy (used only
            for its ``reasoning`` and ``offer_type`` — numeric metrics
            are NOT forwarded to the LLM).
        twin:
            The customer's digital-twin profile.
        analysis:
            The most recent conversation analysis.
        runner_ups:
            Optional list of top runner-up simulation outputs.
        list_price:
            The list price of the product under negotiation.
        customer_message:
            The raw text of the customer's last message.

        Returns
        -------
        tuple[str, str]
            ``(customer_response, internal_reasoning)``

            * ``customer_response`` — the text to send to the customer.
            * ``internal_reasoning`` — sales-team-only notes.
        """

        user_prompt = self._build_user_prompt(winner, simulation, twin, analysis, runner_ups, list_price)
        
        try:
            result: _LLMResponseOutput = await self._llm.generate(
                prompt=user_prompt,
                system_prompt=_SYSTEM_PROMPT,
                response_model=_LLMResponseOutput,
            )
            customer_response = result.customer_response
            internal_reasoning = result.internal_reasoning
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("LLM response generation failed: %s. Using fallback formatter.", exc)
            customer_response = ""
            internal_reasoning = f"Deterministic response generated due to LLM error: {exc!s}"

        # Centralize formatting: ALWAYS run final output through the SalesResponseFormatter
        from app.core.sales_response_formatter import SalesResponseFormatter
        final_customer_response = SalesResponseFormatter.format_response(
            winning_strategy=winner.winning_strategy,
            discount_percent=simulation.discount_percent,
            bundle_concessions=simulation.concessions,
            runner_ups=[r.strategy_name for r in runner_ups] if runner_ups else [],
            list_price=list_price if list_price is not None else 0.0,
            sub_intent=analysis.sub_intent,
            customer_message=customer_message,
            llm_draft=customer_response,
            customer_persistence=customer_persistence,
            last_topic=last_topic,
            previous_strategy=previous_strategy,
            quantity=quantity,
        )

        return final_customer_response, internal_reasoning

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        winner: OptimizerResult,
        simulation: SimulationOutput,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        runner_ups: list[SimulationOutput] | None = None,
        list_price: float | None = None,
    ) -> str:
        """Assemble the user prompt — deliberately omitting raw metrics.

        Only strategy-level context is included.  No close probabilities,
        no financial metrics, no rollout-level scores.

        Parameters
        ----------
        winner:
            Optimizer result.
        simulation:
            Winning strategy's simulation output.
        twin:
            Customer profile.
        analysis:
            Conversation analysis.
        runner_ups:
            Top runner-up strategies.
        list_price:
            The list price of the product.

        Returns
        -------
        str
            The fully-formed user prompt.
        """

        parts: list[str] = []

        # --- recommended strategy ----------------------------------------
        parts.append("## Recommended Strategy")
        parts.append(f"- Strategy: {winner.winning_strategy}")
        parts.append(f"- Offer Type: {simulation.offer_type}")
        if list_price is not None:
            parts.append(f"- List Price: ₹{list_price:,.2f}".replace(".00", ""))
        if simulation.discount_percent > 0:
            parts.append(f"- Discount: {simulation.discount_percent:.1f}%")
            if list_price is not None:
                final_price = list_price * (1.0 - simulation.discount_percent / 100.0)
                savings = list_price - final_price
                parts.append(f"- Effective Price: ₹{final_price:,.2f}".replace(".00", ""))
                parts.append(f"- Total Savings: ₹{savings:,.2f}".replace(".00", ""))
        if simulation.concessions:
            parts.append(f"- Concessions: {', '.join(simulation.concessions)}")
        parts.append(f"- Strategy Reasoning: {simulation.reasoning}")
        parts.append(f"- Winning Factors: {', '.join(winner.winning_factors)}")
        parts.append("")

        # --- alternative strategies / runner-ups --------------------------
        if runner_ups:
            parts.append("## Alternative Strategies (Runner-ups)")
            for i, r_sim in enumerate(runner_ups, 1):
                parts.append(f"### Runner-up {i}: {r_sim.strategy_name}")
                parts.append(f"- Offer Type: {r_sim.offer_type}")
                if r_sim.discount_percent > 0:
                    parts.append(f"- Discount: {r_sim.discount_percent:.1f}%")
                    if list_price is not None:
                        r_final_price = list_price * (1.0 - r_sim.discount_percent / 100.0)
                        parts.append(f"- Effective Price: ₹{r_final_price:,.2f}".replace(".00", ""))
                if r_sim.concessions:
                    parts.append(f"- Concessions: {', '.join(r_sim.concessions)}")
                parts.append(f"- Strategy Reasoning: {r_sim.reasoning}")
            parts.append("")

        # --- customer context --------------------------------------------
        parts.append("## Customer Profile")
        parts.append(f"- Price Sensitivity: {twin.price_sensitivity:.2f}")
        parts.append(f"- Urgency: {twin.urgency:.2f}")
        parts.append(f"- Risk Aversion: {twin.risk_aversion:.2f}")
        parts.append(f"- Brand Loyalty: {twin.brand_loyalty:.2f}")
        parts.append(f"- Decision Speed: {twin.decision_speed:.2f}")
        parts.append("")

        # --- conversation context ----------------------------------------
        parts.append("## Current Conversation Context")
        parts.append(f"- Customer Objection: {analysis.objection_type}")
        parts.append(f"- Negotiation Intent: {analysis.negotiation_intent}")
        if analysis.sub_intent:
            parts.append(f"- Sub-Intent: {analysis.sub_intent}")
        parts.append(f"- Sentiment: {analysis.sentiment}")
        parts.append(f"- Urgency: {analysis.urgency:.2f}")
        parts.append(f"- Stage: {analysis.stage}")
        parts.append("")

        # --- instruction -------------------------------------------------
        parts.append(
            "Craft a customer-facing response and internal reasoning note "
            "following the system prompt rules.  Return as JSON with "
            "'customer_response' and 'internal_reasoning' fields."
        )

        return "\n".join(parts)

