"""Digital twin builder for Ghost Negotiator.

Uses a structured-output LLM call to infer (or update) a customer's
behavioural profile from conversation analysis and history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile
from app.services.llm.base import LLMProvider

if TYPE_CHECKING:
    from app.services.customer_profile_builder import CustomerHistorySummary

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
- If customer purchase history summary is provided, use it to ground the behavioral scores:
  - Frequent purchaser / High total spend -> Higher brand_loyalty.
  - High return rate -> Higher risk_aversion.
  - Repeated discount purchases / low average spend -> Higher price_sensitivity.
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
        customer_history_summary: CustomerHistorySummary | None = None,
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
        customer_history_summary:
            Optional customer purchase history statistics.

        Returns
        -------
        DigitalTwinProfile
            The inferred (or updated) customer profile.
        """
        # Initialize with prior or neutral baseline
        if existing_twin is not None:
            price_sens = existing_twin.price_sensitivity
            urgency = existing_twin.urgency
            risk_av = existing_twin.risk_aversion
            brand_loy = existing_twin.brand_loyalty
            dec_speed = existing_twin.decision_speed
        else:
            price_sens = 0.5
            urgency = 0.5
            risk_av = 0.5
            brand_loy = 0.5
            dec_speed = 0.5

        # 1. Customer history summary adjustments
        if customer_history_summary:
            segment = getattr(customer_history_summary, "segment", "STANDARD").upper()
            if segment in ("VIP", "STRATEGIC"):
                price_sens -= 0.15
                brand_loy += 0.20
            elif segment in ("BARGAIN HUNTER", "BARGAIN"):
                price_sens += 0.20
                brand_loy -= 0.10
            elif segment == "CHURN RISK":
                price_sens += 0.10
                brand_loy -= 0.15

            total_spend = getattr(customer_history_summary, "total_spend", 0.0)
            if total_spend > 50000.0:
                price_sens -= 0.10
                brand_loy += 0.10
            elif total_spend > 10000.0:
                price_sens -= 0.05

            return_rate = getattr(customer_history_summary, "return_rate", 0.0)
            if return_rate > 0.10:
                risk_av += 0.10

            rep_discounts = getattr(customer_history_summary, "repeated_discount_purchases_count", 0)
            if rep_discounts > 2:
                price_sens += 0.15

        # 2. Conversation analysis adjustments
        if analysis:
            obj_type = getattr(analysis, "objection_type", "none").lower()
            if obj_type in ("price", "budget"):
                price_sens += 0.15
                urgency += 0.05
            elif obj_type == "competitor":
                price_sens += 0.10
                brand_loy -= 0.10
            elif obj_type == "trust":
                risk_av += 0.15
                brand_loy -= 0.10
            elif obj_type == "value":
                risk_av += 0.10
                price_sens += 0.05
            elif obj_type == "feature_gap":
                risk_av += 0.10

            intent = getattr(analysis, "negotiation_intent", "").lower()
            if intent == "discount_seeking":
                price_sens += 0.15
            elif intent == "closing":
                dec_speed += 0.15
                urgency += 0.15
            elif intent == "stalling":
                dec_speed -= 0.15
                risk_av += 0.10
            elif intent == "competitive_leverage":
                price_sens += 0.10
                brand_loy -= 0.10
            elif intent == "relationship_building":
                brand_loy += 0.05

            anal_urgency = getattr(analysis, "urgency", 0.5)
            # Blend urgency with latest analysis urgency
            urgency = 0.6 * urgency + 0.4 * anal_urgency

            sentiment = getattr(analysis, "sentiment", "neutral").lower()
            if sentiment in ("negative", "frustrated"):
                price_sens += 0.05
                risk_av += 0.05
            elif sentiment in ("positive", "excited"):
                brand_loy += 0.05
                dec_speed += 0.05

            stage = getattr(analysis, "stage", "").lower()
            if stage == "decision":
                dec_speed += 0.10
                urgency += 0.05
            elif stage in ("negotiation", "objection"):
                price_sens += 0.05

        # Clamp values to [0, 1]
        price_sens = max(0.0, min(1.0, price_sens))
        urgency = max(0.0, min(1.0, urgency))
        risk_av = max(0.0, min(1.0, risk_av))
        brand_loy = max(0.0, min(1.0, brand_loy))
        dec_speed = max(0.0, min(1.0, dec_speed))

        # Build verified profile
        return DigitalTwinProfile(
            price_sensitivity=round(price_sens, 2),
            urgency=round(urgency, 2),
            risk_aversion=round(risk_av, 2),
            brand_loyalty=round(brand_loy, 2),
            decision_speed=round(dec_speed, 2),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        analysis: ConversationAnalysis,
        history: list[dict[str, Any]] | None,
        existing_twin: DigitalTwinProfile | None,
        customer_history_summary: CustomerHistorySummary | None = None,
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
        customer_history_summary:
            Optional customer purchase history summary.

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

        # --- customer history summary -------------------------------------
        if customer_history_summary:
            parts.append("## Customer Purchase History Summary")
            parts.append(f"- Total Orders: {customer_history_summary.total_orders}")
            parts.append(f"- Total Spend: ${customer_history_summary.total_spend:,.2f}")
            parts.append(f"- Average Spend: ${customer_history_summary.average_spend:,.2f}")
            parts.append(f"- Return Rate: {customer_history_summary.return_rate:.1%}")
            parts.append(f"- Frequent Categories: {', '.join(customer_history_summary.frequent_categories)}")
            parts.append(f"- Repeated Discount Purchases: {customer_history_summary.repeated_discount_purchases_count}")
            parts.append(f"- Customer Segment: {customer_history_summary.segment}")
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
