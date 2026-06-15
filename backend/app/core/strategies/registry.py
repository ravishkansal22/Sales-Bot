"""Strategy registry for Ghost Negotiator.

Provides a central, extensible registry of negotiation strategies.  New
strategies can be registered at runtime via :meth:`StrategyRegistry.register`.
"""

from __future__ import annotations

from app.core.strategies.base import Strategy
from app.core.strategies.bundle import BundleStrategy
from app.core.strategies.discount import DiscountStrategy
from app.core.strategies.hardline import HardlineStrategy
from app.core.strategies.personalized import PersonalizedStrategy


class StrategyRegistry:
    """Manage the set of available negotiation strategies.

    On construction the registry is pre-populated with the four built-in
    strategies.  Additional strategies can be added at any time via
    :meth:`register`.

    Attributes
    ----------
    _strategies : list[Strategy]
        Internal mutable list of registered strategy instances.
    """

    _strategies: list[Strategy]

    def __init__(self) -> None:
        """Initialise the registry with the four built-in strategies."""

        self._strategies = [
            DiscountStrategy(),
            HardlineStrategy(),
            BundleStrategy(),
            PersonalizedStrategy(),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all(self) -> list[Strategy]:
        """Return a shallow copy of all registered strategies.

        Returns
        -------
        list[Strategy]
            Every strategy currently in the registry.
        """

        return list(self._strategies)

    def get_by_name(self, name: str) -> Strategy | None:
        """Look up a strategy by its canonical ``name`` attribute.

        Parameters
        ----------
        name:
            Case-insensitive strategy name (e.g. ``"discount"``).

        Returns
        -------
        Strategy | None
            The matching strategy, or ``None`` if not found.
        """

        name_lower = name.lower().strip()
        for strategy in self._strategies:
            if strategy.name.lower().strip() == name_lower:
                return strategy
        return None

    def register(self, strategy: Strategy) -> None:
        """Add a new strategy to the registry.

        If a strategy with the same ``name`` already exists it is
        replaced silently — this allows hot-patching strategies at
        runtime during testing or A/B experiments.

        Parameters
        ----------
        strategy:
            The strategy instance to register.
        """

        # Remove existing strategy with the same name (if any).
        self._strategies = [
            s for s in self._strategies
            if s.name.lower().strip() != strategy.name.lower().strip()
        ]
        self._strategies.append(strategy)

    def __len__(self) -> int:
        """Return the number of registered strategies."""
        return len(self._strategies)

    def __repr__(self) -> str:  # pragma: no cover
        names = [s.name for s in self._strategies]
        return f"StrategyRegistry(strategies={names})"
