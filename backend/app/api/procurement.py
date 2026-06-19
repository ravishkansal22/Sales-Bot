from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, UTC
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order
from app.models.negotiation_context import NegotiationContext
from app.models.locked_deal import LockedDeal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/procurement", tags=["procurement"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LockDealRequest(BaseModel):
    customer_id: str = Field(..., description="UUID or external ID of customer")
    product_id: str = Field(..., description="UUID or external ID of product")
    quantity: int = Field(1, ge=1)
    negotiated_price: float = Field(..., ge=0.0)
    concessions: list[str] = Field(default_factory=list)
    strategy: str = Field(...)
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)

class UpdateQuantityRequest(BaseModel):
    quantity: int = Field(..., ge=1)

class FinalizePurchaseRequest(BaseModel):
    customer_id: str = Field(...)

# ---------------------------------------------------------------------------
# Dynamic PDF Generator
# ---------------------------------------------------------------------------

def generate_procurement_pdf(
    customer_name: str,
    customer_id: str,
    items: list[dict[str, Any]],
    totals: dict[str, Any],
    file_path: str
) -> None:
    """Generate a clean B2B procurement summary PDF using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_text_color(30, 41, 59) # Slate 800

    # Decorative Border
    pdf.set_draw_color(0, 242, 254) # Cyan Glow
    pdf.set_line_width(0.8)
    pdf.rect(5, 5, 200, 287)

    # Title Banner
    pdf.set_fill_color(15, 23, 42) # Slate 900
    pdf.rect(5, 5, 200, 30, "F")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "GHOST NEGOTIATOR", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 242, 254)
    pdf.cell(0, 5, "B2B CONTRACT SUPPLY AGREEMENT SUMMARY", ln=True, align="C")
    pdf.ln(15)

    pdf.set_text_color(30, 41, 59)
    # Metadata Block
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, "Customer Name:")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(60, 6, customer_name)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, "Date:")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(50, 6, datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"), ln=True)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, "Customer ID:")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(60, 6, customer_id)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, "Order Reference:")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(50, 6, f"GNO-{uuid.uuid4().hex[:8].upper()}", ln=True)
    pdf.ln(8)

    # Line Item Table Header
    pdf.set_fill_color(241, 245, 249) # Slate 100
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(50, 8, "Product Name", border=1, fill=True)
    pdf.cell(20, 8, "Qty", border=1, fill=True, align="C")
    pdf.cell(30, 8, "Catalog Price", border=1, fill=True, align="R")
    pdf.cell(30, 8, "Negotiated Price", border=1, fill=True, align="R")
    pdf.cell(30, 8, "Savings", border=1, fill=True, align="R")
    pdf.cell(30, 8, "Strategy", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 9)
    for item in items:
        savings = (item["catalog_price"] - item["negotiated_price"]) * item["quantity"]
        pdf.cell(50, 8, item["product_name"], border=1)
        pdf.cell(20, 8, str(item["quantity"]), border=1, align="C")
        pdf.cell(30, 8, f"INR {item['catalog_price']:,.2f}", border=1, align="R")
        pdf.cell(30, 8, f"INR {item['negotiated_price']:,.2f}", border=1, align="R")
        pdf.cell(30, 8, f"INR {savings:,.2f}", border=1, align="R")
        pdf.cell(30, 8, item["strategy"].upper(), border=1, align="C", ln=True)

    pdf.ln(5)

    # Totals Summary Block
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(100, pdf.get_y(), 100, 32, "F")
    
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_x(105)
    pdf.cell(45, 6, "Total Items:")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(45, 6, str(totals["total_items"]), ln=True, align="R")

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_x(105)
    pdf.cell(45, 6, "Catalog Subtotal:")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(45, 6, f"INR {totals['catalog_total']:,.2f}", ln=True, align="R")

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_x(105)
    pdf.cell(45, 6, "Negotiated B2B Total:")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(45, 6, f"INR {totals['negotiated_total']:,.2f}", ln=True, align="R")

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(16, 185, 129) # Emerald Green
    pdf.set_x(105)
    pdf.cell(45, 6, f"Total Savings ({totals['average_savings_pct']:.1f}%):")
    pdf.cell(45, 6, f"INR {totals['total_savings']:,.2f}", ln=True, align="R")

    pdf.set_text_color(30, 41, 59)
    pdf.ln(12)

    # Concessions list
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Locked Concessions & Agreements", ln=True)
    pdf.set_font("Helvetica", "", 9)
    
    has_concessions = False
    for item in items:
        if item["concessions"]:
            has_concessions = True
            concessions_str = ", ".join(item["concessions"])
            pdf.cell(0, 5, f"- {item['product_name']}: {concessions_str}", ln=True)

    if not has_concessions:
        pdf.cell(0, 5, "No custom value-add concessions loaded.", ln=True)

    pdf.ln(15)

    # Footer legal text
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184) # Slate 400
    pdf.multi_cell(0, 4, "Disclaimer: This document is a generated summary of terms agreed upon in the B2B Ghost Negotiator environment. Terms are locked for procurement routing and contract execution.", align="C")

    pdf.output(file_path)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/lock")
async def lock_deal(
    req: LockDealRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Lock negotiation terms and insert into procurement cart."""
    # Resolve customer
    customer = None
    try:
        cust_uuid = uuid.UUID(req.customer_id)
        customer = await db.get(Customer, cust_uuid)
    except ValueError:
        stmt = select(Customer).where(Customer.external_customer_id == req.customer_id)
        res = await db.execute(stmt)
        customer = res.scalars().first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{req.customer_id}' not found.",
        )

    # Resolve product
    product = None
    try:
        prod_uuid = uuid.UUID(req.product_id)
        product = await db.get(Product, prod_uuid)
    except ValueError:
        stmt = select(Product).where(Product.external_product_id == req.product_id)
        res = await db.execute(stmt)
        product = res.scalars().first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{req.product_id}' not found.",
        )

    # Upsert LockedDeal
    stmt = select(LockedDeal).where(
        LockedDeal.customer_id == customer.id,
        LockedDeal.product_id == product.id
    )
    res = await db.execute(stmt)
    deal = res.scalars().first()

    if deal:
        deal.quantity = req.quantity
        deal.negotiated_price = req.negotiated_price
        deal.concessions = req.concessions
        deal.strategy = req.strategy
        deal.confidence_score = req.confidence_score
    else:
        deal = LockedDeal(
            id=uuid.uuid4(),
            customer_id=customer.id,
            product_id=product.id,
            quantity=req.quantity,
            negotiated_price=req.negotiated_price,
            concessions=req.concessions,
            strategy=req.strategy,
            confidence_score=req.confidence_score
        )
        db.add(deal)

    await db.commit()
    return {"status": "success", "message": "Deal locked in cart successfully.", "deal_id": str(deal.id)}


@router.get("/cart")
async def get_cart(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Fetch B2B procurement cart items and computed saving totals."""
    # Resolve customer
    customer = None
    try:
        cust_uuid = uuid.UUID(customer_id)
        customer = await db.get(Customer, cust_uuid)
    except ValueError:
        stmt = select(Customer).where(Customer.external_customer_id == customer_id)
        res = await db.execute(stmt)
        customer = res.scalars().first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found.",
        )

    # Fetch locked deals
    stmt = select(LockedDeal).where(LockedDeal.customer_id == customer.id)
    res = await db.execute(stmt)
    deals = res.scalars().all()

    items = []
    catalog_total = 0.0
    negotiated_total = 0.0
    total_items = 0

    for d in deals:
        prod = d.product
        items.append({
            "deal_id": str(d.id),
            "product_id": prod.external_product_id or str(prod.id),
            "product_name": prod.name,
            "catalog_price": prod.selling_price,
            "negotiated_price": d.negotiated_price,
            "quantity": d.quantity,
            "concessions": d.concessions,
            "strategy": d.strategy,
            "confidence_score": d.confidence_score
        })
        catalog_total += prod.selling_price * d.quantity
        negotiated_total += d.negotiated_price * d.quantity
        total_items += d.quantity

    total_savings = catalog_total - negotiated_total
    average_savings_pct = (total_savings / catalog_total * 100.0) if catalog_total > 0 else 0.0

    return {
        "items": items,
        "summary": {
            "total_items": total_items,
            "catalog_total": catalog_total,
            "negotiated_total": negotiated_total,
            "total_savings": total_savings,
            "average_savings_pct": average_savings_pct
        }
    }


@router.delete("/cart/{deal_id}")
async def remove_from_cart(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Remove a locked deal from the procurement cart."""
    deal_uuid = uuid.UUID(deal_id)
    await db.execute(delete(LockedDeal).where(LockedDeal.id == deal_uuid))
    await db.commit()
    return {"status": "success", "message": "Item removed from cart."}


@router.put("/cart/{deal_id}/quantity")
async def update_quantity(
    deal_id: str,
    req: UpdateQuantityRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Edit item quantity inside the procurement cart."""
    deal_uuid = uuid.UUID(deal_id)
    await db.execute(
        update(LockedDeal)
        .where(LockedDeal.id == deal_uuid)
        .values(quantity=req.quantity)
    )
    await db.commit()
    return {"status": "success", "message": "Quantity updated."}


@router.post("/cart/{deal_id}/reopen")
async def reopen_negotiation(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Reopen negotiation for a cart item, restoring active negotiation context."""
    deal_uuid = uuid.UUID(deal_id)
    stmt = select(LockedDeal).where(LockedDeal.id == deal_uuid)
    res = await db.execute(stmt)
    deal = res.scalars().first()

    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal record not found.",
        )

    # Upsert NegotiationContext
    stmt = select(NegotiationContext).where(NegotiationContext.customer_id == deal.customer_id)
    res = await db.execute(stmt)
    context = res.scalars().first()

    if context:
        context.product_id = deal.product_id
        context.quantity = deal.quantity
        context.current_offer = deal.negotiated_price
        context.requested_discount = round((1.0 - deal.negotiated_price / deal.product.selling_price) * 100, 2)
        context.current_strategy = deal.strategy
        context.negotiation_stage = "negotiation"
    else:
        context = NegotiationContext(
            id=uuid.uuid4(),
            customer_id=deal.customer_id,
            product_id=deal.product_id,
            quantity=deal.quantity,
            current_offer=deal.negotiated_price,
            requested_discount=round((1.0 - deal.negotiated_price / deal.product.selling_price) * 100, 2),
            current_strategy=deal.strategy,
            negotiation_stage="negotiation"
        )
        db.add(context)

    # Delete from cart
    await db.delete(deal)
    await db.commit()

    return {"status": "success", "message": "Negotiation reopened for this product."}


@router.post("/purchase")
async def finalize_purchase(
    req: FinalizePurchaseRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Finalize purchase, empty cart, create order records and generate PDF procurement summary."""
    # Resolve customer
    customer = None
    try:
        cust_uuid = uuid.UUID(req.customer_id)
        customer = await db.get(Customer, cust_uuid)
    except ValueError:
        stmt = select(Customer).where(Customer.external_customer_id == req.customer_id)
        res = await db.execute(stmt)
        customer = res.scalars().first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{req.customer_id}' not found.",
        )

    # Fetch locked deals in cart
    stmt = select(LockedDeal).where(LockedDeal.customer_id == customer.id)
    res = await db.execute(stmt)
    deals = res.scalars().all()

    if not deals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Procurement cart is empty.",
        )

    items_data = []
    catalog_total = 0.0
    negotiated_total = 0.0
    total_items = 0

    # Create order records for database
    for d in deals:
        prod = d.product
        items_data.append({
            "product_name": prod.name,
            "catalog_price": prod.selling_price,
            "negotiated_price": d.negotiated_price,
            "quantity": d.quantity,
            "strategy": d.strategy,
            "concessions": d.concessions
        })
        catalog_total += prod.selling_price * d.quantity
        negotiated_total += d.negotiated_price * d.quantity
        total_items += d.quantity

        # Create Order record
        order = Order(
            id=uuid.uuid4(),
            customer_id=customer.id,
            product_id=prod.id,
            purchase_price=d.negotiated_price * d.quantity,
            purchase_date=datetime.now(UTC),
            payment_method="B2B Wire / Invoicing",
            delivery_status="Processing"
        )
        db.add(order)
        # Clear stock quantity
        prod.stock_quantity = max(0, prod.stock_quantity - d.quantity)
        # Delete locked deal
        await db.delete(d)

    # Update customer stats
    customer.total_orders += len(deals)
    customer.total_spend += negotiated_total
    customer.average_order_value = customer.total_spend / customer.total_orders
    customer.last_purchase_date = datetime.now(UTC)

    totals = {
        "total_items": total_items,
        "catalog_total": catalog_total,
        "negotiated_total": negotiated_total,
        "total_savings": catalog_total - negotiated_total,
        "average_savings_pct": (catalog_total - negotiated_total) / catalog_total * 100.0 if catalog_total > 0 else 0.0
    }

    # Generate PDF summary file in workspace
    order_id = uuid.uuid4().hex[:8].upper()
    pdf_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public", "pdf")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = f"procurement_summary_{order_id}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    generate_procurement_pdf(
        customer_name=customer.name,
        customer_id=customer.external_customer_id or str(customer.id),
        items=items_data,
        totals=totals,
        file_path=pdf_path
    )

    await db.commit()

    return {
        "status": "success",
        "message": "Purchase finalized. Orders created successfully.",
        "summary": totals,
        "pdf_url": f"/api/v1/procurement/download/{pdf_filename}",
        "order_reference": f"GNO-{order_id}"
    }


@router.get("/download/{filename}")
def download_pdf(filename: str):
    """Retrieve generated procurement PDF summary."""
    pdf_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public", "pdf")
    file_path = os.path.join(pdf_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF Summary file not found."
        )
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=filename
    )
