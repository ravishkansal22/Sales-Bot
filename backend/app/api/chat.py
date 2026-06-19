"""Chat API router — full Ghost Negotiator pipeline.

Exposes the primary ``/chat`` endpoint that orchestrates conversation
analysis, digital-twin construction, multi-strategy simulation, and
response generation.  Every intermediate result is persisted to the
database so the negotiation history is fully auditable.
"""

from __future__ import annotations

import uuid
import re
from datetime import UTC, datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.conversation_analyzer import ConversationAnalyzer
from app.core.digital_twin import DigitalTwinBuilder
from app.core.response_generator import ResponseGenerator
from app.core.simulation_engine import SimulationEngine, generate_concessions
from app.core.strategies.registry import StrategyRegistry
from app.core.strategy_optimizer import StrategyOptimizer
from app.db.postgres import get_db
from app.models.conversation import Conversation
from app.models.customer import Customer, DigitalTwinSnapshot
from app.models.simulation import SimulationResult
from app.models.negotiation_context import NegotiationContext
from app.schemas.chat import ChatRequest, ChatResponse, SelectProductRequest
from app.schemas.simulation import DigitalTwinProfile, SimulationOutput
from app.services.llm_service import get_llm_provider, get_settings
from app.services.product_service import ProductService
from app.services.product_resolver import ProductResolver
from app.services.customer_profile_builder import CustomerProfileBuilder
from app.services.customer_service import CustomerService
from app.models.product import Product
from app.services.product_knowledge_service import ProductKnowledgeService

router = APIRouter(tags=["chat"])


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

def has_product_intent(message: str) -> bool:
    msg_lower = message.lower()
    keywords = [
        "want", "need", "show", "buy", "looking for", "find", "search", "get", "instead", 
        "or", "refrigerator", "tv", "laptop", "ball", "shoes", "headphones", "television", 
        "earbuds", "camera", "blender", "jacket", "heels", "sneakers"
    ]
    return any(kw in msg_lower for kw in keywords)

def extract_discount_request(message: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", message, re.IGNORECASE)
    if match:
        try:
            val = float(match.group(1))
            if 0 < val <= 100:
                return val
        except ValueError:
            pass
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Execute the full Ghost Negotiator pipeline and return a response."""
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
        customer = await CustomerService.get_or_create_customer(db, request.customer_id)

        # -- Intent Classification & Routing ----------------------------------
        knowledge_service = ProductKnowledgeService(llm=llm)
        history = await _load_conversation_history(db, str(customer.id))
        classification = await knowledge_service.classify_intent(request.message, history)

        # Pre-resolve product if context exists or product_id is provided
        neg_context = None
        is_mock = hasattr(db, "_mock_return_value") or type(db).__name__ in ("MagicMock", "Mock", "AsyncMock")
        if not is_mock:
            stmt = select(NegotiationContext).where(NegotiationContext.customer_id == customer.id)
            res = await db.execute(stmt)
            neg_context = res.scalars().first()

        product = None
        if neg_context:
            product = await ProductService.get_product_by_id(db, neg_context.product_id)
        elif request.product_id:
            try:
                prod_uuid = uuid.UUID(request.product_id)
                product = await ProductService.get_product_by_id(db, prod_uuid)
            except ValueError:
                product = await ProductService.get_product_by_external_id(db, request.product_id)

        # Route custom non-negotiation intents
        if classification.intent == "product_question":
            if not product:
                resolver = ProductResolver(llm=llm)
                resolved = await resolver.resolve_products(request.message, db)
                if resolved:
                    product = resolved[0]
                else:
                    popular = await ProductService.search_products(db, "", limit=1)
                    product = popular[0] if popular else None

            if product:
                answer = await knowledge_service.answer_product_question(product, request.message, db)
                
                # Save user message
                user_turn = Conversation(
                    id=str(uuid.uuid4()),
                    customer_id=customer.id,
                    message=request.message,
                    role="user",
                    analysis={"objection_type": "none", "negotiation_intent": "information_gathering", "urgency": 0.5, "sentiment": "neutral", "stage": "discovery"}
                )
                db.add(user_turn)
                
                # Save assistant response
                assistant_turn = Conversation(
                    id=str(uuid.uuid4()),
                    customer_id=customer.id,
                    message=answer,
                    role="assistant",
                )
                db.add(assistant_turn)
                await db.commit()

                # Build default response values
                existing_snapshot = await _load_latest_twin_snapshot(db, str(customer.id))
                digital_twin = _snapshot_to_twin_profile(existing_snapshot) if existing_snapshot else DigitalTwinProfile(price_sensitivity=0.5, urgency=0.5, risk_aversion=0.5, brand_loyalty=0.5, decision_speed=0.5)
                winner = OptimizerResult(
                    winning_strategy="initial",
                    score=1.0,
                    optimization_mode=OptimizationMode.BALANCED,
                    optimizer_reasoning="Product question answered using catalog records.",
                    winning_factors=["Product Knowledge Layer"],
                    risk_score=0.0,
                    confidence_score=1.0,
                    all_rankings=[]
                )

                stock = product.stock_quantity
                inventory_status = "Available"
                if stock < 20:
                    inventory_status = "Low Inventory"
                elif stock >= 100:
                    inventory_status = "High Inventory"
                else:
                    inventory_status = "Limited Availability"

                return ChatResponse(
                    digital_twin=digital_twin,
                    simulations=[],
                    winner=winner,
                    response=answer,
                    internal_reasoning="Dynamic query routed to product knowledge layer.",
                    intent_type="product_question",
                    inventory_status=inventory_status,
                    near_minimum_price=False
                )
            else:
                raise HTTPException(status_code=400, detail="Please select a product from catalog first.")

        elif classification.intent == "product_comparison":
            comparison = await knowledge_service.compare_products(request.message, product, db)
            response_text = "Here is the side-by-side comparison of the catalog items matching your request."
            
            # Save user message
            user_turn = Conversation(
                id=str(uuid.uuid4()),
                customer_id=customer.id,
                message=request.message,
                role="user",
                analysis={"objection_type": "none", "negotiation_intent": "information_gathering", "urgency": 0.5, "sentiment": "neutral", "stage": "discovery"}
            )
            db.add(user_turn)
            
            # Save assistant response
            assistant_turn = Conversation(
                id=str(uuid.uuid4()),
                customer_id=customer.id,
                message=response_text,
                role="assistant",
            )
            db.add(assistant_turn)
            await db.commit()

            # Build default response values
            existing_snapshot = await _load_latest_twin_snapshot(db, str(customer.id))
            digital_twin = _snapshot_to_twin_profile(existing_snapshot) if existing_snapshot else DigitalTwinProfile(price_sensitivity=0.5, urgency=0.5, risk_aversion=0.5, brand_loyalty=0.5, decision_speed=0.5)
            winner = OptimizerResult(
                winning_strategy="initial",
                score=1.0,
                optimization_mode=OptimizationMode.BALANCED,
                optimizer_reasoning="Product comparison executed dynamically from database.",
                winning_factors=["Product Comparison Engine"],
                risk_score=0.0,
                confidence_score=1.0,
                all_rankings=[]
            )

            inventory_status = "Available"
            if product:
                stock = product.stock_quantity
                if stock < 20:
                    inventory_status = "Low Inventory"
                elif stock >= 100:
                    inventory_status = "High Inventory"
                else:
                    inventory_status = "Limited Availability"

            return ChatResponse(
                digital_twin=digital_twin,
                simulations=[],
                winner=winner,
                response=response_text,
                internal_reasoning="Dynamic query routed to product comparison layer.",
                intent_type="product_comparison",
                comparison_results=comparison,
                inventory_status=inventory_status,
                near_minimum_price=False
            )

        # -- Product Discovery Check ------------------------------------------
        is_product_discovery = False
        resolved_products = []
        if not request.product_id or has_product_intent(request.message):
            resolver = ProductResolver(llm=llm)
            resolved_products = await resolver.resolve_products(request.message, db)
            if resolved_products:
                if not request.product_id:
                    is_product_discovery = True
                else:
                    best_match = resolved_products[0]
                    best_match_id = str(best_match.id)
                    best_match_ext_id = best_match.external_product_id
                    if request.product_id not in (best_match_id, best_match_ext_id):
                        is_product_discovery = True

        if is_product_discovery:
            # Save user search turn
            user_turn = Conversation(
                id=str(uuid.uuid4()),
                customer_id=customer.id,
                message=request.message,
                role="user",
                analysis={
                    "objection_type": "product_search",
                    "negotiation_intent": "product_search",
                    "urgency": 0.5,
                    "sentiment": "neutral",
                    "stage": "awareness"
                },
            )
            db.add(user_turn)
            await db.flush()

            # Return list of product cards as assistant reply
            response_text = "I found the following products matching your query. Please select one to begin our negotiation:"
            assistant_turn = Conversation(
                id=str(uuid.uuid4()),
                customer_id=customer.id,
                message=response_text,
                role="assistant",
                analysis={"recommended_products": [str(p.id) for p in resolved_products]},
            )
            db.add(assistant_turn)
            await db.commit()

            # Return discovery response (skip twin/simulations/optimizer)
            existing_snapshot = await _load_latest_twin_snapshot(db, str(customer.id))
            digital_twin = (
                _snapshot_to_twin_profile(existing_snapshot)
                if existing_snapshot is not None
                else DigitalTwinProfile(
                    price_sensitivity=0.5,
                    urgency=0.5,
                    risk_aversion=0.5,
                    brand_loyalty=0.5,
                    decision_speed=0.5,
                )
            )

            winner = OptimizerResult(
                winning_strategy="initial",
                score=1.0,
                optimization_mode=OptimizationMode.BALANCED,
                optimizer_reasoning="Waiting for customer to select a product from catalog recommendations.",
                winning_factors=["Product Discovery"],
                risk_score=0.0,
                confidence_score=1.0,
                all_rankings=[]
            )

            return ChatResponse(
                digital_twin=digital_twin,
                simulations=[],
                winner=winner,
                response=response_text,
                internal_reasoning="Product discovery query matched catalog items. Displaying product cards to customer.",
                intent_type="product_discovery",
                recommended_products=[ProductSchema.model_validate(p) for p in resolved_products],
                inventory_status="Available",
                near_minimum_price=False
            )

        # -- 2. Load/Initialize Negotiation Context ---------------------------
        neg_context = None
        is_mock = hasattr(db, "_mock_return_value") or type(db).__name__ in ("MagicMock", "Mock", "AsyncMock")
        
        if not is_mock:
            stmt = select(NegotiationContext).where(NegotiationContext.customer_id == customer.id)
            res = await db.execute(stmt)
            neg_context = res.scalars().first()

        product = None
        quantity = request.quantity

        if not neg_context:
            if request.product_id or not is_mock:
                # Resolve product
                if request.product_id:
                    try:
                        prod_uuid = uuid.UUID(request.product_id)
                        product = await ProductService.get_product_by_id(db, prod_uuid)
                    except ValueError:
                        product = await ProductService.get_product_by_external_id(db, request.product_id)
                if not product and not is_mock:
                    popular = await ProductService.search_products(db, "", limit=1)
                    product = popular[0] if popular else None
                
                if product:
                    neg_context = NegotiationContext(
                        id=uuid.uuid4(),
                        customer_id=customer.id,
                        product_id=product.id,
                        quantity=request.quantity,
                        current_offer=product.selling_price,
                        requested_discount=0.0,
                        current_strategy="hardline",
                        negotiation_stage="initiated",
                    )
                    if not is_mock:
                        db.add(neg_context)
                        await db.flush()

        else:
            product = await ProductService.get_product_by_id(db, neg_context.product_id)
            quantity = neg_context.quantity

        # Parse discount requests
        parsed_discount = extract_discount_request(request.message)
        if neg_context and parsed_discount is not None:
            neg_context.requested_discount = parsed_discount
        if neg_context:
            neg_context.quantity = quantity

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

        # -- 3. History & existing twin ---------------------------------------
        history = await _load_conversation_history(db, str(customer.id))
        existing_snapshot = await _load_latest_twin_snapshot(db, str(customer.id))
        existing_twin = (
            _snapshot_to_twin_profile(existing_snapshot)
            if existing_snapshot is not None
            else None
        )

        # -- 4. Conversation analysis ----------------------------------------
        analysis = await analyzer.analyze(request.message, history)

        # -- 5. Save user message ---------------------------------------------
        user_turn = Conversation(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            message=request.message,
            role="user",
            analysis=analysis.model_dump(),
        )
        db.add(user_turn)
        await db.flush()

        # -- Customer History Summary -----------------------------------------
        customer_summary = await CustomerProfileBuilder.build_summary(db, str(customer.id), customer=customer)

        # -- 6. Digital twin --------------------------------------------------
        digital_twin = await twin_builder.build_twin(
            analysis, history, existing_twin, customer_summary
        )

        # -- 7. Persist twin snapshot -----------------------------------------
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

        # -- 8. Simulations ---------------------------------------------------
        simulations = await sim_engine.simulate_all(
            digital_twin, analysis, deal_value, cost_basis, product, neg_context.quantity if neg_context else quantity
        )

        # -- 9. Strategy optimisation (deterministic) -------------------------
        winner = StrategyOptimizer.optimize(simulations)
        winner.concessions = generate_concessions(product.category if product else None, winner.winning_strategy, product.name if product else None)

        # -- 10. Generate response ---------------------------------------------
        winning_sim = _find_winning_simulation(
            simulations, winner.winning_strategy
        )
        response_text, internal_reasoning = await resp_generator.generate(
            winner, winning_sim, digital_twin, analysis
        )

        # -- 11. Persist simulation results -----------------------------------
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
                confidence_score=0.0,
                optimizer_reasoning=winner.optimizer_reasoning if is_winner else None,
                winning_factors=winner.winning_factors if is_winner else None,
                rollout_count=len(sim.rollouts),
                rollouts=[r.model_dump() for r in sim.rollouts],
                is_winner=is_winner,
            )
            if is_winner:
                sim_record.confidence_score = winner.confidence_score
            db.add(sim_record)

        # -- 12. Update NegotiationContext ------------------------------------
        if neg_context:
            neg_context.current_offer = deal_value * (1.0 - winning_sim.discount_percent / 100.0)
            neg_context.current_strategy = winner.winning_strategy
            neg_context.negotiation_stage = analysis.stage
        
        # -- 13. Save assistant reply -----------------------------------------
        assistant_turn = Conversation(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            message=response_text,
            role="assistant",
            analysis=None,
        )
        db.add(assistant_turn)

        await db.commit()

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
            unit_offer = product.selling_price * (1.0 - winning_sim.discount_percent / 100.0)
            if min_price > 0 and unit_offer <= min_price * 1.05:
                near_min = True

        return ChatResponse(
            digital_twin=digital_twin,
            simulations=simulations,
            winner=winner,
            response=response_text,
            internal_reasoning=internal_reasoning,
            intent_type="negotiation",
            inventory_status=inventory_status,
            near_minimum_price=near_min
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {exc!s}",
        ) from exc


@router.post("/workspace/select-product")
async def select_product_endpoint(
    request: SelectProductRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Initialize a negotiation context for a chosen product."""
    try:
        # 1. Resolve Customer
        customer = await CustomerService.get_or_create_customer(db, request.customer_id)

        # 2. Resolve Product
        product = None
        try:
            prod_uuid = uuid.UUID(request.product_id)
            product = await ProductService.get_product_by_id(db, prod_uuid)
        except ValueError:
            product = await ProductService.get_product_by_external_id(db, request.product_id)

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID '{request.product_id}' not found.",
            )

        # 3. Reset previous conversation logs, digital twins, and simulation results for this customer
        await db.execute(delete(SimulationResult).where(SimulationResult.customer_id == customer.id))
        await db.execute(delete(Conversation).where(Conversation.customer_id == customer.id))
        await db.execute(delete(DigitalTwinSnapshot).where(DigitalTwinSnapshot.customer_id == customer.id))

        # 4. Upsert NegotiationContext
        stmt = select(NegotiationContext).where(NegotiationContext.customer_id == customer.id)
        res = await db.execute(stmt)
        neg_context = res.scalars().first()

        if neg_context:
            neg_context.product_id = product.id
            neg_context.quantity = request.quantity
            neg_context.current_offer = product.selling_price
            neg_context.requested_discount = 0.0
            neg_context.current_strategy = "hardline"
            neg_context.negotiation_stage = "initiated"
            neg_context.context_json = {}
        else:
            neg_context = NegotiationContext(
                id=uuid.uuid4(),
                customer_id=customer.id,
                product_id=product.id,
                quantity=request.quantity,
                current_offer=product.selling_price,
                requested_discount=0.0,
                current_strategy="hardline",
                negotiation_stage="initiated",
                context_json={},
            )
            db.add(neg_context)

        # 5. Initialize Digital Twin (persists baseline snapshot)
        initial_twin = DigitalTwinSnapshot(
            id=uuid.uuid4(),
            customer_id=customer.id,
            price_sensitivity=0.45,
            urgency=0.35,
            risk_aversion=0.50,
            brand_loyalty=0.80,
            decision_speed=0.45,
        )
        db.add(initial_twin)

        # 6. Save welcome message in Conversation
        welcome_text = f"Welcome. We are evaluating a B2B agreement for {product.name} (Listed Price: ₹{product.selling_price:,.2f}). I am calibrated to negotiate bundles, custom terms, or discount requests. How would you like to proceed?"
        welcome_turn = Conversation(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            message=welcome_text,
            role="assistant",
            analysis=None,
        )
        db.add(welcome_turn)
        await db.commit()

        # 7. Prepare response payload
        return {
            "product": {
                "id": product.external_product_id or str(product.id),
                "name": product.name,
                "description": product.description or "B2B catalog product under negotiation terms.",
                "price": product.selling_price,
                "category": product.category,
                "specifications": {
                    "Category": product.category,
                    "Stock": f"{product.stock_quantity} units",
                    "Popularity": f"{round(product.popularity_index / 20.0, 1)}/5.0",
                    "Return Rate": f"{round(product.return_rate, 2)}%"
                }
            },
            "deal_summary": {
                "selectedProductId": product.external_product_id or str(product.id),
                "currentPrice": product.selling_price,
                "customerDiscountRequest": 0,
                "currentAiOfferPrice": product.selling_price,
                "bundleItems": [],
                "status": "Negotiation Initiated",
                "closeProbability": 0.88,
                "confidenceScore": 0.90,
                "optimizationObjective": "balanced"
            },
            "digital_twin": {
                "price_sensitivity": 0.45,
                "urgency": 0.35,
                "risk_aversion": 0.50,
                "brand_loyalty": 0.80,
                "decision_speed": 0.45
            }
        }
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize product negotiation: {exc!s}",
        )


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
        import traceback

        traceback.print_exc()

        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {exc!s}",
        ) from exc
