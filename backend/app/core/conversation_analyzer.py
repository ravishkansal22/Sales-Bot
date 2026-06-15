"""Conversation analyser for Ghost Negotiator.

Uses a structured-output LLM call to extract negotiation signals from
customer messages.  The LLM returns a
:class:`~app.schemas.chat.ConversationAnalysis` model.
"""

from __future__ import annotations

from typing import Any

from app.schemas.chat import ConversationAnalysis
from app.services.llm.base import LLMProvider

_SYSTEM_PROMPT: str = """\
You are an expert B2B sales conversation analyst.  Your job is to analyse
a customer's latest message (and optionally prior conversation history)
and extract structured negotiation intelligence.

Return EXACTLY one JSON object matching the schema below.  Do not wrap
in markdown fences.

### Fields

- **objection_type** (str): The primary objection the customer is raising.
  Choose ONE from:
    "price"          – customer thinks the price is too high
    "value"          – customer questions whether the product is worth it
    "competitor"     – customer is comparing to a competitor
    "timing"         – customer says now is not the right time
    "authority"      – customer needs approval from someone else
    "budget"         – customer's budget is constrained
    "feature_gap"    – customer needs a feature that is missing
    "trust"          – customer lacks confidence in the vendor
    "none"           – no clear objection detected

- **negotiation_intent** (str): What the customer is trying to achieve.
  Choose ONE from:
    "discount_seeking"   – wants a lower price
    "value_exploration"  – wants to understand value better
    "competitive_leverage" – using a competitor as leverage
    "stalling"           – delaying a decision
    "closing"            – ready or nearly ready to buy
    "information_gathering" – still in research mode
    "relationship_building" – building rapport, not transactional yet

- **urgency** (float, 0-1): How urgently the customer needs a solution.
  0 = no urgency at all, 1 = critical/immediate need.

- **sentiment** (str): Overall emotional tone.  Choose ONE from:
    "positive", "neutral", "negative", "frustrated", "anxious", "excited"

- **stage** (str): Current negotiation stage.  Choose ONE from:
    "discovery"      – early exploration
    "evaluation"     – actively comparing options
    "negotiation"    – discussing terms
    "decision"       – about to decide
    "objection"      – actively pushing back
    "closed_won"     – deal is done
    "closed_lost"    – customer has walked away

### Examples

Customer: "Your competitor is offering 20% less for basically the same thing."
→ {"objection_type": "competitor", "negotiation_intent": "competitive_leverage",
   "urgency": 0.6, "sentiment": "neutral", "stage": "negotiation"}

Customer: "We love the product but our budget was just cut in half."
→ {"objection_type": "budget", "negotiation_intent": "discount_seeking",
   "urgency": 0.5, "sentiment": "anxious", "stage": "objection"}

Customer: "Can we get this wrapped up by Friday?  We need to go live Monday."
→ {"objection_type": "none", "negotiation_intent": "closing",
   "urgency": 0.95, "sentiment": "excited", "stage": "decision"}
"""


class ConversationAnalyzer:
    """Analyse customer messages to extract negotiation intelligence.

    Uses a single LLM call with structured output to produce a
    :class:`ConversationAnalysis` — no chain-of-thought, no multi-step
    reasoning, just a fast classification pass.

    Parameters
    ----------
    llm:
        An :class:`LLMProvider` instance capable of returning structured
        Pydantic models.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def analyze(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> ConversationAnalysis:
        """Analyse a customer message for negotiation signals.

        Parameters
        ----------
        message:
            The customer's latest message text.
        history:
            Optional list of prior conversation turns, each a dict with
            at least ``{"role": str, "content": str}``.

        Returns
        -------
        ConversationAnalysis
            Structured analysis of the message.
        """

        user_prompt = self._build_user_prompt(message, history)
        return await self._llm.generate(
            prompt=user_prompt,
            system_prompt=_SYSTEM_PROMPT,
            response_model=ConversationAnalysis,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        message: str,
        history: list[dict[str, Any]] | None,
    ) -> str:
        """Assemble the user prompt with optional conversation history.

        Parameters
        ----------
        message:
            Latest customer message.
        history:
            Optional prior turns.

        Returns
        -------
        str
            The fully-formed user prompt.
        """

        parts: list[str] = []

        if history:
            parts.append("## Conversation History")
            for turn in history:
                role = turn.get("role", "unknown").capitalize()
                content = turn.get("message", turn.get("content", ""))
                parts.append(f"**{role}**: {content}")
            parts.append("")  # blank line

        parts.append("## Latest Customer Message")
        parts.append(message)
        parts.append("")
        parts.append(
            "Analyse the latest message above.  Return a single JSON "
            "object matching the ConversationAnalysis schema."
        )

        return "\n".join(parts)
