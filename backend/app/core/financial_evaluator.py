"""Deterministic financial evaluator for Ghost Negotiator.

All computations are pure Python arithmetic — **no LLM, no AI**.  Every
public method is a ``@staticmethod`` so the evaluator carries no mutable
state and is trivially thread-safe.
"""

from __future__ import annotations

import logging
import time
from app.schemas.simulation import FinancialMetrics

logger = logging.getLogger(__name__)


class FinancialEvaluator:
    """Evaluate the financial impact of a proposed deal configuration.

    The evaluator answers the question: *"Given a deal worth $X with cost
    basis $Y, what happens to our margins if we offer Z% discount and add
    a value-add bundle costing $B?"*

    All returned values are encapsulated in a
    :class:`~app.schemas.simulation.FinancialMetrics` model.
    """

    @staticmethod
    def evaluate(
        deal_value: float,
        cost_basis: float,
        discount_percent: float,
        bundle_value: float,
        product_selling_price: float | None = None,
        product_cost_price: float | None = None,
        product_minimum_price: float | None = None,
        quantity: int = 1,
    ) -> FinancialMetrics:
        """Compute deterministic financial metrics for a deal configuration.

        Supports dynamic product-derived overrides if product pricing is provided.
        """
        t0 = time.perf_counter()
        # --- apply product overrides if provided -----------------------------
        if product_selling_price is not None:
            deal_value = product_selling_price * quantity
        if product_cost_price is not None:
            cost_basis = product_cost_price * quantity

        # --- guard against degenerate inputs --------------------------------
        if deal_value <= 0:
            elapsed = time.perf_counter() - t0
            logger.info(f"FinancialEvaluator took {elapsed:.6f}s")
            return FinancialMetrics(
                gross_margin_retention=0.0,
                revenue_impact=0.0,
                profit_impact=0.0,
                contract_leakage=1.0,
                minimum_price_closeness=1.0,
            )

        discount_percent = max(0.0, min(discount_percent, 100.0))
        bundle_value = max(0.0, bundle_value)

        # --- core arithmetic ------------------------------------------------
        discounted_revenue: float = deal_value * (1.0 - discount_percent / 100.0)
        total_cost: float = cost_basis + bundle_value
        original_margin: float = deal_value - cost_basis
        new_margin: float = discounted_revenue - total_cost

        # --- derived metrics ------------------------------------------------
        if original_margin <= 0:
            gross_margin_retention = 0.0
        else:
            gross_margin_retention = max(0.0, min(new_margin / original_margin, 1.0))

        revenue_impact: float = (discounted_revenue - deal_value) / deal_value
        profit_impact: float = new_margin - original_margin
        contract_leakage: float = 1.0 - gross_margin_retention

        # --- calculate closeness to minimum price floor ----------------------
        minimum_price_closeness = 0.0
        if product_minimum_price is not None:
            min_allowed = product_minimum_price * quantity
            net_price = discounted_revenue - bundle_value
            
            if net_price <= min_allowed:
                minimum_price_closeness = 1.0
            else:
                price_cushion = net_price - min_allowed
                max_cushion = deal_value - min_allowed
                if max_cushion > 0:
                    minimum_price_closeness = 1.0 - min(1.0, max(0.0, price_cushion / max_cushion))
                else:
                    minimum_price_closeness = 1.0

        elapsed = time.perf_counter() - t0
        logger.info(f"FinancialEvaluator took {elapsed:.6f}s")
        return FinancialMetrics(
            gross_margin_retention=round(gross_margin_retention, 6),
            revenue_impact=round(revenue_impact, 6),
            profit_impact=round(profit_impact, 2),
            contract_leakage=round(contract_leakage, 6),
            minimum_price_closeness=round(minimum_price_closeness, 6),
        )
