"""Chat API router — full Ghost Negotiator pipeline.

Exposes the primary ``/chat`` endpoint that orchestrates conversation
analysis, digital-twin construction, multi-strategy simulation, and
response generation.  Every intermediate result is persisted to the
database so the negotiation history is fully auditable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.conversation_analyzer import ConversationAnalyzer
from app.core.digital_twin import DigitalTwinBuilder
from app.core.response_generator import ResponseGenerator
from app.core.simulation_engine import SimulationEngine
from app.core.strategies.registry import StrategyRegistry
from app.core.strategy_optimizer import StrategyOptimizer
from app.db.postgres import get_db
from app.models.conversation import Conversation
from app.models.customer import Customer, DigitalTwinSnapshot
from app.models.simulation import SimulationResult
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.simulation import DigitalTwinProfile, SimulationOutput
from app.services.llm_service import get_llm_provider, get_settings

router = APIRouter(tags=["chat"])


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
        External customer identifier (may be a UUID string or slug).

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
        List of ``{"role": ..., "message": ...}`` dicts ordered by
        ``created_at`` ascending.
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
        The latest snapshot or ``None`` if the customer has never been
        profiled.
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
    """Convert a persisted ``DigitalTwinSnapshot`` to a Pydantic schema.

    Parameters
    ----------
    snapshot:
        The ORM snapshot instance.

    Returns
    -------
    DigitalTwinProfile
        A Pydantic schema suitable for passing to core modules.
    """

    return DigitalTwinProfile(
        price_sensitivity=snapshot.price_sensitivity,
        urgency=snapshot.urgency,
        risk_aversion=snapshot.risk_aversion,
        brand_loyalty=snapshot.brand_loyalty,
        decision_speed=snapshot.decision_speed,
    )


def _find_winning_simulation(
    simulations: list[SimulationOutput],
    winning_strategy: str,
) -> SimulationOutput:
    """Find the simulation matching the winning strategy name.

    Parameters
    ----------
    simulations:
        All simulation outputs.
    winning_strategy:
        Name of the winning strategy.

    Returns
    -------
    SimulationOutput
        The matching simulation output.
    """
    for sim in simulations:
        if sim.strategy_name == winning_strategy:
            return sim
    # Fallback to first simulation if name doesn't match exactly.
    return simulations[0]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Execute the full Ghost Negotiator pipeline and return a response.

    Pipeline steps
    --------------
    1. Get or create the customer record.
    2. Load conversation history and latest twin snapshot.
    3. Analyse the incoming message in the context of the history.
    4. Persist the user message as a conversation turn.
    5. Build / update the digital-twin profile.
    6. Persist a twin snapshot.
    7. Run multi-strategy simulations via ``SimulationEngine``.
    8. Optimise strategies via ``StrategyOptimizer``.
    9. Generate a natural-language response and internal reasoning.
    10. Persist simulation results (marking the winner).
    11. Persist the assistant reply as a conversation turn.
    12. Return the assembled ``ChatResponse``.

    Parameters
    ----------
    request:
        Incoming chat payload containing the customer message, IDs, and
        deal economics.
    db:
        Injected async database session (auto-committed on success).

    Returns
    -------
    ChatResponse
        Full response including digital twin, simulations, winner, the
        generated reply, and internal reasoning.

    Raises
    ------
    HTTPException
        500 if any pipeline stage fails unexpectedly.
    """
    try:
        # -- 0. Bootstrap services -------------------------------------------
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
        resp_generator = ResponseGenerator(llm=llm)

        # -- 1. Customer ------------------------------------------------------
        customer = await _get_or_create_customer(db, request.customer_id)

        # -- 2. History & existing twin ---------------------------------------
        history = await _load_conversation_history(db, request.customer_id)
        existing_snapshot = await _load_latest_twin_snapshot(
            db, request.customer_id
        )
        existing_twin = (
            _snapshot_to_twin_profile(existing_snapshot)
            if existing_snapshot is not None
            else None
        )

        # -- 3. Conversation analysis ----------------------------------------
        analysis = await analyzer.analyze(request.message, history)

        # -- 4. Save user message ---------------------------------------------
        user_turn = Conversation(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            message=request.message,
            role="user",
            analysis=analysis.model_dump(),
        )
        db.add(user_turn)
        await db.flush()

        # -- 5. Digital twin --------------------------------------------------
        digital_twin = await twin_builder.build_twin(
            analysis, history, existing_twin
        )

        # -- 6. Persist twin snapshot -----------------------------------------
        twin_snapshot = DigitalTwinSnapshot(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            price_sensitivity=digital_twin.price_sensitivity,
            urgency=digital_twin.urgency,
            risk_aversion=digital_twin.risk_aversion,
            brand_loyalty=digital_twin.brand_loyalty,
            decision_speed=digital_twin.decision_speed,
        )
        db.add(twin_snapshot)
        await db.flush()

        # -- 7. Simulations ---------------------------------------------------
        simulations = await sim_engine.simulate_all(
            digital_twin, analysis, request.deal_value, request.cost_basis
        )

        # -- 8. Strategy optimisation (deterministic) -------------------------
        winner = StrategyOptimizer.optimize(simulations)

        # -- 9. Generate response ---------------------------------------------
        winning_sim = _find_winning_simulation(
            simulations, winner.winning_strategy
        )
        response_text, internal_reasoning = await resp_generator.generate(
            winner, winning_sim, digital_twin, analysis
        )

        # -- 10. Persist simulation results -----------------------------------
        for sim in simulations:
            is_winner = sim.strategy_name == winner.winning_strategy
            sim_record = SimulationResult(
                id=str(uuid.uuid4()),
                conversation_id=user_turn.id,
                customer_id=customer.id,
                strategy_name=sim.strategy_name,
                offer_type=sim.offer_type,
                discount_percent=sim.discount_percent,
                bundle_value=sim.bundle_value,
                reasoning=sim.reasoning,
                close_probability=sim.average_close_probability,
                expected_profit=sim.average_expected_profit,
                expected_value=sim.average_expected_value,
                risk_score=sim.average_risk_score,
                confidence_score=0.0,  # Will be set for winner below
                optimizer_reasoning=winner.optimizer_reasoning if is_winner else None,
                winning_factors=winner.winning_factors if is_winner else None,
                rollout_count=len(sim.rollouts),
                rollouts=[r.model_dump() for r in sim.rollouts],
                is_winner=is_winner,
            )
            if is_winner:
                sim_record.confidence_score = winner.confidence_score
            db.add(sim_record)

        # -- 11. Save assistant reply -----------------------------------------
        assistant_turn = Conversation(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            message=response_text,
            role="assistant",
            analysis=None,
        )
        db.add(assistant_turn)

        await db.commit()

        # -- 12. Assemble response -------------------------------------------
        return ChatResponse(
            digital_twin=digital_twin,
            simulations=simulations,
            winner=winner,
            response=response_text,
            internal_reasoning=internal_reasoning,
        )

    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {exc!s}",
        ) from exc


@router.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Health-check endpoint with database connectivity verification.

    Executes a trivial ``SELECT 1`` against the database to confirm
    end-to-end connectivity.  Returns a JSON object with service status,
    database status, and the current UTC timestamp.

    Parameters
    ----------
    db:
        Injected async database session.

    Returns
    -------
    dict[str, str]
        ``{"status": "healthy", "database": "connected",
        "timestamp": "<ISO-8601>"}`` on success.

    Raises
    ------
    HTTPException
        503 if the database is unreachable.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {exc!s}",
        ) from exc
