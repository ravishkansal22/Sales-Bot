"""Catalog and customer intelligence API router.

Exposes endpoints for listing, searching, recommending products, and retrieving customer details.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.negotiation_context import NegotiationContext
from app.models.customer import Customer, DigitalTwinSnapshot
from app.models.simulation import SimulationResult
from app.models.conversation import Conversation
from app.models.product import Product
from app.schemas.product import ProductSchema
from app.services.customer_profile_builder import CustomerProfileBuilder
from app.services.llm_service import get_llm_provider
from app.services.product_resolver import ProductResolver
from app.services.product_service import ProductService
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/api/v1", tags=["Catalog"])



@router.get("/products", response_model=list[ProductSchema])
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve paginated list of catalog products.

    Args:
        page: Page number (1-based).
        limit: Number of items per page.
        db: Active database session.
    """
    offset = (page - 1) * limit
    stmt = select(Product).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/products/search", response_model=list[ProductSchema])
async def search_products(
    q: str = Query("", description="Keyword or term to search for"),
    db: AsyncSession = Depends(get_db),
):
    """Search products using keyword term across name and category.

    Args:
        q: The search query string.
        db: Active database session.
    """
    return await ProductService.search_products(db, q)


@router.get("/products/recommendations", response_model=list[ProductSchema])
async def recommend_products(
    q: str = Query(..., description="Query for fuzzy catalog matching"),
    db: AsyncSession = Depends(get_db),
):
    """Get fuzzy product recommendations based on search terms.

    Uses keyword mapping, SQL ILIKE search, and difflib similarity ratios.

    Args:
        q: Product selection query.
        db: Active database session.
    """
    llm = get_llm_provider()
    resolver = ProductResolver(llm=llm)
    return await resolver.resolve_products(q, db)


@router.get("/products/{id}", response_model=ProductSchema)
async def get_product(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed properties of a product by UUID or external product ID.

    Args:
        id: UUID string or external product ID (e.g. 'P1000').
        db: Active database session.
    """
    product = None
    try:
        prod_uuid = uuid.UUID(id)
        product = await ProductService.get_product_by_id(db, prod_uuid)
    except ValueError:
        # Fallback to external ID string
        product = await ProductService.get_product_by_external_id(db, id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID or External ID '{id}' not found.",
        )
    return product


@router.get("/customers/{id}")
async def get_customer(
    id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve customer details along with profile statistics.

    Args:
        id: UUID string or external customer ID.
        db: Active database session.
    """
    customer = None
    try:
        cust_uuid = uuid.UUID(id)
        customer = await db.get(Customer, cust_uuid)
    except ValueError:
        # Fallback to external customer ID
        stmt = select(Customer).where(Customer.external_customer_id == id)
        result = await db.execute(stmt)
        customer = result.scalars().first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID or External ID '{id}' not found.",
        )

    summary = await CustomerProfileBuilder.build_summary(db, str(customer.id))
    return {
        "customer": {
            "id": customer.id,
            "external_customer_id": customer.external_customer_id,
            "name": customer.name,
            "email": customer.email,
            "customer_segment": customer.customer_segment,
            "total_spend": customer.total_spend,
            "average_order_value": customer.average_order_value,
            "total_orders": customer.total_orders,
            "last_purchase_date": customer.last_purchase_date,
            "created_at": customer.created_at,
        },
        "history_summary": summary,
    }


async def _resolve_customer(db: AsyncSession, id_str: str) -> Customer | None:
    """Helper to resolve a customer from UUID or external customer ID string."""
    return await CustomerService.resolve_customer(db, id_str)


@router.get("/customers/{id}/twin")
async def get_customer_twin(
    id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve the latest digital twin snapshot for a customer."""
    customer = await _resolve_customer(db, id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID or External ID '{id}' not found.",
        )

    stmt = (
        select(DigitalTwinSnapshot)
        .where(DigitalTwinSnapshot.customer_id == customer.id)
        .order_by(DigitalTwinSnapshot.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    snapshot = res.scalars().first()
    if not snapshot:
        # Default fallback
        return {
            "price_sensitivity": 0.45,
            "urgency": 0.35,
            "risk_aversion": 0.50,
            "brand_loyalty": 0.80,
            "decision_speed": 0.45,
        }

    return {
        "price_sensitivity": snapshot.price_sensitivity,
        "urgency": snapshot.urgency,
        "risk_aversion": snapshot.risk_aversion,
        "brand_loyalty": snapshot.brand_loyalty,
        "decision_speed": snapshot.decision_speed,
    }


@router.get("/customers/{id}/twin-history")
async def get_customer_twin_history(
    id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve the twin snapshots history for a customer."""
    customer = await _resolve_customer(db, id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID or External ID '{id}' not found.",
        )

    stmt = (
        select(DigitalTwinSnapshot)
        .where(DigitalTwinSnapshot.customer_id == customer.id)
        .order_by(DigitalTwinSnapshot.created_at.asc())
    )
    res = await db.execute(stmt)
    snapshots = res.scalars().all()

    if not snapshots:
        return [
            {
                "timestamp": "Initial",
                "priceSensitivity": 45,
                "urgency": 35,
                "riskAversion": 50,
                "brandLoyalty": 80,
                "decisionSpeed": 45,
            }
        ]

    return [
        {
            "timestamp": snap.created_at.strftime("%I:%M %p") if snap.created_at else "Initial",
            "priceSensitivity": int(snap.price_sensitivity * 100),
            "urgency": int(snap.urgency * 100),
            "riskAversion": int(snap.risk_aversion * 100),
            "brandLoyalty": int(snap.brand_loyalty * 100),
            "decisionSpeed": int(snap.decision_speed * 100),
        }
        for snap in snapshots
    ]


@router.get("/customers/{id}/messages")
async def get_customer_messages(
    id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve all conversation messages for a customer."""
    customer = await _resolve_customer(db, id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID or External ID '{id}' not found.",
        )

    stmt = (
        select(Conversation)
        .where(Conversation.customer_id == customer.id)
        .order_by(Conversation.created_at.asc())
    )
    res = await db.execute(stmt)
    turns = res.scalars().all()

    result_list = []
    for t in turns:
        msg_data = {
            "id": str(t.id),
            "sender": "customer" if t.role == "user" else "company",
            "text": t.message,
            "timestamp": t.created_at.strftime("%I:%M %p") if t.created_at else "",
            "created_at": t.created_at.isoformat() if t.created_at else "",
            "client_message_id": t.analysis.get("client_message_id") if (t.analysis and isinstance(t.analysis, dict)) else None
        }
        
        # Check if this is a product discovery turn with recommendations
        if t.analysis and "recommended_products" in t.analysis:
            prod_ids = t.analysis["recommended_products"]
            recommended_prods = []
            for p_id in prod_ids:
                try:
                    p_uuid = uuid.UUID(p_id)
                    p = await ProductService.get_product_by_id(db, p_uuid)
                except ValueError:
                    p = await ProductService.get_product_by_external_id(db, p_id)
                if p:
                    recommended_prods.append({
                        "id": p.external_product_id or str(p.id),
                        "name": p.name,
                        "description": p.description or "B2B catalog product under negotiation terms.",
                        "price": p.selling_price,
                        "category": p.category,
                        "specifications": {
                            "Category": p.category,
                            "Stock": f"{p.stock_quantity} units",
                            "Popularity": f"{round(p.popularity_index / 20.0, 1)}/5.0",
                            "Return Rate": f"{round(p.return_rate, 2)}%"
                        }
                    })
            msg_data["recommended_products"] = recommended_prods
            msg_data["intent_type"] = "product_discovery"
        result_list.append(msg_data)

    return result_list


@router.get("/customers/{id}/timeline")
async def get_customer_timeline(
    id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve a chronological timeline of negotiation events for a customer."""
    customer = await _resolve_customer(db, id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID or External ID '{id}' not found.",
        )

    stmt = (
        select(Conversation)
        .where(Conversation.customer_id == customer.id)
        .order_by(Conversation.created_at.asc())
    )
    res = await db.execute(stmt)
    turns = res.scalars().all()

    events = []
    events.append({
        "id": "init_deal",
        "type": "strategy",
        "timestamp": "10:00 AM",
        "title": "Deal Initialized",
        "description": f"B2B supply profile loaded for {customer.name}. Segment: {customer.customer_segment or 'Standard'}.",
        "status": "info"
    })

    for i, t in enumerate(turns):
        time_str = t.created_at.strftime("%I:%M %p") if t.created_at else "10:00 AM"
        if t.role == "user":
            analysis = t.analysis or {}
            objection_type = analysis.get("objection_type")
            if objection_type:
                events.append({
                    "id": f"obj_{t.id}",
                    "type": "objection" if objection_type == "price" else "urgency",
                    "timestamp": time_str,
                    "title": f"Objection Detected: {objection_type.capitalize()}",
                    "description": f"Customer: \"{t.message}\". Intent: {analysis.get('negotiation_intent', '')}.",
                    "status": "warning",
                    "client_message_id": analysis.get("client_message_id") if isinstance(analysis, dict) else None
                })
        else:
            user_turn = turns[i-1] if i > 0 else None
            if user_turn:
                sim_stmt = select(SimulationResult).where(SimulationResult.conversation_id == user_turn.id)
                sim_res = await db.execute(sim_stmt)
                sims = sim_res.scalars().all()
                if sims:
                    winner = next((s for s in sims if s.is_winner), None)
                    events.append({
                        "id": f"sim_{t.id}",
                        "type": "simulation",
                        "timestamp": time_str,
                        "title": "Monte Carlo Simulations Swept",
                        "description": f"Simulated {len(sims)} strategies. Winner: {winner.strategy_name if winner else 'None'}.",
                        "status": "info"
                    })
                    if winner:
                        events.append({
                            "id": f"opt_{t.id}",
                            "type": "optimizer",
                            "timestamp": time_str,
                            "title": "Optimizer Selected Winner",
                            "description": f"Strategy: {winner.strategy_name}. Expected Profit: Rs. {winner.expected_profit:,.2f}. Close Prob: {winner.close_probability:.0%}.",
                            "status": "success"
                        })
    return events


@router.get("/customers/{id}/simulations")
async def get_customer_simulations(
    id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve the latest strategy simulations run for a customer."""
    customer = await _resolve_customer(db, id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID or External ID '{id}' not found.",
        )

    stmt = (
        select(SimulationResult)
        .where(SimulationResult.customer_id == customer.id)
        .order_by(SimulationResult.created_at.desc())
    )
    res = await db.execute(stmt)
    sims = res.scalars().all()

    if not sims:
        return []

    latest_conv_id = sims[0].conversation_id
    latest_sims = [s for s in sims if s.conversation_id == latest_conv_id]

    return [
        {
            "strategy_name": s.strategy_name,
            "offer_type": s.offer_type,
            "discount_percent": s.discount_percent,
            "bundle_value": s.bundle_value,
            "reasoning": s.reasoning,
            "rollouts": s.rollouts or [],
            "average_close_probability": s.close_probability,
            "average_risk_score": s.risk_score,
            "average_expected_profit": s.expected_profit,
            "average_expected_value": s.expected_value,
            "average_gross_margin_retention": 1.0 - (s.discount_percent / 100.0) if s.discount_percent else 1.0
        }
        for s in latest_sims
    ]


@router.get("/customers/{id}/optimizer-result")
async def get_customer_optimizer_result(
    id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve the latest optimizer result for a customer."""
    customer = await _resolve_customer(db, id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID or External ID '{id}' not found.",
        )

    stmt_context = select(NegotiationContext).where(NegotiationContext.customer_id == customer.id)
    res_context = await db.execute(stmt_context)
    neg_context = res_context.scalars().first()

    current_discount_percent = 0.0
    current_offer_price = 0.0
    if neg_context and neg_context.context_json:
        current_discount_percent = neg_context.context_json.get("current_discount_percent", 0.0)
        current_offer_price = neg_context.context_json.get("current_offer_price", 0.0)

    stmt_winner = (
        select(SimulationResult)
        .where(SimulationResult.customer_id == customer.id, SimulationResult.is_winner == True)
        .order_by(SimulationResult.created_at.desc())
        .limit(1)
    )
    res_winner = await db.execute(stmt_winner)
    winner = res_winner.scalars().first()

    if not winner:
        return None

    return {
        "winning_strategy": winner.strategy_name,
        "score": winner.expected_value,
        "optimizer_reasoning": winner.optimizer_reasoning or "Optimal strategy chosen based on expected profit and risk.",
        "winning_factors": winner.winning_factors or ["Highest expected value"],
        "risk_score": winner.risk_score,
        "confidence_score": winner.confidence_score,
        "current_discount_percent": current_discount_percent,
        "current_offer_price": current_offer_price,
    }

