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
import os
import sqlite3
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import TypeVar, Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Metrics / Stats Service
# ---------------------------------------------------------------------------

class MetricsService:
    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            # Place metrics.db in the backend directory
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "metrics.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            with conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS metrics (key TEXT PRIMARY KEY, val TEXT)"
                )
        finally:
            conn.close()

    def increment(self, key: str, amount: int = 1) -> int:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT val FROM metrics WHERE key = ?", (key,))
                row = cur.fetchone()
                if row is None:
                    new_val = amount
                    cur.execute("INSERT INTO metrics (key, val) VALUES (?, ?)", (key, str(new_val)))
                else:
                    new_val = int(row[0]) + amount
                    cur.execute("UPDATE metrics SET val = ? WHERE key = ?", (str(new_val), key))
                return new_val
        finally:
            conn.close()

    def get(self, key: str) -> int:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT val FROM metrics WHERE key = ?", (key,))
            row = cur.fetchone()
            if row is not None:
                try:
                    return int(row[0])
                except ValueError:
                    return 0
            return 0
        finally:
            conn.close()

    def set_value(self, key: str, val: str) -> None:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO metrics (key, val) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET val = ?",
                    (key, val, val)
                )
        finally:
            conn.close()

    def get_value(self, key: str) -> str | None:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT val FROM metrics WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row is not None else None
        finally:
            conn.close()

    def reset(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            with conn:
                conn.execute("DELETE FROM metrics")
        finally:
            conn.close()

    @property
    def count_429(self) -> int:
        return self.get("429_count")

    @property
    def fallback_count(self) -> int:
        return self.get("fallback_count")

    @property
    def cache_hits(self) -> int:
        return self.get("cache_hits")

    @property
    def cache_misses(self) -> int:
        return self.get("cache_misses")

    @property
    def circuit_breaker_open_count(self) -> int:
        return self.get("circuit_breaker_open_count")


class LLMCallCountsDict(dict):
    def __init__(self, metrics_serv: MetricsService):
        super().__init__()
        self._metrics = metrics_serv
        self.update({
            "IntentClassification": 0,
            "ConversationAnalysis": 0,
            "DigitalTwinProfile": 0,
            "LLMStrategyOutput": 0,
            "_LLMResponseOutput": 0,
            "SearchExtraction": 0,
            "total": 0
        })

    def __getitem__(self, key):
        return self._metrics.get(f"call_count:{key}")

    def __setitem__(self, key, value):
        current = self._metrics.get(f"call_count:{key}")
        diff = value - current
        self._metrics.increment(f"call_count:{key}", diff)

    def get(self, key, default=0):
        val = self._metrics.get(f"call_count:{key}")
        return val if val is not None else default

    def items(self):
        return [(k, self.get(k)) for k in self.keys()]

    def keys(self):
        return ["IntentClassification", "ConversationAnalysis", "DigitalTwinProfile", "LLMStrategyOutput", "_LLMResponseOutput", "SearchExtraction", "total"]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())


metrics_service = MetricsService()
llm_call_counts = LLMCallCountsDict(metrics_service)



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
    GROQ_API_KEY: str = ""
    DEFAULT_MODEL: str = "gemini-2.0-flash"
    ROLLOUT_COUNT: int = 3
    DEBUG: bool = False

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = ""
    ENABLE_OLLAMA_FALLBACK: bool = True
    GROQ_COOLDOWN_SECONDS: int = 300
    GROQ_FAILURE_THRESHOLD: int = 5
    GROQ_TIMEOUT: float = 8.0
    DISCOVERY_ESCAPE_PATTERNS: list[str] = [
        "show", "search", "new product", "another product",
        "different model", "compare", "alternatives", "switch"
    ]
    TAVILY_API_KEY: str = ""
    RETRIEVAL_PROVIDER: str = "tavily"

    # Business rule configurations
    ALLOW_BELOW_COST: bool = False
    ALLOW_BELOW_MINIMUM: bool = False
    STRICT_NEGOTIATION_VALIDATION: bool = True
    ENABLE_SPEC_ESTIMATION: bool = False
    SPEC_ESTIMATION_CONFIDENCE_THRESHOLD: float = 0.85

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
        "expected_value": 0.20,
        "close_probability": 0.50,
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

        self._client = AsyncOpenAI(api_key=api_key, max_retries=0)
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


class GroqProvider(LLMProvider):
    """Groq provider using the ``groq`` Python SDK.

    Uses JSON mode with manual schema validation for robust structured output.
    """

    def __init__(self, api_key: str, model: str) -> None:
        """Initialise the Groq provider.

        Args:
            api_key: Groq API key.
            model: Model identifier (e.g. ``llama-3.3-70b-versatile``).
        """
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=api_key, max_retries=0)
        self._model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        """Generate structured output via Groq using JSON mode."""
        model_name = response_model.__name__

        # 1. TextAnswer bypass: TextAnswer is plain text, so do not use JSON mode
        if model_name == "TextAnswer":
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                timeout=settings.GROQ_TIMEOUT,
            )
            content = completion.choices[0].message.content
            if content is None:
                raise ValueError("Groq returned an empty response")
            return response_model(answer=content.strip())

        # 2. Extract model json schema and append it to the system instruction
        schema_dict = response_model.model_json_schema()
        schema_json = json.dumps(schema_dict, indent=2)

        json_instruction = (
            f"\n\nYou MUST return a valid JSON object conforming exactly to this JSON schema:\n"
            f"{schema_json}\n\n"
            f"IMPORTANT: You must return ONLY the raw JSON object. Do not wrap the JSON in markdown code blocks like ```json ... ```. "
            f"Do not include any explanations, pre-text, or post-text. The response must contain the lowercase word 'json' to satisfy formatting requirements."
        )

        full_system_prompt = system_prompt + json_instruction

        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            timeout=settings.GROQ_TIMEOUT,
        )

        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("Groq returned an empty response")

        # Strip markdown code blocks if present
        cleaned_content = content.strip()
        if cleaned_content.startswith("```"):
            cleaned_content = re.sub(r"^```(?:json)?\s*", "", cleaned_content)
            cleaned_content = re.sub(r"\s*```$", "", cleaned_content)
        cleaned_content = cleaned_content.strip()

        # Parse JSON payload
        try:
            parsed = json.loads(cleaned_content)
            if (
                isinstance(parsed, dict)
                and "description" in parsed
                and isinstance(parsed["description"], dict)
            ):
                 parsed = parsed["description"]
        except json.JSONDecodeError as je:
            logger.error("Groq JSON parsing failed. Content was: %r. Error: %s", content, je)
            raise ValueError(f"Invalid JSON from Groq: {je}") from je

        # Model-specific defaults mapping for schema repair
        DEFAULTS_MAP = {
            "IntentClassification": {
                "intent": "negotiation",
                "confidence": 0.95,
                "reasoning": "Schema repair",
                "target_product_ids": []
            },
            "ConversationAnalysis": {
                "objection_type": "price",
                "negotiation_intent": "general negotiation",
                "urgency": 0.5,
                "sentiment": "neutral",
                "stage": "consideration"
            },
            "DigitalTwinProfile": {
                "price_sensitivity": 0.5,
                "urgency": 0.5,
                "risk_aversion": 0.5,
                "brand_loyalty": 0.5,
                "decision_speed": 0.5
            },
            "LLMStrategyOutput": {
                "strategy_name": "discount",
                "strategy": "discount",
                "offer_type": "discount",
                "discount_percent": 0.0,
                "bundle_value": 0.0,
                "reasoning": "Schema repair",
                "explanation": "Schema repair",
                "confidence": 0.9
            },
            "SearchExtraction": {
                "query": "",
                "is_product_related": False
            }
        }

        # Validate with repair logic (maximum 2 repair attempts)
        repaired = dict(parsed)
        MAX_REPAIR_ATTEMPTS = 2
        for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
            try:
                validated = response_model.model_validate(repaired)
                logger.info("Groq output validated successfully for %s", model_name)
                return validated
            except Exception as ve:
                if attempt == MAX_REPAIR_ATTEMPTS:
                    logger.error("Repair failed for %s after %d attempts. Payload: %s. Error: %s", model_name, attempt, repaired, ve)
                    raise ve

                logger.warning(
                    "Pydantic validation failed for %s (attempt %d/%d) with payload: %s. Error: %s. Attempting repair...",
                    model_name, attempt + 1, MAX_REPAIR_ATTEMPTS, repaired, ve
                )

                from pydantic import ValidationError
                if isinstance(ve, ValidationError):
                    for err in ve.errors():
                        loc = err.get("loc")
                        if loc and isinstance(loc, tuple) and len(loc) == 1:
                            field_name = loc[0]
                            if isinstance(field_name, str) and field_name in response_model.model_fields:
                                field = response_model.model_fields[field_name]
                                model_defaults = DEFAULTS_MAP.get(model_name, {})
                                if field_name in model_defaults:
                                    repaired[field_name] = model_defaults[field_name]
                                else:
                                    # Fallback to schema default or generic type fallback
                                    from pydantic_core import PydanticUndefined
                                    if field.default is not PydanticUndefined:
                                        repaired[field_name] = field.default
                                    elif field.default_factory is not None:
                                        repaired[field_name] = field.default_factory()
                                    else:
                                        ann = field.annotation
                                        ann_str = str(ann).lower()
                                        if "str" in ann_str:
                                            repaired[field_name] = "unknown"
                                        elif "float" in ann_str or "int" in ann_str:
                                            repaired[field_name] = 0.0
                                        elif "list" in ann_str:
                                            repaired[field_name] = []
                                        elif "dict" in ann_str:
                                            repaired[field_name] = {}
                                        elif "bool" in ann_str:
                                            repaired[field_name] = False
                                        else:
                                            repaired[field_name] = None
                        else:
                            model_defaults = DEFAULTS_MAP.get(model_name, {})
                            for k, val in model_defaults.items():
                                if k not in repaired:
                                    repaired[k] = val
                            break
                else:
                    model_defaults = DEFAULTS_MAP.get(model_name, {})
                    for k, val in model_defaults.items():
                        if k not in repaired:
                            repaired[k] = val



# ---------------------------------------------------------------------------
# Graceful Degradation Providers
# ---------------------------------------------------------------------------


class DeterministicFallbackProvider(LLMProvider):
    """Fallback LLM provider that yields deterministic outputs.

    Used when external LLM providers are offline, or if API keys are missing.
    """

    def _validate_and_log(self, name: str, response_model: type[T], data: dict[str, Any]) -> T:
        logger.info("DeterministicFallbackProvider: Validating schema %s with data: %s", name, data)
        try:
            validated = response_model.model_validate(data)
            logger.info("DeterministicFallbackProvider: Schema %s validated successfully.", name)
            return validated
        except Exception as ve:
            logger.error("DeterministicFallbackProvider: Schema %s validation failed: %s", name, ve)
            raise

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        logger.warning("Deterministic Fallback Provider triggered for response model: %s", response_model.__name__)
        name = response_model.__name__

        # Build safe type-conforming defaults
        default_data = {}
        for field_name, field in response_model.model_fields.items():
            from pydantic_core import PydanticUndefined
            if field.default is not PydanticUndefined:
                default_data[field_name] = field.default
            elif field.default_factory is not None:
                default_data[field_name] = field.default_factory()
            else:
                ann = field.annotation
                ann_str = str(ann).lower()
                if "str" in ann_str:
                    default_data[field_name] = "default"
                elif "float" in ann_str or "int" in ann_str:
                    default_data[field_name] = 0.0
                elif "list" in ann_str:
                    default_data[field_name] = []
                elif "dict" in ann_str:
                    default_data[field_name] = {}
                elif "bool" in ann_str:
                    default_data[field_name] = False
                else:
                    default_data[field_name] = None

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
            return self._validate_and_log(name, response_model, {**default_data, **data})

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
            return self._validate_and_log(name, response_model, {**default_data, **data})

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
                reasoning = "Provide a 5% discount and bundle standard concessions to preserve core product margins."
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
            return self._validate_and_log(name, response_model, {**default_data, **data})

        # 4. Response Generator Output
        elif name == "_LLMResponseOutput" or "response" in name.lower():
            # Parse recommended strategy and parameters
            strat_name = "discount"
            discount = 0.0
            bundle_val = 0.0

            # Isolate the Recommended Strategy section to avoid matching runner-up values
            rec_section = ""
            rec_match = re.search(r"## Recommended Strategy(.*?)(?:##|$)", prompt, re.DOTALL)
            if rec_match:
                rec_section = rec_match.group(1)
            else:
                rec_section = prompt

            strat_match = re.search(r"- Strategy:\s*(\w+)", rec_section)
            if strat_match:
                strat_name = strat_match.group(1).lower()

            disc_match = re.search(r"- Discount:\s*([\d\.]+)%", rec_section)
            if disc_match:
                discount = float(disc_match.group(1))

            bund_match = re.search(r"- Bundle Value Added:\s*\$?([\d\.,]+)", rec_section)
            if bund_match:
                bundle_val = float(bund_match.group(1).replace(",", ""))

            concessions = []
            conc_match = re.search(r"- Concessions:\s*(.*)", rec_section)
            if conc_match:
                concessions = [c.strip() for c in conc_match.group(1).split(",")]

            # Parse alternative strategies / runner-ups
            runner_ups_list = []
            runner_up_matches = re.finditer(r"### Runner-up \d+:\s*(\w+)(.*?)(?=### Runner-up \d+:|##|$)", prompt, re.DOTALL)
            for match in runner_up_matches:
                ru_name = match.group(1).lower().strip()
                ru_block = match.group(2)
                ru_disc = 0.0
                ru_disc_match = re.search(r"- Discount:\s*([\d\.]+)%", ru_block)
                if ru_disc_match:
                    ru_disc = float(ru_disc_match.group(1))
                ru_concessions = []
                ru_conc_match = re.search(r"- Concessions:\s*(.*)", ru_block)
                if ru_conc_match:
                    ru_concessions = [c.strip() for c in ru_conc_match.group(1).split(",")]
                runner_ups_list.append({
                    "name": ru_name,
                    "discount": ru_disc,
                    "concessions": ru_concessions
                })

            if strat_name == "discount":
                concession_list_str = ""
                if concessions:
                    concession_list_str = f" along with {', '.join(concessions)}"
                
                alternative_texts = []
                for ru in runner_ups_list:
                    if ru["name"] == "bundle" and ru["concessions"]:
                        alternative_texts.append(f"explore value-add bundles (including {', '.join(ru['concessions'])})")
                    elif ru["name"] == "personalized" and ru["concessions"]:
                        alternative_texts.append(f"phased logistics/custom terms (like {', '.join(ru['concessions'])})")

                if alternative_texts:
                    pivot_text = " To support you further, we can also " + " or ".join(alternative_texts) + "."
                else:
                    pivot_text = ""

                resp_text = (
                    f"We appreciate your budget considerations. While a higher reduction exceeds the approved range, "
                    f"I can immediately approve a {discount:.1f}% discount on this order{concession_list_str} to bring the unit price to a competitive rate.{pivot_text} "
                    f"Let me know if you would like to lock in this deal."
                )
            elif strat_name == "hardline":
                alternative_texts = []
                for ru in runner_ups_list:
                    if ru["name"] == "discount" and ru["discount"] > 0:
                        alternative_texts.append(f"approve a {ru['discount']:.1f}% discount")
                    elif ru["name"] == "bundle" and ru["concessions"]:
                        alternative_texts.append(f"explore bundle options such as {', '.join(ru['concessions'])}")
                    elif ru["name"] == "personalized" and ru["concessions"]:
                        alternative_texts.append(f"structure tailored terms including {', '.join(ru['concessions'])}")

                if alternative_texts:
                    pivot_text = " However, we can look into alternative options: we might be able to " + " or ".join(alternative_texts) + "."
                else:
                    pivot_text = " We would be happy to discuss larger volume pricing structures or payment terms that could better suit your budget."

                resp_text = (
                    f"While we cannot accommodate a direct price reduction at this stage, we stand behind the exceptional value "
                    f"and warranty included with this catalog price.{pivot_text} Please let us know if you would like to discuss these options."
                )
            elif strat_name == "bundle":
                if concessions:
                    concessions_str = "including " + ", ".join(concessions)
                else:
                    concessions_str = "value-added support SLA, payment terms, and delivery logistics"

                alternative_texts = []
                for ru in runner_ups_list:
                    if ru["name"] == "discount" and ru["discount"] > 0:
                        alternative_texts.append(f"a direct {ru['discount']:.1f}% price concession")

                if alternative_texts:
                    pivot_text = " In addition, we can explore " + " or ".join(alternative_texts) + "."
                else:
                    pivot_text = ""

                resp_text = (
                    f"To support your procurement objectives without compromising on core margins, we have structured a value bundle "
                    f"that features key concessions, {concessions_str}.{pivot_text} This provides substantial value-add for your team. "
                    f"Would this approach work for you?"
                )
            elif strat_name == "personalized":
                if concessions:
                    concessions_str = f" and custom terms such as {', '.join(concessions)}"
                else:
                    concessions_str = ""

                resp_text = (
                    f"Based on your requirements, we have prepared a tailored B2B agreement. We are pleased to offer a "
                    f"calibrated unit price of {discount:.1f}% off list price{concessions_str}. We believe this aligns with your timeline "
                    f"and budget expectations. Please let us know your thoughts."
                )
            else:
                resp_text = f"Thank you for your message. We are ready to work with you on a customized B2B agreement. We can discuss price concessions, value-add bundle options, or compare different options in our catalog. How would you like to proceed?"

            data = {
                "customer_response": resp_text,
                "internal_reasoning": f"Generated fallback response for {strat_name} strategy with {discount:.1f}% discount and ${bundle_val:.2f} bundle value.",
            }
            return self._validate_and_log(name, response_model, {**default_data, **data})

        # 5. Search Extraction / Product Resolver query
        elif name == "SearchExtraction" or "search" in name.lower():
            # Extract keywords
            words = [w for w in prompt.split() if len(w) > 3 and w.lower() not in ["user", "message", "query"]]
            query = " ".join(words[:2]) if words else "product"
            data = {
                "query": query,
                "is_product_related": True,
            }
            return self._validate_and_log(name, response_model, {**default_data, **data})

        # 6. Intent Classification
        elif name == "IntentClassification":
            prompt_lower = prompt.lower()
            intent = "negotiation"
            
            # Simple keyword classification rules
            if any(kw in prompt_lower for kw in ["compare", "vs", "versus", "difference between", "better"]):
                intent = "product_comparison"
            elif any(kw in prompt_lower for kw in [
                "warranty", "guarantee", "warranty period", "dimension", "dimensions", "size", "height", "width", "depth", "length", 
                "specifications", "spec", "specs", "material", "made of", "weight", "features", "details", "compatible", 
                "color", "colour", "shade", "hue", "cpu", "chip", "chipset", "processor", "ram", "storage", "capacity", 
                "memory", "mah", "battery capacity", "battery life", "battery", "megapixels", "mp", "resolution", "lens", "camera"
            ]):
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
            return self._validate_and_log(name, response_model, {**default_data, **data})

        # Generic default model validation to guarantee no missing fields
        return self._validate_and_log(name, response_model, default_data)


# ---------------------------------------------------------------------------
# Circuit Breaker Service
# ---------------------------------------------------------------------------

import threading
import time

class CircuitBreakerService:
    """Manages circuit breaker state across workers thread-safely."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_memory = {
            "consecutive_failures": 0,
            "state": "closed",
            "cooldown_until": 0.0,
            "half_open_probe_active": False
        }

    async def _get_state(self) -> dict[str, Any]:
        from app.services.redis_service import _redis_service
        if _redis_service is not None:
            try:
                state_str = await _redis_service._client.get("groq_circuit_breaker_state")
                if state_str:
                    return json.loads(state_str)
            except Exception as e:
                logger.warning("CircuitBreakerService: Failed to read from Redis: %s. Disabling Redis globally and using in-memory fallback.", e)
                from app.services.redis_service import disable_redis
                disable_redis()
        
        with self._lock:
            return dict(self._in_memory)

    async def _set_state(self, state: dict[str, Any]) -> None:
        from app.services.redis_service import _redis_service
        if _redis_service is not None:
            try:
                await _redis_service._client.set("groq_circuit_breaker_state", json.dumps(state))
                return
            except Exception as e:
                logger.warning("CircuitBreakerService: Failed to write to Redis: %s. Disabling Redis globally and using in-memory fallback.", e)
                from app.services.redis_service import disable_redis
                disable_redis()
        
        with self._lock:
            self._in_memory.update(state)

    async def check_circuit(self) -> str:
        """Check the current state of the circuit.
        
        If state is 'open' and cooldown has expired, transitions to 'half_open'.
        """
        state = await self._get_state()
        current_state = state.get("state", "closed")
        cooldown_until = state.get("cooldown_until", 0.0)
        
        if current_state == "open":
            if time.time() >= cooldown_until:
                current_state = "half_open"
                state["state"] = "half_open"
                state["half_open_probe_active"] = False
                await self._set_state(state)
                logger.warning("CircuitBreakerService: Cooldown expired. Transitioning from OPEN to HALF-OPEN state.")
                
        return current_state

    async def acquire_half_open_probe(self) -> bool:
        """Attempt to acquire a probe lock for half_open trial.
        
        Returns True if this request won the probe right and should call Groq.
        Returns False if another request is already probing.
        """
        from app.services.redis_service import _redis_service
        if _redis_service is not None:
            try:
                res = await _redis_service._client.set("groq_half_open_probe_active", "true", ex=15, nx=True)
                return bool(res)
            except Exception as e:
                logger.warning("CircuitBreakerService: Redis probe lock failed: %s. Disabling Redis globally and using in-memory fallback.", e)
                from app.services.redis_service import disable_redis
                disable_redis()
        
        with self._lock:
            if self._in_memory.get("half_open_probe_active", False):
                return False
            self._in_memory["half_open_probe_active"] = True
            return True

    async def record_success(self) -> None:
        """Record a successful call. Transitions back to CLOSED and resets consecutive failures."""
        state = await self._get_state()
        state["state"] = "closed"
        state["consecutive_failures"] = 0
        state["half_open_probe_active"] = False
        await self._set_state(state)
        
        from app.services.redis_service import _redis_service
        if _redis_service is not None:
            try:
                await _redis_service._client.delete("groq_half_open_probe_active")
            except Exception:
                from app.services.redis_service import disable_redis
                disable_redis()
        
        logger.info("CircuitBreakerService: Registered success. Resetting circuit to CLOSED.")

    async def record_failure(self, trip_immediately: bool = False) -> None:
        """Record a failure. Increments consecutive failures and trips breaker if needed."""
        state = await self._get_state()
        failures = state.get("consecutive_failures", 0) + 1
        state["consecutive_failures"] = failures
        current_state = state.get("state", "closed")
        
        if trip_immediately or current_state == "half_open" or failures >= settings.GROQ_FAILURE_THRESHOLD:
            state["state"] = "open"
            state["cooldown_until"] = time.time() + settings.GROQ_COOLDOWN_SECONDS
            state["half_open_probe_active"] = False
            await self._set_state(state)
            metrics_service.increment("circuit_breaker_open_count")
            logger.warning("CircuitBreakerService: Circuit tripped to OPEN. Consecutive failures: %d. Cooldown for %d seconds. (Immediate trip: %s)", failures, settings.GROQ_COOLDOWN_SECONDS, trip_immediately)
        else:
            await self._set_state(state)
            logger.info("CircuitBreakerService: Registered failure. Consecutive failures: %d/%d", failures, settings.GROQ_FAILURE_THRESHOLD)
            
        from app.services.redis_service import _redis_service
        if _redis_service is not None:
            try:
                await _redis_service._client.delete("groq_half_open_probe_active")
            except Exception:
                from app.services.redis_service import disable_redis
                disable_redis()


circuit_breaker_service = CircuitBreakerService()


# ---------------------------------------------------------------------------
# Ollama Provider
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.configured_model = model.strip() if model else ""
        if not self.configured_model:
            self.enabled = False
            logger.warning("Ollama disabled because no OLLAMA_MODEL configured.")
        else:
            self.enabled = True

    async def _get_model(self) -> str:
        return self.configured_model

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        model = await self._get_model()
        model_name = response_model.__name__

        if model_name == "TextAnswer":
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                req_data = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_ctx": 2048,
                        "num_predict": 256
                    }
                }
                res = await client.post(f"{self.base_url}/api/chat", json=req_data)
                if res.status_code != 200:
                    raise ValueError(f"Ollama returned status {res.status_code}: {res.text}")
                
                data = res.json()
                content = data.get("message", {}).get("content")
                if content is None:
                    raise ValueError("Ollama returned an empty response")
                return response_model(answer=content.strip())

        schema_dict = response_model.model_json_schema()
        schema_json = json.dumps(schema_dict, indent=2)

        json_instruction = (
            f"\n\nYou MUST return a valid JSON object conforming exactly to this JSON schema:\n"
            f"{schema_json}\n\n"
            f"IMPORTANT: You must return ONLY the raw JSON object. Do not wrap the JSON in markdown code blocks like ```json ... ```. "
            f"Do not include any explanations, pre-text, or post-text. The response must contain the lowercase word 'json' to satisfy formatting requirements."
        )

        full_system_prompt = system_prompt + json_instruction

        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            req_data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.7
                }
            }
            res = await client.post(f"{self.base_url}/api/chat", json=req_data)
            if res.status_code != 200:
                raise ValueError(f"Ollama returned status {res.status_code}: {res.text}")
            
            data = res.json()
            content = data.get("message", {}).get("content")
            if content is None:
                raise ValueError("Ollama returned an empty response")

        # Clean markdown code blocks if present
        cleaned_content = content.strip()
        if cleaned_content.startswith("```"):
            cleaned_content = re.sub(r"^```(?:json)?\s*", "", cleaned_content)
            cleaned_content = re.sub(r"\s*```$", "", cleaned_content)
        cleaned_content = cleaned_content.strip()

        try:
            parsed = json.loads(cleaned_content)
        except json.JSONDecodeError as je:
            logger.error("Ollama JSON parsing failed. Content was: %r. Error: %s", content, je)
            raise ValueError(f"Invalid JSON from Ollama: {je}") from je

        DEFAULTS_MAP = {
            "IntentClassification": {
                "intent": "negotiation",
                "confidence": 0.95,
                "reasoning": "Schema repair",
                "target_product_ids": []
            },
            "ConversationAnalysis": {
                "objection_type": "price",
                "negotiation_intent": "general negotiation",
                "urgency": 0.5,
                "sentiment": "neutral",
                "stage": "consideration"
            },
            "DigitalTwinProfile": {
                "price_sensitivity": 0.5,
                "urgency": 0.5,
                "risk_aversion": 0.5,
                "brand_loyalty": 0.5,
                "decision_speed": 0.5
            },
            "LLMStrategyOutput": {
                "strategy_name": "discount",
                "strategy": "discount",
                "offer_type": "discount",
                "discount_percent": 0.0,
                "bundle_value": 0.0,
                "reasoning": "Schema repair",
                "explanation": "Schema repair",
                "confidence": 0.9
            },
            "SearchExtraction": {
                "query": "",
                "is_product_related": False
            }
        }

        repaired = dict(parsed)
        MAX_REPAIR_ATTEMPTS = 2
        for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
            try:
                validated = response_model.model_validate(repaired)
                logger.info("Ollama output validated successfully for %s", model_name)
                return validated
            except Exception as ve:
                if attempt == MAX_REPAIR_ATTEMPTS:
                    logger.error("Repair failed for %s after %d attempts. Payload: %s. Error: %s", model_name, attempt, repaired, ve)
                    raise ve

                logger.warning(
                    "Pydantic validation failed for %s (attempt %d/%d) with payload: %s. Error: %s. Attempting repair...",
                    model_name, attempt + 1, MAX_REPAIR_ATTEMPTS, repaired, ve
                )

                from pydantic import ValidationError
                if isinstance(ve, ValidationError):
                    for err in ve.errors():
                        loc = err.get("loc")
                        if loc and isinstance(loc, tuple) and len(loc) == 1:
                            field_name = loc[0]
                            if isinstance(field_name, str) and field_name in response_model.model_fields:
                                field = response_model.model_fields[field_name]
                                model_defaults = DEFAULTS_MAP.get(model_name, {})
                                if field_name in model_defaults:
                                    repaired[field_name] = model_defaults[field_name]
                                else:
                                    from pydantic_core import PydanticUndefined
                                    if field.default is not PydanticUndefined:
                                        repaired[field_name] = field.default
                                    elif field.default_factory is not None:
                                        repaired[field_name] = field.default_factory()
                                    else:
                                        ann = field.annotation
                                        ann_str = str(ann).lower()
                                        if "str" in ann_str:
                                            repaired[field_name] = "unknown"
                                        elif "float" in ann_str or "int" in ann_str:
                                            repaired[field_name] = 0.0
                                        elif "list" in ann_str:
                                            repaired[field_name] = []
                                        elif "dict" in ann_str:
                                            repaired[field_name] = {}
                                        elif "bool" in ann_str:
                                            repaired[field_name] = False
                                        else:
                                            repaired[field_name] = None
                        else:
                            model_defaults = DEFAULTS_MAP.get(model_name, {})
                            for k, val in model_defaults.items():
                                if k not in repaired:
                                    repaired[k] = val
                            break
                else:
                    model_defaults = DEFAULTS_MAP.get(model_name, {})
                    for k, val in model_defaults.items():
                        if k not in repaired:
                            repaired[k] = val


class GracefulFallbackProvider(LLMProvider):
    """Wraps primary (Groq/Gemini/OpenAI) and secondary (Ollama) providers and falls back to DeterministicFallbackProvider."""

    def __init__(self, primary: LLMProvider | None = None) -> None:
        self.primary = primary
        self.ollama = None
        if settings.ENABLE_OLLAMA_FALLBACK:
            self.ollama = OllamaProvider(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL
            )
        self.fallback = DeterministicFallbackProvider()

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        response_model: type[T],
    ) -> T:
        model_name = response_model.__name__
        log_model_name = "ResponseGeneration" if model_name == "_LLMResponseOutput" else model_name
        logger.info("GracefulFallbackProvider.generate called for model: %s", model_name)
        
        # Increment global call counters
        llm_call_counts[model_name] = llm_call_counts.get(model_name, 0) + 1
        llm_call_counts["total"] += 1
        logger.info("GracefulFallbackProvider: Incrementing call count. Current counts: %s", llm_call_counts)

        # Check circuit breaker
        circuit_state = await circuit_breaker_service.check_circuit()
        
        try_primary = False
        if circuit_state == "closed":
            try_primary = True
        elif circuit_state == "half_open":
            if await circuit_breaker_service.acquire_half_open_probe():
                logger.warning("GracefulFallbackProvider: Groq is in HALF-OPEN state. Acquired probe lock. Probing Groq.")
                try_primary = True
            else:
                logger.warning("GracefulFallbackProvider: Groq is in HALF-OPEN state but another probe is active. Skipping Groq.")
                metrics_service.increment("fallback_count")
        else:
            logger.warning("GracefulFallbackProvider: Groq Circuit Breaker is OPEN. Skipping Groq completely.")
            metrics_service.increment("fallback_count")

        start_time = time.time()

        # Try primary (Groq/Gemini/OpenAI) if set and allowed
        if self.primary is not None and try_primary:
            try:
                prov_name = self.primary.__class__.__name__.lower().replace("provider", "")
                res = await self.primary.generate(prompt, system_prompt, response_model)
                logger.info("Primary LLM provider successfully generated output. provider=%s for model: %s", prov_name, model_name)
                metrics_service.increment(f"provider_used:{prov_name}")
                
                await circuit_breaker_service.record_success()
                
                end_time = time.time()
                elapsed = end_time - start_time
                logger.info(
                    "[LLM PROFILE] Model: %s | Provider: %s | Start: %.4f | End: %.4f | Elapsed: %.4fs | Retries: 0 | Fallback: False",
                    log_model_name, prov_name, start_time, end_time, elapsed
                )
                return res
            except Exception as e:
                logger.error("Primary LLM provider failed: %s. Falling back.", e)
                
                err_str = str(e).lower()
                is_unrecoverable = False
                
                try:
                    import groq
                    if isinstance(e, (groq.AuthenticationError, groq.RateLimitError)):
                        is_unrecoverable = True
                except ImportError:
                    pass
                
                try:
                    import openai
                    if isinstance(e, (openai.AuthenticationError, openai.RateLimitError)):
                        is_unrecoverable = True
                except ImportError:
                    pass
                
                if any(phrase in err_str for phrase in [
                    "401", "unauthorized", "authentication", "api key", 
                    "invalid_api_key", "missing api key", "429", "quota", 
                    "rate limit", "rate_limit", "resource_exhausted"
                ]):
                    is_unrecoverable = True
                
                if is_unrecoverable:
                    logger.warning("Unrecoverable error/429/401 detected on primary provider: %s. Tripping circuit breaker immediately.", e)
                    await circuit_breaker_service.record_failure(trip_immediately=True)
                else:
                    await circuit_breaker_service.record_failure(trip_immediately=False)
                
                if "429" in err_str or "rate limit" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                    metrics_service.increment("429_count")
                
                metrics_service.increment("fallback_count")
        
        # Try Ollama fallback if enabled
        if self.ollama is not None and getattr(self.ollama, "enabled", False):
            try:
                res = await self.ollama.generate(prompt, system_prompt, response_model)
                logger.info("Secondary LLM provider (Ollama) successfully generated output. provider=ollama for model: %s", model_name)
                metrics_service.increment("provider_used:ollama")
                
                end_time = time.time()
                elapsed = end_time - start_time
                logger.info(
                    "[LLM PROFILE] Model: %s | Provider: ollama | Start: %.4f | End: %.4f | Elapsed: %.4fs | Retries: 0 | Fallback: True",
                    log_model_name, start_time, end_time, elapsed
                )
                return res
            except Exception as e:
                logger.error("Secondary LLM provider (Ollama) failed: %s. Falling back to deterministic.", e)
                metrics_service.increment("fallback_count")
        
        # Try Deterministic fallback
        res = await self.fallback.generate(prompt, system_prompt, response_model)
        logger.info("Deterministic fallback generated output. provider=deterministic for model: %s", model_name)
        metrics_service.increment("provider_used:deterministic")
        
        end_time = time.time()
        elapsed = end_time - start_time
        logger.info(
            "[LLM PROFILE] Model: %s | Provider: deterministic | Start: %.4f | End: %.4f | Elapsed: %.4fs | Retries: 0 | Fallback: True",
            log_model_name, start_time, end_time, elapsed
        )
        return res


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
    
    elif provider_name == "ollama":
        primary_provider = OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL
        )

    elif provider_name == "openai":
        if settings.OPENAI_API_KEY:
            primary_provider = OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.DEFAULT_MODEL,
            )
        else:
            logger.warning("OPENAI_API_KEY not set. Utilizing Graceful Fallback.")

    elif provider_name == "groq":
        if settings.GROQ_API_KEY:
            primary_provider = GroqProvider(
                api_key=settings.GROQ_API_KEY,
                model=settings.DEFAULT_MODEL if settings.DEFAULT_MODEL != "gemini-2.0-flash" else "llama-3.3-70b-versatile",
            )
        else:
            logger.warning("GROQ_API_KEY not set. Utilizing Graceful Fallback.")

    else:
        logger.warning("Unknown or unsupported LLM provider name: %s. Utilizing Graceful Fallback.", provider_name)

    return GracefulFallbackProvider(primary_provider)
