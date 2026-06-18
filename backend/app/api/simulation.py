"""Simulation API router — simulation-only pipeline (no response generation).

Exposes the ``/simulate`` endpoint that runs conversation analysis,
digital-twin construction, and multi-strategy simulation without
producing a customer-facing reply.  Useful for *what-if* analysis,
strategy exploration, and debugging.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.conversation_analyzer import ConversationAnalyzer
from app.core.digital_twin import DigitalTwinBuilder
from app.core.simulation_engine import SimulationEngine
from app.core.strategies.registry import StrategyRegistry
from app.core.strategy_optimizer import StrategyOptimizer
from app.db.postgres import get_db
from app.models.conversation import Conversation
from app.models.customer import Customer, DigitalTwinSnapshot
from app.schemas.simulation import (
    DigitalTwinProfile,
    SimulateRequest,
    SimulateResponse,
)
from app.services.llm_service import get_llm_provider, get_settings
from app.services.product_service import ProductService
from app.services.customer_profile_builder import CustomerProfileBuilder

router = APIRouter(tags=["simulation"])


async def _get_or_create_customer(
    db: AsyncSession,
    customer_id: str,
) -> Customer:
    """Return an existing customer or create a new stub record.

    Parameters
    ----------
    db:
        Active async database session.
    customer_id:
        External customer identifier.

    Returns
    -------
    Customer
        The persisted ``Customer`` ORM instance.
    """
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer: Customer | None = result.scalars().first()

    if customer is not None:
        return customer

    customer = Customer(
        id=customer_id,
        name=f"Customer {customer_id[:8]}",
        email=None,
        metadata_={},
    )
    db.add(customer)
    await db.flush()
    return customer


async def _load_conversation_history(
    db: AsyncSession,
    customer_id: str,
) -> list[dict[str, Any]]:
    """Fetch the full ordered conversation history for a customer.

    Parameters
    ----------
    db:
        Active async database session.
    customer_id:
        Customer primary key.

    Returns
    -------
    list[dict[str, Any]]
        Ordered list of ``{"role": ..., "message": ...}`` dicts.
    """
    result = await db.execute(
        select(Conversation)
        .where(Conversation.customer_id == customer_id)
        .order_by(Conversation.created_at.asc())
    )
    rows: list[Conversation] = list(result.scalars().all())
    return [{"role": r.role, "message": r.message} for r in rows]


async def _load_latest_twin_snapshot(
    db: AsyncSession,
    customer_id: str,
) -> DigitalTwinSnapshot | None:
    """Return the most recent digital-twin snapshot for a customer.

    Parameters
    ----------
    db:
        Active async database session.
    customer_id:
        Customer primary key.

    Returns
    -------
    DigitalTwinSnapshot | None
        Latest snapshot or ``None``.
    """
    result = await db.execute(
        select(DigitalTwinSnapshot)
        .where(DigitalTwinSnapshot.customer_id == customer_id)
        .order_by(DigitalTwinSnapshot.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


def _snapshot_to_twin_profile(
    snapshot: DigitalTwinSnapshot,
) -> DigitalTwinProfile:
    """Convert a ``DigitalTwinSnapshot`` ORM object to a Pydantic schema.

    Parameters
    ----------
    snapshot:
        Persisted snapshot.

    Returns
    -------
    DigitalTwinProfile
        A Pydantic schema suitable for core modules.
    """
    return DigitalTwinProfile(
        price_sensitivity=snapshot.price_sensitivity,
        urgency=snapshot.urgency,
        risk_aversion=snapshot.risk_aversion,
        brand_loyalty=snapshot.brand_loyalty,
        decision_speed=snapshot.decision_speed,
    )


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(
    request: SimulateRequest,
    db: AsyncSession = Depends(get_db),
) -> SimulateResponse:
    """Run the simulation pipeline without generating a customer response.

    Pipeline steps
    --------------
    1. Get or create the customer record.
    2. Load conversation history and latest twin snapshot.
    3. Analyse the incoming message.
    4. Build / update the digital-twin profile.
    5. Run multi-strategy simulations.
    6. Optimise and select the winning strategy (deterministic).
    7. Return analysis, twin, simulations, and winner.

    Parameters
    ----------
    request:
        Simulation request payload.
    db:
        Injected async database session.

    Returns
    -------
    SimulateResponse
        Digital twin, conversation analysis, simulation outputs, and
        the winning strategy.

    Raises
    ------
    HTTPException
        500 on any unexpected failure.
    """
    try:
        # -- Bootstrap services -----------------------------------------------
        settings = get_settings()
        llm = get_llm_provider()
        registry = StrategyRegistry()
        analyzer = ConversationAnalyzer(llm=llm)
        twin_builder = DigitalTwinBuilder(llm=llm)
        sim_engine = SimulationEngine(
            llm=llm,
            registry=registry,
            rollout_count=settings.ROLLOUT_COUNT,
        )

        # -- Customer ---------------------------------------------------------
        customer = await _get_or_create_customer(db, request.customer_id)

        # -- History & existing twin ------------------------------------------
        history = await _load_conversation_history(db, request.customer_id)
        existing_snapshot = await _load_latest_twin_snapshot(
            db, request.customer_id
        )
        existing_twin = (
            _snapshot_to_twin_profile(existing_snapshot)
            if existing_snapshot is not None
            else None
        )

        # -- Analysis ---------------------------------------------------------
        analysis = await analyzer.analyze(request.message, history)

        # -- Customer Product & Quantity Resolution --------------------------
        product = None
        quantity = request.quantity
        if request.product_id:
            try:
                prod_uuid = uuid.UUID(request.product_id)
                product = await ProductService.get_product_by_id(db, prod_uuid)
            except ValueError:
                product = await ProductService.get_product_by_external_id(db, request.product_id)

        deal_value = product.selling_price * quantity if product else request.deal_value
        cost_basis = product.cost_price * quantity if product else request.cost_basis

        if deal_value is None or cost_basis is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="deal_value and cost_basis must be provided if product_id is not specified.",
            )

        # -- Customer History Summary -----------------------------------------
        customer_summary = await CustomerProfileBuilder.build_summary(db, str(customer.id), customer=customer)

        # -- Digital twin -----------------------------------------------------
        digital_twin = await twin_builder.build_twin(
            analysis, history, existing_twin, customer_summary
        )

        # -- Simulations ------------------------------------------------------
        simulations = await sim_engine.simulate_all(
            digital_twin, analysis, deal_value, cost_basis, product, quantity
        )

        # -- Deterministic optimisation ---------------------------------------
        winner = StrategyOptimizer.optimize(
            simulations,
            request.optimization_mode,
        )

        return SimulateResponse(
            digital_twin=digital_twin,
            analysis=analysis,
            simulations=simulations,
            winner=winner,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation pipeline failed: {exc!s}",
        ) from exc
