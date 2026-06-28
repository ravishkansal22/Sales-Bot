from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field

class IntentClassification(BaseModel):
    """Pydantic model for user message intent routing classification."""

    intent: str = Field(
        ...,
        description="one of: product_discovery, product_question, product_comparison, negotiation, cart_management, checkout, general, commercial_terms, product_explanation",
    )
    confidence: float = Field(..., description="confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="reasoning for this classification")
    target_product_ids: list[str] = Field(
        default_factory=list,
        description="Names or IDs of products mentioned in the query"
    )
    sub_intent: str | None = Field(
        default=None,
        description="Optional sub-intent for fine-grained routing, e.g. competitor_leverage"
    )


async def classify_intent(
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> IntentClassification:

    msg_lower = message.lower().strip()

    # ==========================================================
    # Acceptance Intent
    # ==========================================================

    acceptance_keywords = [
        "accepted",
        "accept",
        "okay done",
        "done",
        "works for me",
        "sounds good",
        "looks good",
        "go ahead",
        "proceed",
        "proceed with this",
        "confirm",
        "confirmed",
        "finalize it",
        "close the deal",
        "move forward",
        "lock it",
        "book it",
        "i agree",
        "agreed"
    ]

    if any(keyword in msg_lower for keyword in acceptance_keywords):
        return IntentClassification(
            intent="acceptance",
            confidence=0.98,
            reasoning="Customer acceptance signal detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Greetings
    # ==========================================================

    general_patterns = [
        r"\bhello\b",
        r"\bhi\b",
        r"\bhey\b",
        r"\bthanks\b",
        r"\bthank\s+you\b",
        r"\bbye\b"
    ]

    if any(re.search(pattern, msg_lower) for pattern in general_patterns):
        return IntentClassification(
            intent="general",
            confidence=0.95,
            reasoning="Greeting or courtesy expression detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Product Explanation
    # ==========================================================

    explanation_keywords = [
        "how does it work",
        "explain",
        "what is this",
        "how is it used",
        "working principle",
        "usage",
        "how does this product function"
    ]

    if any(keyword in msg_lower for keyword in explanation_keywords):
        return IntentClassification(
            intent="product_explanation",
            confidence=0.95,
            reasoning="Product explanation request detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Sales Advice (BEFORE product_question and negotiation)
    # Captures recommendation, value, and purchase-advice questions.
    # ==========================================================

    sales_advice_phrases = [
        "why should i buy",
        "why buy this",
        "why buy the",
        "would you recommend",
        "do you recommend",
        "is it worth",
        "worth it",
        "worth the money",
        "worth the price",
        "should i buy",
        "is this a good buy",
        "good buy",
        "good investment",
        "why choose this",
        "why choose the",
        "what makes this stand out",
        "what makes it stand out",
        "why do customers buy",
        "recommend this",
        "is this worth",
        "is it a good",
    ]

    if any(phrase in msg_lower for phrase in sales_advice_phrases):
        return IntentClassification(
            intent="sales_advice",
            confidence=0.97,
            reasoning="Sales advice or recommendation question detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Extended Warranty (BEFORE product_question)
    # Captures warranty upsell / additional coverage requests.
    # ==========================================================

    extended_warranty_phrases = [
        "extended warranty",
        "additional warranty",
        "extra warranty",
        "warranty extension",
        "add warranty",
        "more warranty",
        "additional year of warranty",
        "extra year of warranty",
        "extra year warranty",
        "support package",
        "service plan",
        "maintenance plan",
        "additional year",
    ]

    if any(phrase in msg_lower for phrase in extended_warranty_phrases):
        return IntentClassification(
            intent="extended_warranty",
            confidence=0.97,
            reasoning="Extended warranty or service plan request detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Product Questions
    # ==========================================================

    product_question_keywords = [
        "specification",
        "specifications",
        "spec",
        "specs",
        "feature",
        "features",
        "details",
        "information",
        "info",
        "tell me about",
        "what does it have",
        "what info",
        "what information",
        "what is included",
        "color",
        "colour",
        "processor",
        "cpu",
        "chip",
        "chipset",
        "ram",
        "memory",
        "storage",
        "battery",
        "battery life",
        "display",
        "screen",
        "camera",
        "weight",
        "dimensions",
        "size",
        "material",
        "compatibility",
        "connectivity",
        "warranty"
    ]

    question_starters = [
        "what",
        "which",
        "does",
        "is",
        "can",
        "how many"
    ]

    if (
        any(keyword in msg_lower for keyword in product_question_keywords)
        or (
            any(msg_lower.startswith(starter) for starter in question_starters)
            and "discount" not in msg_lower
            and "%" not in msg_lower
            and "better" not in msg_lower
        )
    ):
        return IntentClassification(
            intent="product_question",
            confidence=0.95,
            reasoning="Product information request detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Product Comparison
    # ==========================================================

    comparison_keywords = [
        "compare",
        "vs",
        "versus",
        "difference",
        "better than"
    ]

    if any(keyword in msg_lower for keyword in comparison_keywords):
        return IntentClassification(
            intent="product_comparison",
            confidence=0.95,
            reasoning="Comparison request detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Competitor Leverage
    # ==========================================================

    competitor_keywords = [
        "competitor",
        "other vendor",
        "market price",
        "alternative quote",
        "amazon",
        "flipkart",
        "matching price",
        "competitor offer"
    ]

    if any(keyword in msg_lower for keyword in competitor_keywords):
        return IntentClassification(
            intent="negotiation",
            confidence=0.98,
            reasoning="Competitor leverage detected.",
            target_product_ids=[],
            sub_intent="competitor_leverage"
        )



    # ==========================================================
    # Negotiation
    # ==========================================================

    negotiation_keywords = [
        "discount",
        "offer",
        "cheaper",
        "price",
        "cost",
        "pricing",
        "expensive",
        "cheap",
        "negotiate",
        "rate",
        "bulk",
        "quantity",
        "units",
        "better"
    ]

    has_percentage = bool(re.search(r"\d+\s*%", msg_lower))

    if (
        has_percentage
        or any(keyword in msg_lower for keyword in negotiation_keywords)
    ):
        return IntentClassification(
            intent="negotiation",
            confidence=0.95,
            reasoning="Negotiation request detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Cart Management
    # ==========================================================

    cart_keywords = [
        "add to cart",
        "show cart",
        "view cart",
        "remove from cart",
        "lock deal",
        "reopen negotiation"
    ]

    if any(keyword in msg_lower for keyword in cart_keywords):
        return IntentClassification(
            intent="cart_management",
            confidence=0.95,
            reasoning="Cart management action detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Checkout
    # ==========================================================

    checkout_keywords = [
        "checkout",
        "place order",
        "finalize purchase",
        "complete purchase"
    ]

    if any(keyword in msg_lower for keyword in checkout_keywords):
        return IntentClassification(
            intent="checkout",
            confidence=0.95,
            reasoning="Checkout intent detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Discovery
    # ==========================================================

    discovery_keywords = [
        "find",
        "search",
        "show me",
        "catalog",
        "recommend",
        "available products"
    ]

    if any(keyword in msg_lower for keyword in discovery_keywords):
        return IntentClassification(
            intent="product_discovery",
            confidence=0.95,
            reasoning="Product discovery request detected.",
            target_product_ids=[]
        )

    # ==========================================================
    # Default
    # ==========================================================

    return IntentClassification(
        intent="general",
        confidence=0.60,
        reasoning="No strong intent signal detected.",
        target_product_ids=[]
    )