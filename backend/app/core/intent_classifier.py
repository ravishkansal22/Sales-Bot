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
    """Route user query to appropriate pipeline intent."""
    msg_lower = message.lower()
    
    # 0. Product explanation check
    explanation_keywords = [
        "how does it work",
        "explain",
        "what is this",
        "how is it used",
        "working principle",
        "usage",
        "how does this product function"
    ]
    if any(kw in msg_lower for kw in explanation_keywords):
        return IntentClassification(
            intent="product_explanation",
            confidence=1.0,
            reasoning="Product explanation keyword detected.",
            target_product_ids=[],
            sub_intent=None
        )

    # 1. Competitor leverage check
    competitor_keywords = [
        "competitor",
        "cheaper",
        "other vendor",
        "market price",
        "alternative quote",
        "amazon",
        "flipkart",
        "matching price",
        "competitor offer"
    ]
    if any(kw in msg_lower for kw in competitor_keywords):
        return IntentClassification(
            intent="negotiation",
            confidence=1.0,
            reasoning="Competitor-related keyword detected.",
            target_product_ids=[],
            sub_intent="competitor_leverage"
        )
        
    # 1b. Negotiation check
    negotiation_keywords = [
        "discount", "offer", "cheaper", "price", "cost", "quantity", "bulk", "units", "buy", "deal",
        "pricing", "expensive", "cheap", "negotiate", "rate", "off"
    ]
    has_percent = "%" in msg_lower or any(re.search(rf"\b{re.escape(kw)}\b", msg_lower) for kw in negotiation_keywords)
    if has_percent:
        return IntentClassification(
            intent="negotiation",
            confidence=0.95,
            reasoning="Negotiation/commercial keyword or percentage detected.",
            target_product_ids=[],
            sub_intent=None
        )

    # 2. Commercial terms / warranty check
    commercial_keywords = [
        "warranty",
        "guarantee",
        "support",
        "service",
        "replacement",
        "coverage"
    ]
    if any(kw in msg_lower for kw in commercial_keywords):
        return IntentClassification(
            intent="commercial_terms",
            confidence=1.0,
            reasoning="Commercial-related keyword (warranty/guarantee/support/service/replacement/coverage) detected.",
            target_product_ids=[],
            sub_intent=None
        )

    # 3. Product comparison check
    if any(kw in msg_lower for kw in ["compare", "vs", "versus", "difference between", "better than"]):
        return IntentClassification(
            intent="product_comparison",
            confidence=0.95,
            reasoning="Product comparison keyword detected.",
            target_product_ids=[]
        )

    # 4. Product question check
    general_spec_keywords = [
        "what specifications", "general specifications", "what specs", "list specifications", "list specs",
        "available specifications", "available specs", "share specifications", "share specs", "show specifications",
        "show specs", "tell me about the specifications", "details on specifications", "details on specs"
    ]
    is_general_specs = any(phrase in msg_lower for phrase in general_spec_keywords) or (
        ("specification" in msg_lower or "specs" in msg_lower or "features" in msg_lower or "details" in msg_lower)
    )
    
    qa_keywords = [
        "dimension", "dimensions", "size", "height", "width", "depth", "length", 
        "specifications", "spec", "specs", "material", "made of", "weight", "features", "details", "compatible", 
        "color", "colour", "shade", "hue", "cpu", "chip", "chipset", "processor", "ram", "storage", "capacity", 
        "memory", "mah", "battery capacity", "battery life", "battery", "megapixels", "mp", "resolution", "lens", "camera",
        "page", "pages", "page count", "isbn", "serial", "model"
    ]
    
    if is_general_specs or any(kw in msg_lower for kw in qa_keywords):
        return IntentClassification(
            intent="product_question",
            confidence=0.95,
            reasoning="Product question/specification keyword detected.",
            target_product_ids=[]
        )

    # 5. Product discovery check
    if any(kw in msg_lower for kw in ["find", "search", "show me", "catalog", "what products", "looking for", "recommend"]):
        return IntentClassification(
            intent="product_discovery",
            confidence=0.95,
            reasoning="Product discovery keyword detected.",
            target_product_ids=[]
        )

    # 6. Cart management check
    if any(kw in msg_lower for kw in ["lock deal", "add to cart", "show cart", "view cart", "procurement cart", "remove", "reopen"]):
        return IntentClassification(
            intent="cart_management",
            confidence=0.95,
            reasoning="Cart management keyword detected.",
            target_product_ids=[]
        )

    # 7. Checkout check
    if any(kw in msg_lower for kw in ["checkout", "finalize purchase", "buy", "place order"]):
        return IntentClassification(
            intent="checkout",
            confidence=0.95,
            reasoning="Checkout keyword detected.",
            target_product_ids=[]
        )

    # 8. General check
    general_patterns = [r"\bhello\b", r"\bhi\b", r"\bthanks\b", r"\bthank\s+you\b", r"\bbye\b"]
    negotiation_keywords = ["discount", "price", "expensive", "cost", "offer", "cheap", "rate", "off", "value", "negotiate", "pricing"]
    if any(re.search(pat, msg_lower) for pat in general_patterns) and not any(kw in msg_lower for kw in negotiation_keywords):
        return IntentClassification(
            intent="general",
            confidence=0.95,
            reasoning="General greeting/thanks keyword detected.",
            target_product_ids=[]
        )

    # Default to negotiation
    return IntentClassification(
        intent="negotiation",
        confidence=0.95,
        reasoning="Default classification rule mapping to negotiation.",
        target_product_ids=[]
    )
