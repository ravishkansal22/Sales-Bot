"""LLM provider abstraction and application settings.

Defines an abstract :class:`LLMProvider` interface and two concrete
implementations—:class:`GeminiProvider` (Google Generative AI) and
:class:`OpenAIProvider` (OpenAI)—plus a :func:`get_llm_provider`
factory and the centralised :class:`Settings` configuration object.
"""

from __future__ import annotations

import json
import logging
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
# Factory
# ---------------------------------------------------------------------------


def get_llm_provider(provider_override: str | None = None) -> LLMProvider:
    """Factory function that returns the configured LLM provider.

    Reads from the ``LLM_PROVIDER`` environment variable (via
    :data:`settings`) unless ``provider_override`` is given.

    Args:
        provider_override: Optional provider name to override settings.

    Returns:
        An initialised :class:`LLMProvider` instance.

    Raises:
        ValueError: If the provider name is unrecognised.
        ValueError: If the required API key is not set.
    """
    provider_name = (provider_override or settings.LLM_PROVIDER).lower().strip()

    if provider_name == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY must be set when using the Gemini provider"
            )
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.DEFAULT_MODEL,
        )

    if provider_name == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY must be set when using the OpenAI provider"
            )
        return OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.DEFAULT_MODEL,
        )

    raise ValueError(
        f"Unknown LLM provider: {provider_name!r}. "
        f"Supported providers: gemini, openai"
    )
