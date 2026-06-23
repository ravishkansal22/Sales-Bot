from __future__ import annotations

import re
from typing import List, Optional

class SalesResponseFormatter:
    """Centralized formatting system for Ghost Negotiator responses.

    Ensures consistent pricing presentation, clean commercial terms,
    correct concessions representation, and deterministic output.
    """

    @staticmethod
    def _generate_cooperative_phrasing(
        persistence: int,
        quantity: int,
        previous_strategy: Optional[str],
        objection_type: Optional[str],
    ) -> str:
        # Acknowledge budget/objection if present
        obj_lower = (objection_type or "").lower()
        if "price" in obj_lower or "budget" in obj_lower or "expensive" in obj_lower:
            obj_phrase = "I understand that budget alignment is a priority."
        elif "competitor" in obj_lower:
            obj_phrase = "I recognize the competitive options you are evaluating."
        else:
            obj_phrase = "I appreciate you sharing your perspective."

        # Adapt phrasing for quantity
        if quantity > 10:
            qty_phrase = f"Since you're considering a larger commitment of {quantity} units, we have additional commercial flexibility available."
        else:
            qty_phrase = "I want to ensure we find a mutually beneficial package that works for your requirements."

        # Adapt phrasing for persistence
        if persistence > 2:
            persistence_phrase = "I recognize we need to go further to make this work, and I am committed to finding a creative solution."
        elif persistence > 0:
            persistence_phrase = "Let's explore how we can optimize the overall value of this agreement."
        else:
            persistence_phrase = "I am keen to structure terms that set us up for a successful partnership."

        return f"{obj_phrase} {qty_phrase} {persistence_phrase}"

    @staticmethod
    def format_response(
        winning_strategy: str,
        discount_percent: float,
        bundle_concessions: List[str],
        runner_ups: List[str],
        list_price: float,
        sub_intent: Optional[str] = None,
        customer_message: Optional[str] = None,
        llm_draft: Optional[str] = None,
        customer_persistence: int = 0,
        last_topic: Optional[str] = None,
        previous_strategy: Optional[str] = None,
        quantity: int = 1,
    ) -> str:
        # 1. Base calculations
        list_price_val = float(list_price) if list_price is not None else 0.0
        final_price_val = list_price_val * (1.0 - float(discount_percent) / 100.0)
        savings_val = list_price_val - final_price_val

        list_price_str = f"₹{list_price_val:,.2f}".replace(".00", "")
        final_price_str = f"₹{final_price_val:,.2f}".replace(".00", "")
        savings_str = f"₹{savings_val:,.2f}".replace(".00", "")

        # 2. Concession formatting helper
        def simplify_concession(c: str) -> str:
            c_clean = c.strip()
            if "Support SLA" in c_clean:
                return "extended support"
            elif "Payment Terms" in c_clean:
                return "flexible payment terms"
            elif "Delivery" in c_clean:
                return "priority delivery"
            return c_clean.lower()

        # Simplified bullet points for standard concessions list
        bullet_points = []
        for c in bundle_concessions:
            simp = simplify_concession(c)
            # Capitalize first letter for bullet points
            bullet_points.append(f"• {simp[0].upper() + simp[1:]}")
        concessions_bullet_str = "\n\n".join(bullet_points)

        # Inline concessions joined with 'and' for competitor leverage response
        inline_concessions = [simplify_concession(c) for c in bundle_concessions]
        if len(inline_concessions) > 1:
            concessions_inline_str = ", ".join(inline_concessions[:-1]) + " and " + inline_concessions[-1]
        elif len(inline_concessions) == 1:
            concessions_inline_str = inline_concessions[0]
        else:
            concessions_inline_str = "additional commercial terms"

        # 3. Choose template based on intent and strategy
        strategy_lower = winning_strategy.lower()

        if sub_intent == "competitor_leverage":
            # Extract percentage from customer message if available
            competitor_pct = None
            if customer_message:
                match = re.search(r"(\d+(?:\.\d+)?)\s*%", customer_message)
                if match:
                    competitor_pct = f"{match.group(1)}%"

            if competitor_pct:
                match_phrase = f"matching {competitor_pct} directly"
            else:
                match_phrase = "matching that pricing directly"

            cooperative_intro = SalesResponseFormatter._generate_cooperative_phrasing(
                customer_persistence, quantity, previous_strategy, "competitor"
            )
            response = (
                f"{cooperative_intro}\n\n"
                f"While I may not be able to reach {competitor_pct or 'that pricing'} directly, I can secure the current offer at {final_price_str} "
                f"and include {concessions_inline_str}.\n\n"
                f"If quantity requirements increase, additional flexibility becomes possible."
            )
            return response

        elif strategy_lower == "commercial_terms" or sub_intent == "commercial_terms":
            return (
                "Standard manufacturer warranty applies, and extended support packages "
                "are available as part of our commercial offering."
            )

        elif strategy_lower == "bundle" and concessions_bullet_str:
            cooperative_intro = SalesResponseFormatter._generate_cooperative_phrasing(
                customer_persistence, quantity, previous_strategy, sub_intent or last_topic
            )
            if discount_percent > 0:
                response = (
                    f"{cooperative_intro}\n\n"
                    f"I can immediately secure the price at {final_price_str}, providing a saving of {savings_str} "
                    f"while preserving all support and commercial terms. In addition, I can include:\n\n"
                    f"{concessions_bullet_str}\n\n"
                    f"If you're considering larger quantities, we may be able to structure additional flexibility."
                )
            else:
                response = (
                    f"{cooperative_intro}\n\n"
                    f"I may not be able to reach your requested price level immediately, but I can improve the overall commercial package. "
                    f"Along with standard pricing, I can include:\n\n"
                    f"{concessions_bullet_str}\n\n"
                    f"If you're considering larger quantities, we may be able to structure additional flexibility."
                )
            return response

        elif strategy_lower == "discount" and discount_percent > 0:
            intros = []
            if sub_intent == "competitor_leverage":
                intros.append("I understand the market alternatives you're considering, and I can improve the commercial terms.")
            elif quantity > 1:
                intros.append("For an order of this size, we have additional flexibility available.")
            elif customer_persistence > 1:
                intros.append("Given your continued interest, I can improve the pricing further.")
            else:
                intros.append("I can immediately secure a better commercial price.")

            intro_str = " ".join(intros)
            response = (
                f"{intro_str}\n\n"
                f"Here are the revised commercial terms I can offer you:\n"
                f"• List Price: {list_price_str}\n"
                f"• Revised Price: {final_price_str}\n"
                f"• Total Savings: {savings_str}\n\n"
                f"All standard support, quality guarantees, and delivery terms remain fully preserved."
            )
            return response

        else:
            # Fallback/Default strategies (e.g. hardline)
            cooperative_intro = SalesResponseFormatter._generate_cooperative_phrasing(
                customer_persistence, quantity, previous_strategy, sub_intent or last_topic
            )
            if discount_percent > 0:
                response = (
                    f"{cooperative_intro}\n\n"
                    f"I can immediately secure it at {final_price_str}, providing a saving of {savings_str} "
                    f"while preserving all support and commercial terms.\n\n"
                    f"If you're considering larger quantities, we may be able to structure additional flexibility."
                )
            else:
                response = (
                    f"{cooperative_intro}\n\n"
                    f"I can secure it at {final_price_str} under our standard commercial terms.\n\n"
                    f"If you're considering larger quantities, we may be able to structure additional flexibility."
                )
            return response
