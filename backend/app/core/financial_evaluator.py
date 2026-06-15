"""Deterministic financial evaluator for Ghost Negotiator.

All computations are pure Python arithmetic — **no LLM, no AI**.  Every
public method is a ``@staticmethod`` so the evaluator carries no mutable
state and is trivially thread-safe.
"""

from __future__ import annotations

from app.schemas.simulation import FinancialMetrics


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
    ) -> FinancialMetrics:
        """Compute deterministic financial metrics for a deal configuration.

        Parameters
        ----------
        deal_value:
            Total revenue of the deal at list price (USD).  Must be > 0.
        cost_basis:
            Internal cost to fulfil the deal **excluding** bundle add-ons
            (USD).  Must be >= 0.
        discount_percent:
            Percentage discount offered to the customer (0–100).
        bundle_value:
            Additional cost of value-add bundles included in the offer
            (USD).  Must be >= 0.

        Returns
        -------
        FinancialMetrics
            A Pydantic model containing:

            * **gross_margin_retention** – fraction of original gross
              margin retained after the discount + bundle cost.
              Clamped to ``[0.0, 1.0]``.
            * **revenue_impact** – fractional change in revenue vs. list
              price.  Negative when a discount is applied.
            * **profit_impact** – absolute dollar change in gross profit
              vs. the no-discount baseline.
            * **contract_leakage** – ``1 − gross_margin_retention``,
              i.e. the fraction of margin that has been eroded.

        Formulae
        --------
        ::

            discounted_revenue  = deal_value × (1 − discount_percent / 100)
            total_cost          = cost_basis + bundle_value
            original_margin     = deal_value − cost_basis
            new_margin          = discounted_revenue − total_cost

            gross_margin_retention = clamp(new_margin / original_margin, 0, 1)
            revenue_impact         = (discounted_revenue − deal_value) / deal_value
            profit_impact          = new_margin − original_margin
            contract_leakage       = 1 − gross_margin_retention
        """

        # --- guard against degenerate inputs --------------------------------
        if deal_value <= 0:
            return FinancialMetrics(
                gross_margin_retention=0.0,
                revenue_impact=0.0,
                profit_impact=0.0,
                contract_leakage=1.0,
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
            # Edge case: deal is already at or below cost.  Any discount or
            # bundle cost makes things worse, so retention is 0.
            gross_margin_retention = 0.0
        else:
            gross_margin_retention = max(0.0, min(new_margin / original_margin, 1.0))

        revenue_impact: float = (discounted_revenue - deal_value) / deal_value
        profit_impact: float = new_margin - original_margin
        contract_leakage: float = 1.0 - gross_margin_retention

        return FinancialMetrics(
            gross_margin_retention=round(gross_margin_retention, 6),
            revenue_impact=round(revenue_impact, 6),
            profit_impact=round(profit_impact, 2),
            contract_leakage=round(contract_leakage, 6),
        )
