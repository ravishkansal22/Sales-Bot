from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_specification import ProductSpecification
from app.services.llm.base import LLMProvider
from app.services.product_resolver import ProductResolver
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)


class IntentClassification(BaseModel):
    """Pydantic model for user message intent routing classification."""

    intent: str = Field(
        ...,
        description="one of: product_discovery, product_question, product_comparison, negotiation, cart_management, checkout, general",
    )
    confidence: float = Field(..., description="confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="reasoning for this classification")
    target_product_ids: list[str] = Field(
        default_factory=list,
        description="Names or IDs of products mentioned in the query"
    )


_INTENT_SYSTEM_PROMPT = """\
You are an expert sales intent router for a B2B sales system.
Analyze the customer's message (and optional history) and classify it into one of these intents:
- product_discovery: Searching, seeking, finding, or listing products in the catalog.
- product_question: Asking questions about specs, warranty, dimensions, materials, weight, etc.
- product_comparison: Comparing two or more products or asking for differences.
- cart_management: Adding a locked deal to the cart, locking terms, viewing/modifying the cart, or removing items.
- checkout: Expressing intent to buy, place order, finalize purchase, or check out.
- negotiation: Bargaining, seeking price cuts, objecting to prices, or negotiating.
- general: General greetings (hello, hi), gratitude, or chit-chat.

List the names or IDs of any products mentioned in the query under target_product_ids.
Return EXACTLY one JSON object matching the IntentClassification schema.
"""


class ProductKnowledgeService:
    """Service to route user intents and answer product questions/comparisons using catalog-backed data."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def classify_intent(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> IntentClassification:
        """Route user query to appropriate pipeline intent."""
        prompt_parts = []
        if history:
            prompt_parts.append("## History:")
            for h in history:
                prompt_parts.append(f"{h.get('role', 'user')}: {h.get('message', '')}")
        prompt_parts.append(f"## Message:\n{message}")

        try:
            return await self._llm.generate(
                prompt="\n".join(prompt_parts),
                system_prompt=_INTENT_SYSTEM_PROMPT,
                response_model=IntentClassification,
            )
        except Exception as e:
            logger.error("Intent classification failed: %s. Using default fallback.", e)
            # Default fallback logic is handled inside GracefulFallbackProvider as well,
            # but we define a safe return here in case.
            fallback_provider = self._llm
            if hasattr(fallback_provider, "fallback"):
                return await fallback_provider.fallback.generate(message, "", IntentClassification)
            
            return IntentClassification(
                intent="negotiation",
                confidence=0.5,
                reasoning="Fallback default routing.",
                target_product_ids=[]
            )

    async def answer_product_question(
        self,
        product: Product,
        question: str,
        db: AsyncSession,
    ) -> str:
        """Answer a product question dynamically using catalog fields and database specifications.

        Ensures separation of Catalog-Backed Facts and General Knowledge estimates.
        """
        # Load specifications from database
        stmt = select(ProductSpecification).where(ProductSpecification.product_id == product.id)
        result = await db.execute(stmt)
        specs = result.scalars().all()

        spec_dict = {s.specification_name.lower(): s.specification_value for s in specs}

        # Add catalog fields to spec dict
        spec_dict["category"] = product.category
        spec_dict["price"] = f"INR {product.selling_price:,.2f}"
        spec_dict["stock"] = f"{product.stock_quantity} units available"
        spec_dict["popularity"] = f"{round((product.popularity_index or 0.0) / 20.0, 1)}/5.0"
        spec_dict["return rate"] = f"{round(product.return_rate or 0.0, 2)}%"

        # Match question keywords
        q_lower = question.lower()
        matched_spec_name = None
        matched_spec_val = None

        for spec_name, val in spec_dict.items():
            if spec_name in q_lower:
                matched_spec_name = spec_name
                matched_spec_val = val
                break

        # Generate the response
        if matched_spec_name and matched_spec_val:
            return (
                f"**[Catalog-Backed Fact]**\n"
                f"Regarding the {product.name}, the official database record indicates:\n"
                f"- **{matched_spec_name.title()}**: {matched_spec_val}\n\n"
                f"Is there anything else you would like to know or negotiate?"
            )

        # If not explicitly found in catalog columns or specs, use LLM to give industry estimate
        # but instruct it clearly to state it is general knowledge, not catalog backed.
        system_prompt = (
            "You are a sales advisor. A customer is asking a question about a product. "
            "The requested information is NOT in our catalog database. You must answer using "
            "general knowledge/industry estimates. You MUST prefix your response with "
            "'**[General Knowledge]**' and explicitly state that this information is an industry "
            "estimate and is NOT explicitly defined in our official catalog. Do NOT fabricate catalog specs."
        )

        prompt = (
            f"Product Name: {product.name}\n"
            f"Product Category: {product.category}\n"
            f"Customer Question: {question}\n\n"
            f"Construct a natural response following the prefix rules."
        )

        try:
            class TextAnswer(BaseModel):
                answer: str

            answer_obj = await self._llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=TextAnswer
            )
            return answer_obj.answer
        except Exception:
            return (
                f"**[Catalog-Backed Fact]**\n"
                f"The requested specification is **Unavailable** in the official catalog for {product.name}.\n\n"
                f"We can, however, negotiate B2B contract terms, pricing discounts, or packages for this item."
            )

    async def compare_products(
        self,
        query: str,
        active_product: Product | None,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Perform side-by-side catalog comparison for products mentioned in the query."""
        resolver = ProductResolver(llm=self._llm)
        resolved = await resolver.resolve_products(query, db)

        # Include the active product in comparison if it's not already resolved
        if active_product and active_product.id not in [p.id for p in resolved]:
            resolved.append(active_product)

        # Cap comparison to 3 products
        products_to_compare = resolved[:3]

        comparison_data = []
        all_spec_names = set()

        for prod in products_to_compare:
            stmt = select(ProductSpecification).where(ProductSpecification.product_id == prod.id)
            res = await db.execute(stmt)
            specs = res.scalars().all()

            prod_specs = {s.specification_name: s.specification_value for s in specs}
            for name in prod_specs.keys():
                all_spec_names.add(name)

            comparison_data.append({
                "id": prod.external_product_id or str(prod.id),
                "name": prod.name,
                "price": prod.selling_price,
                "stock": prod.stock_quantity,
                "popularity": round((prod.popularity_index or 0.0) / 20.0, 1),
                "return_rate": prod.return_rate or 0.0,
                "category": prod.category,
                "specifications": prod_specs
            })

        return {
            "resolved_count": len(products_to_compare),
            "spec_names": list(all_spec_names),
            "products": comparison_data
        }
