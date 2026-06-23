"""Base strategy interface for Ghost Negotiator negotiation strategies.

All negotiation strategies must inherit from the abstract ``Strategy`` base class
and implement ``build_prompt`` and ``get_constraints``.  Strategies are discovered
at runtime through the :class:`~app.core.strategies.registry.StrategyRegistry`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile


class Strategy(ABC):
    """Abstract base class for negotiation strategies.

    Every concrete strategy must define:

    * ``name`` – a unique human-readable identifier (e.g. ``"discount"``).
    * ``offer_type`` – the category of offer this strategy produces
      (e.g. ``"percentage_discount"``, ``"value_bundle"``).
    * ``build_prompt`` – constructs the LLM prompt for a single rollout.
    * ``get_constraints`` – returns deterministic constraints the LLM
      output will be validated/clamped against.
    """

    name: str
    offer_type: str

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def build_prompt(
        self,
        twin: DigitalTwinProfile,
        analysis: ConversationAnalysis,
        deal_value: float,
        cost_basis: float,
        rollout_index: int,
    ) -> str:
        """Build the LLM prompt for a single simulation rollout.

        Parameters
        ----------
        twin:
            The digital-twin customer profile with behavioural scores.
        analysis:
            Real-time analysis of the latest customer message.
        deal_value:
            Total monetary value of the deal under negotiation (USD).
        cost_basis:
            Internal cost of fulfilling the deal (USD).
        rollout_index:
            Zero-based index of the current rollout, allowing the
            prompt to request variance across rollouts.

        Returns
        -------
        str
            A fully-formed prompt string ready to be sent to an LLM.
        """

    @abstractmethod
    def get_constraints(self, context_json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return strategy-specific constraints for validation.

        The dictionary **must** include at least:

        * ``min_discount_percent`` (float)
        * ``max_discount_percent`` (float)
        * ``min_bundle_value`` (float)
        * ``max_bundle_value`` (float)

        Parameters
        ----------
        context_json:
            Optional negotiation session state context.

        Returns
        -------
        dict
            Constraint key-value pairs.
        """
