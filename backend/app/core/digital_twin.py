"""Digital twin builder for Ghost Negotiator.

Uses a structured-output LLM call to infer (or update) a customer's
behavioural profile from conversation analysis and history.
"""

from __future__ import annotations

from typing import Any

from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile
from app.services.llm.base import LLMProvider

_SYSTEM_PROMPT: str = """\
You are a customer behaviour modelling expert.  Given a conversation
analysis and optional history, you infer a **Digital Twin Profile** — a
set of normalised (0–1) behavioural scores that predict how a customer
will respond to negotiation strategies.

Return EXACTLY one JSON object matching the schema below.  Do not wrap
in markdown fences.

### Fields (all float, 0–1)

- **price_sensitivity** — How sensitive the customer is to price changes.
    0 = price is irrelevant, 1 = price is the dominant decision factor.
    Signals: explicit price complaints, competitor price comparisons,
    budget constraints, discount requests.

- **urgency** — How quickly the customer needs a solution.
    0 = no timeline pressure, 1 = critical/immediate need.
    Signals: deadline mentions, phrases like "ASAP", "go live Monday",
    frustrated sentiment about delays.

- **risk_aversion** — How cautious the customer is about making a
  wrong decision.
    0 = adventurous / early adopter, 1 = extremely cautious.
    Signals: requests for references, pilot programmes, guarantees,
    long evaluation cycles, "what if it doesn't work" language.

- **brand_loyalty** — How attached the customer is to YOUR brand/product.
    0 = no loyalty / commodity buyer, 1 = strong advocate.
    Signals: repeat customer, positive sentiment, mentions of past
    success, reluctance to switch even when cheaper alternatives exist.

- **decision_speed** — How quickly the customer tends to make decisions.
    0 = very slow / bureaucratic, 1 = fast / empowered buyer.
    Signals: short evaluation cycles, "let's do this", single
    decision-maker, no mention of approval chains.

### Guidelines

- If an **existing twin** is provided, treat it as a Bayesian prior.
  Nudge scores toward the new evidence but do not discard prior
  information unless the new signal is very strong.
- If no existing twin is provided, infer from scratch.
- History gives you longitudinal signal — early messages establish a
  baseline; recent messages may shift scores.
- When uncertain, default to 0.5 (neutral).

### Example

Conversation Analysis:
  objection_type=price, negotiation_intent=discount_seeking,
  urgency=0.7, sentiment=frustrated, stage=negotiation

→ {"price_sensitivity": 0.85, "urgency": 0.70, "risk_aversion": 0.40,
   "brand_loyalty": 0.30, "decision_speed": 0.55}
"""


class DigitalTwinBuilder:
    """Build or update a customer digital-twin profile using LLM inference.

    The builder wraps a single structured LLM call.  It is intentionally
    stateless — persistence is handled upstream by the service layer.

    Parameters
    ----------
    llm:
        An :class:`LLMProvider` instance capable of returning structured
        Pydantic models.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def build_twin(
        self,
        analysis: ConversationAnalysis,
        history: list[dict[str, Any]] | None = None,
        existing_twin: DigitalTwinProfile | None = None,
    ) -> DigitalTwinProfile:
        """Build or incrementally update a digital twin.

        Parameters
        ----------
        analysis:
            Structured analysis of the latest customer message.
        history:
            Optional list of prior conversation turns, each a dict with
            at least ``{"role": str, "content": str}``.
        existing_twin:
            Optional prior twin profile to use as a Bayesian prior.

        Returns
        -------
        DigitalTwinProfile
            The inferred (or updated) customer profile.
        """

        user_prompt = self._build_user_prompt(analysis, history, existing_twin)
        return await self._llm.generate(
            prompt=user_prompt,
            system_prompt=_SYSTEM_PROMPT,
            response_model=DigitalTwinProfile,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        analysis: ConversationAnalysis,
        history: list[dict[str, Any]] | None,
        existing_twin: DigitalTwinProfile | None,
    ) -> str:
        """Assemble the user prompt with all available context.

        Parameters
        ----------
        analysis:
            Current conversation analysis.
        history:
            Optional conversation history.
        existing_twin:
            Optional prior twin to update.

        Returns
        -------
        str
            The fully-formed user prompt.
        """

        parts: list[str] = []

        # --- existing twin -----------------------------------------------
        if existing_twin is not None:
            parts.append("## Existing Digital Twin (Bayesian Prior)")
            parts.append(f"- Price Sensitivity: {existing_twin.price_sensitivity:.2f}")
            parts.append(f"- Urgency: {existing_twin.urgency:.2f}")
            parts.append(f"- Risk Aversion: {existing_twin.risk_aversion:.2f}")
            parts.append(f"- Brand Loyalty: {existing_twin.brand_loyalty:.2f}")
            parts.append(f"- Decision Speed: {existing_twin.decision_speed:.2f}")
            parts.append("")

        # --- conversation history ----------------------------------------
        if history:
            parts.append("## Conversation History")
            for turn in history:
                role = turn.get("role", "unknown").capitalize()
                content = turn.get("message", turn.get("content", ""))
                parts.append(f"**{role}**: {content}")
            parts.append("")

        # --- current analysis --------------------------------------------
        parts.append("## Latest Conversation Analysis")
        parts.append(f"- Objection Type: {analysis.objection_type}")
        parts.append(f"- Negotiation Intent: {analysis.negotiation_intent}")
        parts.append(f"- Urgency: {analysis.urgency:.2f}")
        parts.append(f"- Sentiment: {analysis.sentiment}")
        parts.append(f"- Stage: {analysis.stage}")
        parts.append("")

        # --- instruction -------------------------------------------------
        parts.append(
            "Based on all the information above, return a single JSON "
            "object with the five Digital Twin Profile scores."
        )

        return "\n".join(parts)
