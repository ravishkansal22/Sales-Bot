"""LLM provider abstraction and application settings.

Defines an abstract :class:`LLMProvider` interface and two concrete
implementations—:class:`GeminiProvider` (Google Generative AI) and
:class:`OpenAIProvider` (OpenAI)—plus a :func:`get_llm_provider`
factory and the centralised :class:`Settings` configuration object.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Centralised application configuration.

    Values are read from environment variables or a ``.env`` file
    located in the project root.

    Attributes:
        DATABASE_URL: Async PostgreSQL connection string.
        REDIS_URL: Redis connection string.
        LLM_PROVIDER: Which LLM backend to use (``gemini`` or ``openai``).
        GEMINI_API_KEY: API key for Google Generative AI.
        OPENAI_API_KEY: API key for OpenAI.
        DEFAULT_MODEL: Default model identifier for the chosen provider.
        ROLLOUT_COUNT: Number of Monte-Carlo rollouts per strategy.
        DEBUG: Enable debug mode (verbose SQL logging, etc.).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ghost_negotiator"
    REDIS_URL: str = "redis://localhost:6379/0"
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_MODEL: str = "gemini-2.0-flash"
    ROLLOUT_COUNT: int = 3
    DEBUG: bool = False

    # 1. Base progressive stage discount ceilings
    STAGE_CEILINGS: dict[str, float] = {
        "0": 5.0,
        "1": 10.0,
        "2": 15.0,
        "3": 15.0,
        "4": 15.0,
        "default": 15.0
    }

    # 2. Configurable customer segment modifiers
    SEGMENT_MODIFIERS: dict[str, float] = {
        "VIP": 5.0,
        "STRATEGIC": 5.0,
        "STANDARD": 0.0,
        "BARGAIN HUNTER": -2.0,
        "BARGAIN": -2.0,
        "CHURN RISK": -1.0,
        "default": 0.0
    }

    # 3. Volume-based logarithmic discount allowance coefficients
    VOLUME_COEFFICIENT: float = 3.3
    VOLUME_MAX_ALLOWANCE: float = 10.0

    # 4. Loyalty-based modifiers
    LOYALTY_HIGH_THRESHOLD: float = 0.7
    LOYALTY_HIGH_MODIFIER: float = 2.0
    LOYALTY_LOW_THRESHOLD: float = 0.3
    LOYALTY_LOW_MODIFIER: float = -1.0

    # 5. Historical spend modifiers
    SPEND_HIGH_THRESHOLD: float = 50000.0
    SPEND_HIGH_MODIFIER: float = 3.0
    SPEND_MED_THRESHOLD: float = 10000.0
    SPEND_MED_MODIFIER: float = 1.5

    # 6. Inventory thresholds and modifiers
    STOCK_CRITICAL: int = 5
    STOCK_CRITICAL_CEILING: float = 3.0
    STOCK_LOW: int = 20
    STOCK_LOW_CEILING: float = 5.0
    STOCK_MEDIUM: int = 100
    STOCK_MEDIUM_CEILING: float = 10.0
    STOCK_EXCESS_CEILING_MODIFIER: float = 5.0

    # 7. Optimizer scoring weights
    SCORING_WEIGHTS: dict[str, float] = {
        "expected_value": 0.40,
        "close_probability": 0.30,
        "risk_score": 0.20,
        "confidence": 0.10
    }

    # 8. Repeated discount request penalties and boosts
    REPEATED_DEMAND_THRESHOLD: int = 2
    REPEATED_DEMAND_DISCOUNT_PENALTY: float = -250.0
    REPEATED_DEMAND_BUNDLE_BOOST: float = 150.0

    # 9. Strategy fit weights
    STRATEGY_FIT_WEIGHTS: dict[str, dict[str, float]] = {
        "discount": {
            "price_sensitivity": 0.40,
            "urgency": 0.25,
            "brand_loyalty_inv": 0.20,
            "decision_speed": 0.15
        },
        "hardline": {
            "brand_loyalty": 0.35,
            "price_sensitivity_inv": 0.30,
            "risk_aversion": 0.20,
            "urgency_inv": 0.15
        },
        "bundle": {
            "risk_aversion_inv": 0.30,
            "price_sensitivity_inv": 0.25,
            "brand_loyalty": 0.25,
            "urgency": 0.20
        },
        "personalized": {
            "price_sensitivity": 0.25,
            "urgency": 0.20,
            "brand_loyalty": 0.20,
            "risk_aversion_inv": 0.20,
            "decision_speed": 0.15
        },
        "default": {
            "price_sensitivity": 0.20,
            "urgency": 0.20,
            "brand_loyalty": 0.20,
            "risk_aversion_inv": 0.20,
            "decision_speed": 0.20
        }
    }

    # 10. Close probability weights
    CLOSE_PROBABILITY_WEIGHTS: dict[str, float] = {
        "strategy_fit": 0.50,
        "urgency": 0.20,
        "decision_speed": 0.15,
        "margin": 0.15,
        "buying_intent_delta": 0.15,
        "trust_delta": 0.10,
        "objection_delta": -0.10,
        "engagement_delta": 0.05
    }

    # 11. Risk score weights
    RISK_SCORE_WEIGHTS: dict[str, float] = {
        "discount_risk": 0.35,
        "bundle_risk": 0.20,
        "leakage_risk": 0.30,
        "margin_risk": 0.15
    }

    # 12. Confidence score params
    CONFIDENCE_MAX_VARIANCE: float = 0.25

    # 13. Bundle deal value max ratio
    MAX_BUNDLE_DEAL_VALUE_RATIO: float = 0.25

    # 14. Optimizer explainability threshold multipliers
    OPTIMIZER_RISK_MULTIPLIER: float = 1.2
    OPTIMIZER_CLOSE_PROB_MULTIPLIER: float = 0.9
    SCORING_SCALE_FACTOR: float = 1000.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Returns:
        The global :class:`Settings` instance.
    """
    return Settings()


settings: Settings = get_settings()


# ---------------------------------------------------------------------------
# Abstract LLM provider
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    Each provider must implement :meth:`generate` which accepts a user
    prompt, a system prompt, and a Pydantic model class, then returns a
    parsed instance of that model.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        """Generate structured output from the LLM.

        Args:
            prompt: The user-facing prompt / message.
            system_prompt: System-level instructions for the model.
            response_model: A Pydantic model class that the raw LLM
                JSON output will be validated against.

        Returns:
            A validated instance of ``response_model``.
        """
        ...


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


class GeminiProvider(LLMProvider):
    """Google Generative AI provider using the ``google-genai`` SDK.

    Uses ``client.aio.models.generate_content`` with JSON-mode response
    and schema-based validation.
    """

    def __init__(self, api_key: str, model: str) -> None:
        """Initialise the Gemini provider.

        Args:
            api_key: Google AI API key.
            model: Model identifier (e.g. ``gemini-2.0-flash``).
        """
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        """Generate structured output via Gemini.

        Args:
            prompt: User prompt text.
            system_prompt: System-level instructions.
            response_model: Target Pydantic model for validation.

        Returns:
            Parsed and validated ``response_model`` instance.

        Raises:
            ValueError: If the response cannot be parsed into the model.
        """
        from google.genai import types

        generation_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=response_model,
            temperature=0.7,
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=generation_config,
        )

        raw_text = response.text
        if raw_text is None:
            raise ValueError("Gemini returned an empty response")

        parsed = json.loads(raw_text)
        return response_model.model_validate(parsed)


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    """OpenAI provider using the ``openai`` Python SDK.

    Uses ``client.beta.chat.completions.parse`` with structured
    ``response_format`` for guaranteed-valid JSON output.
    """

    def __init__(self, api_key: str, model: str) -> None:
        """Initialise the OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model identifier (e.g. ``gpt-4o``).
        """
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        """Generate structured output via OpenAI.

        Args:
            prompt: User prompt text.
            system_prompt: System-level instructions.
            response_model: Target Pydantic model for validation.

        Returns:
            Parsed and validated ``response_model`` instance.

        Raises:
            ValueError: If the model refuses or the response cannot
                be parsed.
        """
        completion = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format=response_model,
            temperature=0.7,
        )

        message = completion.choices[0].message

        if message.refusal:
            raise ValueError(f"OpenAI refused the request: {message.refusal}")

        if message.parsed is None:
            raise ValueError("OpenAI returned an unparseable response")

        return message.parsed


# ---------------------------------------------------------------------------
# Graceful Degradation Providers
# ---------------------------------------------------------------------------


class DeterministicFallbackProvider(LLMProvider):
    """Fallback LLM provider that yields deterministic outputs.

    Used when external LLM providers are offline, or if API keys are missing.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        logger.warning("Deterministic Fallback Provider triggered for response model: %s", response_model.__name__)
        name = response_model.__name__

        # 1. Conversation Analysis
        if name == "ConversationAnalysis":
            prompt_lower = prompt.lower()
            obj_type = "none"
            intent = "information_gathering"
            stage = "discovery"
            sentiment = "neutral"
            urgency = 0.5
            
            # Simple keyword checks
            if "competitor" in prompt_lower or "cheaper" in prompt_lower:
                obj_type = "competitor"
                intent = "competitive_leverage"
                stage = "negotiation"
            elif "discount" in prompt_lower or "price" in prompt_lower or "%" in prompt_lower or "off" in prompt_lower:
                obj_type = "price"
                intent = "discount_seeking"
                stage = "negotiation"
            elif "accept" in prompt_lower or "agree" in prompt_lower or "deal" in prompt_lower or "buy" in prompt_lower:
                obj_type = "none"
                intent = "closing"
                stage = "closed_won"
            elif "hello" in prompt_lower or "hi" in prompt_lower:
                intent = "relationship_building"
                stage = "discovery"

            data = {
                "objection_type": obj_type,
                "negotiation_intent": intent,
                "urgency": urgency,
                "sentiment": sentiment,
                "stage": stage,
            }
            return response_model.model_validate(data)

        # 2. Digital Twin
        elif name == "DigitalTwinProfile":
            price_sens = 0.5
            urgency = 0.5
            risk_av = 0.5
            brand_loy = 0.5
            dec_speed = 0.5

            # Parse prior values from prompt
            prior_match = re.findall(
                r"- (Price Sensitivity|Urgency|Risk Aversion|Brand Loyalty|Decision Speed):\s*([\d\.]+)",
                prompt,
            )
            prior = {k.lower(): float(v) for k, v in prior_match}

            price_sens = prior.get("price sensitivity", price_sens)
            urgency = prior.get("urgency", urgency)
            risk_av = prior.get("risk aversion", risk_av)
            brand_loy = prior.get("brand loyalty", brand_loy)
            dec_speed = prior.get("decision speed", dec_speed)

            # Nudge based on latest message
            prompt_lower = prompt.lower()
            if "objection type: competitor" in prompt_lower:
                price_sens = min(1.0, price_sens + 0.15)
                brand_loy = max(0.0, brand_loy - 0.15)
                urgency = min(1.0, urgency + 0.1)
            elif "objection type: price" in prompt_lower:
                price_sens = min(1.0, price_sens + 0.1)
                urgency = min(1.0, urgency + 0.05)
            elif "negotiation intent: closing" in prompt_lower:
                urgency = min(1.0, urgency + 0.2)
                dec_speed = min(1.0, dec_speed + 0.2)

            data = {
                "price_sensitivity": round(price_sens, 2),
                "urgency": round(urgency, 2),
                "risk_aversion": round(risk_av, 2),
                "brand_loyalty": round(brand_loy, 2),
                "decision_speed": round(dec_speed, 2),
            }
            return response_model.model_validate(data)

        # 3. Strategy Output
        elif name == "LLMStrategyOutput":
            strat_name = "discount"
            prompt_lower = prompt.lower()
            if "strategy: bundle" in prompt_lower or "bundle strategy" in prompt_lower:
                strat_name = "bundle"
            elif "strategy: hardline" in prompt_lower or "hardline strategy" in prompt_lower:
                strat_name = "hardline"
            elif "strategy: personalized" in prompt_lower or "personalized strategy" in prompt_lower:
                strat_name = "personalized"

            discount = 0.0
            bundle_val = 0.0
            reasoning = ""

            if strat_name == "discount":
                discount = 12.0
                reasoning = "Offer a direct 12% price discount on the list price to address pricing concerns and secure the B2B supply agreement."
            elif strat_name == "hardline":
                discount = 0.0
                reasoning = "Maintain listing catalog price, highlighting the high value, quality assurance, and support warranty."
            elif strat_name == "bundle":
                discount = 5.0
                bundle_val = 30.0
                reasoning = "Provide a 5% discount and bundle standard accessories/concessions to preserve core product margins."
            elif strat_name == "personalized":
                discount = 8.0
                bundle_val = 15.0
                reasoning = "Apply a tailored agreement with an 8% discount combined with priority shipping support."

            data = {
                "strategy_name": strat_name,
                "offer_type": strat_name,
                "discount_percent": discount,
                "bundle_value": bundle_val,
                "reasoning": reasoning,
            }
            return response_model.model_validate(data)

        # 4. Response Generator Output
        elif name == "_LLMResponseOutput" or "response" in name.lower():
            # Parse recommended strategy and parameters
            strat_name = "discount"
            discount = 0.0
            bundle_val = 0.0

            strat_match = re.search(r"- Strategy:\s*(\w+)", prompt)
            if strat_match:
                strat_name = strat_match.group(1).lower()

            disc_match = re.search(r"- Discount:\s*([\d\.]+)%", prompt)
            if disc_match:
                discount = float(disc_match.group(1))

            bund_match = re.search(r"- Bundle Value Added:\s*\$?([\d\.,]+)", prompt)
            if bund_match:
                bundle_val = float(bund_match.group(1).replace(",", ""))

            if strat_name == "discount":
                resp_text = f"We appreciate your budget considerations. To help finalize this agreement, we can offer a calibrated {discount:.1f}% discount on this order. This brings the unit price to a competitive rate while preserving our premium quality standard. Let me know if you would like to lock in this deal."
            elif strat_name == "hardline":
                resp_text = f"Our catalog pricing reflects the premium quality and structural durability of our products. While we are unable to lower the base price, we stand behind the outstanding value and full B2B warranty included with this purchase. We look forward to partnering with you."
            elif strat_name == "bundle":
                resp_text = f"To support your procurement objectives without compromising on margins, we have structured a value bundle. We can offer a {discount:.1f}% price concession and include premium maintenance packages/accessories at no additional charge. This provides substantial value-add for your team. Would this approach work for you?"
            elif strat_name == "personalized":
                resp_text = f"Based on your requirements, we have prepared a tailored B2B agreement. We are pleased to offer a calibrated unit price of {discount:.1f}% off, along with custom delivery schedules and priority support. We believe this aligns with your timeline and budget expectations. Please let us know your thoughts."
            else:
                resp_text = f"Thank you for your message. We are ready to work with you on a customized B2B agreement. We can discuss price concessions, value-add bundle options, or compare different options in our catalog. How would you like to proceed?"

            data = {
                "customer_response": resp_text,
                "internal_reasoning": f"Generated fallback response for {strat_name} strategy with {discount:.1f}% discount and ${bundle_val:.2f} bundle value.",
            }
            return response_model.model_validate(data)

        # 5. Search Extraction / Product Resolver query
        elif name == "SearchExtraction" or "search" in name.lower():
            # Extract keywords
            words = [w for w in prompt.split() if len(w) > 3 and w.lower() not in ["user", "message", "query"]]
            query = " ".join(words[:2]) if words else "product"
            data = {
                "query": query,
                "is_product_related": True,
            }
            return response_model.model_validate(data)

        # 6. Intent Classification
        elif name == "IntentClassification":
            prompt_lower = prompt.lower()
            intent = "negotiation"
            
            # Simple keyword classification rules
            if any(kw in prompt_lower for kw in ["compare", "vs", "versus", "difference between", "better"]):
                intent = "product_comparison"
            elif any(kw in prompt_lower for kw in ["warranty", "dimension", "specifications", "spec", "material", "made of", "weight", "features", "details", "compatible"]):
                intent = "product_question"
            elif any(kw in prompt_lower for kw in ["find", "search", "show me", "catalog", "what products", "looking for", "recommend"]):
                intent = "product_discovery"
            elif any(kw in prompt_lower for kw in ["lock deal", "add to cart", "show cart", "view cart", "procurement cart", "remove", "reopen"]):
                intent = "cart_management"
            elif any(kw in prompt_lower for kw in ["checkout", "finalize purchase", "buy", "place order"]):
                intent = "checkout"
            elif any(kw in prompt_lower for kw in ["hello", "hi", "thanks", "thank you", "bye"]):
                intent = "general"

            data = {
                "intent": intent,
                "confidence": 0.95,
                "reasoning": f"Fallback routing classified query as: {intent}",
                "target_product_ids": []
            }
            return response_model.model_validate(data)

        # Generic default construct
        return response_model.construct()


class GracefulFallbackProvider(LLMProvider):
    """Wraps a primary LLMProvider and falls back to DeterministicFallbackProvider upon error."""

    def __init__(self, primary: LLMProvider | None = None) -> None:
        self.primary = primary
        self.fallback = DeterministicFallbackProvider()

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        if self.primary is not None:
            try:
                return await self.primary.generate(prompt, system_prompt, response_model)
            except Exception as e:
                logger.error("Primary LLM provider failed: %s. Falling back to deterministic model.", e)
                return await self.fallback.generate(prompt, system_prompt, response_model)
        else:
            return await self.fallback.generate(prompt, system_prompt, response_model)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm_provider(provider_override: str | None = None) -> LLMProvider:
    """Factory function that returns the configured LLM provider.

    Reads from the ``LLM_PROVIDER`` environment variable (via
    :data:`settings`) unless ``provider_override`` is given.
    """
    provider_name = (provider_override or settings.LLM_PROVIDER).lower().strip()

    primary_provider = None
    if provider_name == "gemini":
        if settings.GEMINI_API_KEY:
            primary_provider = GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model=settings.DEFAULT_MODEL,
            )
        else:
            logger.warning("GEMINI_API_KEY not set. Utilizing Graceful Fallback.")

    elif provider_name == "openai":
        if settings.OPENAI_API_KEY:
            primary_provider = OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.DEFAULT_MODEL,
            )
        else:
            logger.warning("OPENAI_API_KEY not set. Utilizing Graceful Fallback.")

    else:
        logger.warning("Unknown or unsupported LLM provider name: %s. Utilizing Graceful Fallback.", provider_name)

    return GracefulFallbackProvider(primary_provider)
