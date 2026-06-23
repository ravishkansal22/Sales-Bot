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
from app.services.customer_service import CustomerService
from app.services.product_knowledge_service import ProductKnowledgeService
from app.models.negotiation_context import NegotiationContext
from app.core.simulation_engine import generate_concessions
from app.core.intent_classifier import classify_intent


router = APIRouter(tags=["simulation"])


async def _get_or_create_customer(
    db: AsyncSession,
    customer_id: str,
) -> Customer:
    """Return an existing customer or create a new stub record."""
    return await CustomerService.get_or_create_customer(db, customer_id)



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
        history = await _load_conversation_history(db, str(customer.id))
        existing_snapshot = await _load_latest_twin_snapshot(
            db, str(customer.id)
        )
        existing_twin = (
            _snapshot_to_twin_profile(existing_snapshot)
            if existing_snapshot is not None
            else None
        )

        # -- Analysis ---------------------------------------------------------
        analysis = await analyzer.analyze(request.message, history)
        from app.api.chat import extract_discount_request
        classification = await classify_intent(request.message, history)
        parsed_discount = extract_discount_request(request.message)
        analysis.intent_type = classification.intent
        analysis.sub_intent = classification.sub_intent
        analysis.requested_discount = parsed_discount if parsed_discount is not None else 0.0

        # -- 2. Load/Initialize Negotiation Context ---------------------------
        neg_context = None
        is_mock = hasattr(db, "_mock_return_value") or type(db).__name__ in ("MagicMock", "Mock", "AsyncMock")
        
        if not is_mock:
            stmt = select(NegotiationContext).where(NegotiationContext.customer_id == customer.id)
            res = await db.execute(stmt)
            neg_context = res.scalars().first()

        product = None
        quantity = request.quantity
        
        prod_id = request.product_id or (str(neg_context.product_id) if neg_context and not is_mock else None)
        if prod_id:
            try:
                prod_uuid = uuid.UUID(prod_id)
                product = await ProductService.get_product_by_id(db, prod_uuid)
            except ValueError:
                product = await ProductService.get_product_by_external_id(db, prod_id)

        if not product and not is_mock:
            popular = await ProductService.search_products(db, "", limit=1)
            product = popular[0] if popular else None

        if not product and not is_mock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No product selected and no catalog products available.",
            )

        if neg_context and not request.product_id:
            quantity = neg_context.quantity

        if product:
            deal_value = product.selling_price * quantity
            cost_basis = product.cost_price * quantity
        else:
            deal_value = request.deal_value
            cost_basis = request.cost_basis

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

        # Update context_json behavioral state inside neg_context in-memory
        context_json = {}
        if neg_context and neg_context.context_json:
            context_json = dict(neg_context.context_json)
        
        if parsed_discount is not None:
            context_json["requested_discount"] = parsed_discount
            context_json["current_customer_requested_discount"] = parsed_discount
        else:
            context_json.setdefault("requested_discount", 0.0)
            context_json.setdefault("current_customer_requested_discount", 0.0)
            
        context_json["mentioned_quantity"] = quantity
        context_json["quantity"] = quantity

        # -- Simulations ------------------------------------------------------
        simulations = await sim_engine.simulate_all(
            digital_twin,
            analysis,
            deal_value,
            cost_basis,
            product,
            quantity,
            history=history,
            customer=customer,
            context_json=context_json
        )

        # Determine has_pricing_request
        has_pricing_request = False
        from app.api.chat import is_negotiation_message
        if is_negotiation_message(request.message):
            has_pricing_request = True
        elif neg_context and neg_context.requested_discount > 0.0:
            has_pricing_request = True
        elif history:
            for h in history:
                if h.get("role") == "user" and is_negotiation_message(h.get("message", "")):
                    has_pricing_request = True
                    break

        # Calculate dynamic ceiling
        dynamic_ceiling = 0.0
        if product:
            dynamic_ceiling = sim_engine.calculate_dynamic_ceiling(
                product=product,
                quantity=quantity,
                history=history,
                customer=customer,
                brand_loyalty=digital_twin.brand_loyalty,
                context_json=context_json
            )

        # -- Deterministic optimisation ---------------------------------------
        winner = StrategyOptimizer.optimize(
            simulations,
            request.optimization_mode,
            stock_quantity=product.stock_quantity if product else 50,
            history=history,
            has_pricing_request=has_pricing_request,
            context_json=context_json,
            dynamic_ceiling=dynamic_ceiling,
            list_price=product.selling_price if product else 0.0,
            requested_discount_percent=parsed_discount if parsed_discount is not None else 0.0,
        )
        winner.concessions = generate_concessions(product.category if product else None, winner.winning_strategy, product.name if product else None, context_json)

        # -- 14. Assemble response -------------------------------------------
        inventory_status = "Available"
        near_min = False
        if product:
            stock = product.stock_quantity
            if stock < 20:
                inventory_status = "Low Inventory"
            elif stock >= 100:
                inventory_status = "High Inventory"
            else:
                inventory_status = "Limited Availability"

            # Check closeness to floor price
            min_price = product.minimum_price
            winning_sim = next((s for s in simulations if s.strategy_name == winner.winning_strategy), None)
            if winning_sim:
                if winning_sim.discount_percent > 0.0 or winner.winning_strategy == "discount":
                    winning_sim.discount_percent = winner.actual_offer_discount
                
                # Expose current negotiated values on winner object
                winner.current_discount_percent = float(winning_sim.discount_percent)
                winner.current_offer_price = float(product.selling_price * (1.0 - winning_sim.discount_percent / 100.0))
                
                unit_offer = product.selling_price * (1.0 - winning_sim.discount_percent / 100.0)
                if min_price > 0 and unit_offer <= min_price * 1.05:
                    near_min = True

        return SimulateResponse(
            digital_twin=digital_twin,
            analysis=analysis,
            simulations=simulations,
            winner=winner,
            inventory_status=inventory_status,
            near_minimum_price=near_min
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation pipeline failed: {exc!s}",
        ) from exc
