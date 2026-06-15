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
recommended strategy and context about the customer.

### Rules

1. **Never reveal** internal scores, simulation data, probabilities,
   profit margins, cost basis, or any backend metrics.
2. The customer-facing response must be **natural, professional, and
   persuasive** — like a real salesperson would write.
3. Align your response with the winning strategy:
   - "discount" → present the discount as a special / limited offer.
   - "hardline" → reinforce the value, justify the price.
   - "bundle" → highlight the added value / extras included.
   - "personalized" → use the specific factors from the reasoning.
4. Address the customer's objection / sentiment directly.
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

        Returns
        -------
        tuple[str, str]
            ``(customer_response, internal_reasoning)``

            * ``customer_response`` — the text to send to the customer.
            * ``internal_reasoning`` — sales-team-only notes.
        """

        user_prompt = self._build_user_prompt(winner, simulation, twin, analysis)
        result: _LLMResponseOutput = await self._llm.generate(
            prompt=user_prompt,
            system_prompt=_SYSTEM_PROMPT,
            response_model=_LLMResponseOutput,
        )
        return result.customer_response, result.internal_reasoning

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        winner: OptimizerResult,
        simulation: SimulationOutput,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
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
        if simulation.discount_percent > 0:
            parts.append(f"- Discount: {simulation.discount_percent:.1f}%")
        if simulation.bundle_value > 0:
            parts.append(f"- Bundle Value Added: ${simulation.bundle_value:,.2f}")
        parts.append(f"- Strategy Reasoning: {simulation.reasoning}")
        parts.append(f"- Winning Factors: {', '.join(winner.winning_factors)}")
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
